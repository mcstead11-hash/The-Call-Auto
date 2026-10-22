"""Thin client for ESPN's public scoreboard and game summary JSON (no key needed)."""
import json
import urllib.request

BASE = 'https://site.api.espn.com/apis/site/v2/sports/football/{league}/{path}'
LEAGUES = {'nfl': 'NFL', 'college-football': 'CFB'}


def _get(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (compatible; the-call/1.0)', 'Accept': 'application/json'})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.load(r)


def scoreboard(league, date=None):
    q = '?limit=300'
    if league == 'college-football':
        q += '&groups=80'  # FBS only
    if date:
        q += '&dates=' + date
    return _get(BASE.format(league=league, path='scoreboard' + q))


def summary(league, event_id):
    return _get(BASE.format(league=league, path='summary?event=' + str(event_id)))


def game_state(event):
    return event.get('status', {}).get('type', {}).get('state')  # pre / in / post


def teams(summary_json):
    """Both sides keyed by ESPN team id: abbreviation, short name, color, home/away."""
    comp = summary_json['header']['competitions'][0]
    out = {}
    for c in comp['competitors']:
        t = c['team']
        out[str(t['id'])] = {
            'id': str(t['id']),
            'abbr': t.get('abbreviation', ''),
            'name': t.get('shortDisplayName') or t.get('name') or t.get('displayName'),
            'location': t.get('location') or '',
            'color': '#' + (t.get('color') or '8A93A6').lstrip('#'),
            'alt': '#' + (t.get('alternateColor') or 'EDF0F6').lstrip('#'),
            'side': c.get('homeAway'),
        }
    return out


def plays(summary_json):
    """Every play in game order, from completed drives plus the live drive."""
    drives = summary_json.get('drives') or {}
    seq = []
    for d in drives.get('previous') or []:
        seq.extend(d.get('plays') or [])
    cur = drives.get('current')
    if cur:
        seq.extend(cur.get('plays') or [])
    seen, out = set(), []
    for p in seq:
        pid = str(p.get('id'))
        if pid not in seen:
            seen.add(pid)
            out.append(p)
    out.sort(key=lambda p: int(p.get('sequenceNumber') or 0))
    return out


def win_probability(summary_json):
    """playId -> home win probability (0..1) after that play."""
    return {str(w['playId']): float(w['homeWinPercentage'])
            for w in summary_json.get('winprobability') or [] if 'playId' in w}
