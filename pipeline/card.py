"""Turn a detected call into a plays.json entry shaped to the kind of call."""
import re

from .detect import OFFENSIVE_PENALTY

ORD = {1: '1st', 2: '2nd', 3: '3rd', 4: '4th'}

# question, option a, option b, which side option a helps ('beneficiary' of the call as made, 'offense', 'defense')
PENALTY_Q = {
    'pi': ('Was it pass interference?', 'Flag', 'No flag'),
    'rtp': ('Was it roughing the passer?', 'Flag', 'No flag'),
    'targeting': ('Was it targeting?', 'Targeting', 'Clean hit'),
    'kicker': ('Did he rough the kicker?', 'Flag', 'No flag'),
    'ur': ('Was it unnecessary roughness?', 'Flag', 'No flag'),
    'unsportsmanlike': ('Did that deserve a flag?', 'Flag', 'No flag'),
    'holding': ('Was it holding?', 'Holding', 'Clean'),
    'contact': ('Was it illegal contact?', 'Flag', 'No flag'),
    'facemask': ('Was it a face mask?', 'Flag', 'No flag'),
    'grounding': ('Was it intentional grounding?', 'Grounding', 'No flag'),
}
REVIEW_Q = {
    'catch': ('Was it a catch?', 'Catch', 'No catch', 'offense'),
    'interception': ('Was it an interception?', 'Pick', 'No pick', 'defense'),
    'fumble': ('Was it a fumble?', 'Fumble', 'Down', 'defense'),
    'touchdown': ('Was it a touchdown?', 'Touchdown', 'Short', 'offense'),
    'spot': ('Did he get the first down?', 'First down', 'Short', 'offense'),
}


def _key(abbr, taken):
    k = re.sub(r'[^A-Z]', '', abbr.upper())[:4] or 'T'
    if k == 'N':
        k = 'NN'
    while k in taken:
        k = (k[:3] + 'X')
    return k


def _slug(s):
    return re.sub(r'[^a-z0-9]+', '-', s.lower()).strip('-')


def _sentence(text):
    """The action part of ESPN's play text, without formation and penalty legalese."""
    t = re.sub(r'\(\d+:\d+( - \d\w+)?\)\s*', '', text or '')
    t = re.sub(r'\((Shotgun|No Huddle[^)]*|Pistol)\)\s*', '', t, flags=re.I)
    t = re.sub(r'^\s*(No Huddle-?)?(Shotgun|Pistol)?\s*', '', t, flags=re.I)
    t = re.sub(r'#\d+ ', '', t)
    t = re.sub(r'\*\* Injury Update:[^.]*\.\s*|\S+ reported in as eligible\.\s*', '', t)
    t = re.split(r'PENALTY|The Replay Official|The previous play|\bReplay\b|challenged|NULLIFIED', t, flags=re.I)[0]
    t = re.sub(r'\s+', ' ', t).strip(' .;,')
    return t[:150].rsplit(' ', 1)[0] + '…' if len(t) > 150 else t


def build(c, teams, league, event_id):
    p, prev, pen, rev = c['play'], c['prev'] or c['play'], c['penalty'], c['review']
    start = p.get('start') or {}
    off_id = str((start.get('team') or {}).get('id') or '')
    away = next(t for t in teams.values() if t['side'] == 'away')
    home = next(t for t in teams.values() if t['side'] == 'home')
    offense = teams.get(off_id)
    defense = (home if offense is away else away) if offense else None

    taken = set()
    keys = {}
    for t in (away, home):
        keys[t['id']] = _key(t['abbr'], taken)
        taken.add(keys[t['id']])

    if pen:
        penalized = pen['team']
        if not penalized and offense:
            penalized = offense if OFFENSIVE_PENALTY.search(pen['name']) else defense
        q, a, b = PENALTY_Q.get(pen['kind'], (f"Was it {pen['name'].lower()}?", 'Flag', 'No flag'))
        helped = (home if penalized is away else away) if penalized else None
        favors = {'a': keys[helped['id']], 'b': keys[penalized['id']]} if penalized else None
        kind = pen['kind']
    else:
        q, a, b, side = REVIEW_Q.get(rev['subject'], ('Did the refs get it right?', 'Right call', 'Wrong call', None))
        if side and offense:
            helps_a = offense if side == 'offense' else defense
            other = defense if side == 'offense' else offense
            favors = {'a': keys[helps_a['id']], 'b': keys[other['id']]}
        else:
            favors = None
        kind = 'review-' + rev['subject']

    period = (p.get('period') or {}).get('number') or 1
    qtxt = f'Q{period}' if period <= 4 else ('OT' if period == 5 else f'{period - 4}OT')
    clock = (p.get('clock') or {}).get('displayValue') or ''
    hs, as_ = int(prev.get('homeScore') or 0), int(prev.get('awayScore') or 0)
    lead, trail = ((home, hs), (away, as_)) if hs >= as_ else ((away, as_), (home, hs))
    situation = start.get('downDistanceText') or ''
    meta = ' · '.join(x for x in [
        {'nfl': 'NFL', 'college-football': 'CFB'}.get(league, league.upper()),
        f"{lead[0]['name']} {lead[1]}, {trail[0]['name']} {trail[1]}",
        f'{qtxt} {clock}'.strip(),
        situation,
    ] if x)

    action = _sentence(p.get('text'))
    if pen:
        who = penalized['name'] if penalized else pen['abbr']
        yds = f", {pen['yards']} yards" if pen['yards'] else ''
        call = f"Flag on the {who}: {pen['name'].lower()}{yds}."
        if rev:
            call += ' Overturned on replay.' if rev['outcome'] == 'reversed' else ' Upheld on replay.'
        elif pen['no_play'] and action:
            call += ' The play came back.'
    else:
        call = 'Overturned on replay.' if rev['outcome'] == 'reversed' else 'Ruling stood after review.'
    if rev and not pen and action:
        action = 'Called on the field: ' + action
    desc = (action + '. ' if action else '') + call

    impact = None
    if c['swing'] is not None and c['swing'] >= 1 and c['toward']:
        impact = {'swing': round(c['swing']), 'toward': keys[c['toward']]}

    play_id = '-'.join([_slug(away['abbr']), _slug(home['abbr']), _slug(kind), qtxt.lower(),
                        clock.replace(':', ''), str(event_id)[-6:]])[:80]
    entry = {
        'sample': False,
        'meta': meta,
        'question': q,
        'desc': desc,
        'clip': '',
        'watch': f"https://www.espn.com/{'nfl' if league == 'nfl' else 'college-football'}/game/_/gameId/{event_id}",
        'teams': [{'key': keys[t['id']], 'name': t['name'], 'color': t['color']} for t in (away, home)],
        'options': {'a': a, 'b': b},
        'open': True,
        'auto': {'league': league, 'event': str(event_id), 'espn_play': str(p.get('id')),
                 'score': c['score'], 'detected': None},
    }
    if favors:
        entry['favors'] = favors
    if impact:
        entry['impact'] = impact
    return play_id, entry
