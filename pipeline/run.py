"""One pass of the bot: scan live games, publish the biggest new call, queue its posts.

  python3 -m pipeline.run                       live games right now
  python3 -m pipeline.run --date 20261018 --dry-run   replay a past day and print what it would pick
"""
import argparse
import datetime as dt
import json
import os

from . import card, clips, detect, espn, page, social

ROOT = page.ROOT
STATE = os.path.join(ROOT, 'pipeline', 'state.json')
DRAFTS = os.path.join(ROOT, 'drafts')

LIMITS = {
    'per_game': int(os.environ.get('MAX_PER_GAME') or 2),
    'per_day': int(os.environ.get('MAX_PER_DAY') or 8),
    'cooldown_min': int(os.environ.get('COOLDOWN_MIN') or 10),
    'fresh_min': int(os.environ.get('FRESH_MIN') or 25),   # live mode ignores calls older than this
    'threshold': float(os.environ.get('THRESHOLD') or detect.DEFAULTS['threshold']),
}


def now():
    return dt.datetime.now(dt.timezone.utc)


def load_state():
    try:
        with open(STATE) as f:
            return json.load(f)
    except FileNotFoundError:
        return {'games': {}, 'espn_plays': [], 'published': [], 'pending_posts': []}


def save_state(s):
    s['espn_plays'] = s['espn_plays'][-2000:]
    s['published'] = s['published'][-500:]
    with open(STATE, 'w') as f:
        json.dump(s, f, indent=2)
        f.write('\n')


def _iso(ts):
    try:
        return dt.datetime.fromisoformat(ts.replace('Z', '+00:00'))
    except (AttributeError, ValueError):
        return None


def scan(leagues, date, replay):
    """Every scored candidate across today's (or a past day's) games."""
    found = []
    for league in leagues:
        board = espn.scoreboard(league, date)
        for ev in board.get('events') or []:
            st = espn.game_state(ev)
            if st == 'pre' or (st != 'in' and not replay):
                continue
            s = espn.summary(league, ev['id'])
            tms = espn.teams(s)
            for c in detect.candidates(espn.plays(s), espn.win_probability(s), tms, {'threshold': LIMITS['threshold']}):
                c.update(league=league, event=str(ev['id']), teams=tms, start=ev.get('date'), name=ev.get('shortName'))
                found.append(c)
    return sorted(found, key=lambda c: -c['score'])


def eligible(c, state, replay):
    if not c['publish'] or str(c['play'].get('id')) in state['espn_plays']:
        return False
    if len(state['games'].get(c['event'], [])) >= LIMITS['per_game']:
        return False
    if not replay:
        wc = _iso(c['play'].get('wallclock'))
        if wc and now() - wc > dt.timedelta(minutes=LIMITS['fresh_min']):
            return False
    return True


def throttled(state):
    today = now().date().isoformat()
    recent = [p for p in state['published'] if p['at'][:10] == today]
    if len(recent) >= LIMITS['per_day']:
        return 'daily cap reached'
    if recent:
        last = _iso(recent[-1]['at'])
        if last and now() - last < dt.timedelta(minutes=LIMITS['cooldown_min']):
            return 'cooling down'
    return None


def describe(c):
    p = c['play']
    return f"{c['score']:6.1f}  {c['name']}  Q{(p.get('period') or {}).get('number')} {(p.get('clock') or {}).get('displayValue')}  swing={c['swing']}  {(p.get('text') or '')[:int(os.environ.get('TEXT_WIDTH', 150))]}"


def backfill_clips(data):
    for pid, play in data['plays'].items():
        auto = play.get('auto')
        if not auto or play.get('clip') or not auto.get('detected'):
            continue
        if now() - _iso(auto['detected']) > dt.timedelta(hours=36):
            continue
        clip = clips.find(play, auto['league'])
        if clip:
            play['clip'] = clip
            print('clip added to', pid, clip)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--league', action='append', help='nfl and/or college-football (default: both)')
    ap.add_argument('--date', help='YYYYMMDD; replays a past day instead of live games')
    ap.add_argument('--dry-run', action='store_true', help='print candidates, change nothing')
    ap.add_argument('--top', type=int, default=15)
    args = ap.parse_args()
    leagues = args.league or ['nfl', 'college-football']
    replay = bool(args.date)

    found = scan(leagues, args.date, replay)
    print(f'{len(found)} disputed calls found, {sum(c["publish"] for c in found)} above threshold {LIMITS["threshold"]}')
    for c in found[:args.top]:
        print(('PUBLISH ' if c['publish'] else '        ') + describe(c))
    if args.dry_run:
        for c in [c for c in found if c['publish']][:int(os.environ.get('SAMPLES', 5))]:
            pid, entry = card.build(c, c['teams'], c['league'], c['event'])
            print('\n--- ' + pid)
            print(json.dumps(entry, indent=2))
            print(json.dumps(social.compose(pid, entry, page.share_url(pid)), indent=2))
        return

    state = load_state()
    data = page.load_plays()
    backfill_clips(data)

    pick = next((c for c in found if eligible(c, state, replay)), None)
    why = throttled(state) if pick else 'nothing new above threshold'
    if pick and not why:
        pid, entry = card.build(pick, pick['teams'], pick['league'], pick['event'])
        if pid in data['plays']:
            pid += '-b'
        entry['auto']['detected'] = now().isoformat(timespec='seconds')
        entry['clip'] = clips.find(entry, pick['league'], pick.get('start')) or ''
        data['plays'][pid] = entry
        data['current'] = pid
        page.write_share_page(pid, entry)
        drafts = social.compose(pid, entry, page.share_url(pid))
        os.makedirs(DRAFTS, exist_ok=True)
        with open(os.path.join(DRAFTS, pid + '.json'), 'w') as f:
            json.dump({'play': pid, 'drafts': drafts, 'results': None}, f, indent=2)
        state['espn_plays'].append(str(pick['play'].get('id')))
        state['games'].setdefault(pick['event'], []).append(pid)
        state['published'].append({'id': pid, 'at': now().isoformat(timespec='seconds')})
        state['pending_posts'].append(pid)
        print('published', pid)
    else:
        print('no new play:', why)
    page.save_plays(data)
    save_state(state)


if __name__ == '__main__':
    main()
