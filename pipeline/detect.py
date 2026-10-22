"""Find referee calls with an outsized effect on a game and turn each into a play card.

A play is a candidate when it carries an accepted judgment-call penalty or a replay
review. Its score is the win-probability swing on that play, weighted by how
disputable that kind of call is, plus bonuses for late, close games, reversals and
erased touchdowns or turnovers. No-calls (a flag that should have been thrown) leave
no trace in the play-by-play, so they can't be found this way.
"""
import re

# How disputable each penalty is. 0 means a procedural flag nobody argues about.
PENALTY_WEIGHT = [
    (r'pass interference', 1.0, 'pi'),
    (r'roughing the passer', 1.0, 'rtp'),
    (r'targeting', 1.0, 'targeting'),
    (r'roughing the kicker|running into the kicker', 0.8, 'kicker'),
    (r'unnecessary roughness', 0.8, 'ur'),
    (r'unsportsmanlike|taunting', 0.7, 'unsportsmanlike'),
    (r'holding', 0.7, 'holding'),
    (r'illegal contact', 0.6, 'contact'),
    (r'face ?mask', 0.6, 'facemask'),
    (r'intentional grounding', 0.6, 'grounding'),
    (r'illegal block|block in the back|chop block|clipping|illegal use of hands|horse collar|lowering the head|leverage|leaping', 0.6, 'penalty'),
    (r'ineligible', 0.5, 'penalty'),
    (r'false start|delay of game|offside|encroachment|neutral zone|too many|illegal formation|illegal shift|illegal motion|illegal substitution|illegal snap|defensive delay', 0.0, None),
]
OFFENSIVE_PENALTY = re.compile(r'offensive|false start|intentional grounding|illegal block|ineligible|chop block|illegal formation', re.I)
PENALTY_RE = re.compile(r'PENALTY on ([A-Za-z]{1,5})-[^,]*,\s*([^,(]+?)\s*(?:\(|,)\s*(?:(\d+) yards?)?', re.I)
PENALTY_TEAM_ONLY_RE = re.compile(r'PENALTY on ([A-Za-z]{1,5}),\s*([^,(]+?)\s*(?:\(|,)\s*(?:(\d+) yards?)?', re.I)
REVIEW_RE = re.compile(r'replay|challenge|review|reversed|overturned|upheld|ruling on the field (stands|is confirmed)', re.I)

DEFAULTS = {
    'threshold': 18.0,      # minimum score to publish
    'late_bonus': 8.0,      # 4th quarter or OT, one-score game
    'clutch_bonus': 5.0,    # final two minutes of a half
    'reversal_bonus': 10.0,
    'erased_bonus': 12.0,   # penalty wiped out a touchdown or turnover
}


def _clock_seconds(play):
    v = (play.get('clock') or {}).get('displayValue') or '15:00'
    try:
        m, s = v.split(':')
        return int(m) * 60 + int(s)
    except ValueError:
        return 900


def _penalty(play, teams_by_abbr):
    text = play.get('text') or ''
    if 'PENALTY' not in text.upper():
        return None
    m = PENALTY_RE.search(text) or PENALTY_TEAM_ONLY_RE.search(text)
    if not m:
        return None
    tail = text[m.end():m.end() + 40].lower()
    if 'declined' in text[m.start():m.end() + 20].lower() or 'offsetting' in text.lower():
        return None
    name = m.group(2).strip().rstrip('.')
    weight, kind = 0.5, 'penalty'
    for pat, w, k in PENALTY_WEIGHT:
        if re.search(pat, name, re.I):
            weight, kind = w, k
            break
    return {
        'abbr': m.group(1).upper(),
        'team': teams_by_abbr.get(m.group(1).upper()),
        'name': name,
        'yards': int(m.group(3)) if m.group(3) else None,
        'weight': weight,
        'kind': kind,
        'no_play': 'no play' in text.lower() or 'no play' in tail,
    }


def _review(play):
    text = play.get('text') or ''
    if not REVIEW_RE.search(text):
        return None
    t = text.lower()
    if 'reversed' in t or 'overturned' in t:
        outcome = 'reversed'
    elif 'upheld' in t or 'stands' in t or 'confirmed' in t:
        outcome = 'upheld'
    else:
        return None
    if re.search(r'complet|incomplete|catch|reception', t):
        subject = 'catch'
    elif re.search(r'intercept', t):
        subject = 'interception'
    elif re.search(r'fumble|recover', t):
        subject = 'fumble'
    elif re.search(r'touchdown|goal line|broke the plane|end zone', t):
        subject = 'touchdown'
    elif re.search(r'first down|line to gain|spot', t):
        subject = 'spot'
    else:
        subject = 'other'
    return {'outcome': outcome, 'subject': subject, 'weight': 1.0 if outcome == 'reversed' else 0.6}


def candidates(plays, wp, teams, cfg=None):
    """Score every play that holds a disputed call. Returns a list sorted best first."""
    cfg = {**DEFAULTS, **(cfg or {})}
    by_abbr = {t['abbr'].upper(): t for t in teams.values()}
    home = next((t for t in teams.values() if t['side'] == 'home'), None)
    out = []
    prev_wp, prev = None, None
    for p in plays:
        pid = str(p.get('id'))
        cur_wp = wp.get(pid, prev_wp)
        pen, rev = _penalty(p, by_abbr), _review(p)
        if (pen and pen['weight'] > 0) or rev:
            swing = abs(cur_wp - prev_wp) * 100 if (cur_wp is not None and prev_wp is not None) else None
            weight = max(pen['weight'] if pen else 0, rev['weight'] if rev else 0)
            score = (swing if swing is not None else 10.0) * weight
            q, secs = (p.get('period') or {}).get('number') or 1, _clock_seconds(p)
            before = prev or p
            margin = abs(int(before.get('homeScore') or 0) - int(before.get('awayScore') or 0))
            if q >= 4 and margin <= 8:
                score += cfg['late_bonus']
            if q in (2, 4) or q >= 5:
                if secs <= 120:
                    score += cfg['clutch_bonus']
            if rev and rev['outcome'] == 'reversed':
                score += cfg['reversal_bonus']
            text = (p.get('text') or '').lower()
            if pen and pen['no_play'] and re.search(r'touchdown|intercepted|fumble', text.split('penalty')[0]):
                score += cfg['erased_bonus']
            toward = None
            if swing is not None and home and swing >= 1:
                toward = home['id'] if cur_wp > prev_wp else next(t['id'] for t in teams.values() if t['id'] != home['id'])
            out.append({
                'play': p, 'prev': prev, 'penalty': pen, 'review': rev,
                'swing': round(swing, 1) if swing is not None else None, 'toward': toward,
                'score': round(score, 1), 'publish': score >= cfg['threshold'],
            })
        if cur_wp is not None:
            prev_wp = cur_wp
        prev = p
    return sorted(out, key=lambda c: -c['score'])
