"""Write a detected play into plays.json and give it its own share page with link-preview tags."""
import html
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = os.environ.get('SITE_URL', 'https://mcstead11-hash.github.io/The-Call-Auto/').rstrip('/') + '/'


def load_plays():
    with open(os.path.join(ROOT, 'plays.json')) as f:
        return json.load(f)


def save_plays(data):
    with open(os.path.join(ROOT, 'plays.json'), 'w') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write('\n')


def share_url(play_id):
    return f'{SITE}p/{play_id}/'


def write_share_page(play_id, play):
    """Static page at p/<id>/ so X, Reddit and Facebook show this play's question in the preview, then forward to the vote."""
    teams = ' vs '.join(t['name'] for t in play['teams'])
    title = html.escape(f"The Call: {play['question']} ({teams})")
    desc = html.escape(play['desc'][:200])
    target = html.escape(f'{SITE}?play={play_id}')
    image = html.escape(f'{SITE}p/{play_id}/og.png' if play.get('og_image') else f'{SITE}og.png')
    page = f'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>
<meta name="description" content="{desc}">
<meta property="og:type" content="website">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{desc}">
<meta property="og:image" content="{image}">
<meta property="og:url" content="{html.escape(share_url(play_id))}">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{title}">
<meta name="twitter:description" content="{desc}">
<meta name="twitter:image" content="{image}">
<link rel="canonical" href="{target}">
<meta http-equiv="refresh" content="0; url={target}">
<style>body{{background:#0D111C;color:#EDF0F6;font-family:system-ui,sans-serif;padding:24px}}a{{color:#F5B83D}}</style>
</head>
<body><p><a href="{target}">Make the call</a></p></body>
</html>
'''
    d = os.path.join(ROOT, 'p', play_id)
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, 'index.html'), 'w') as f:
        f.write(page)
