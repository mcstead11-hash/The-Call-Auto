"""Write the posts for a play and, only when POSTING_MODE=live, publish them.

Each platform posts only when its credentials are set as repository secrets:
  X:        X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN, X_ACCESS_SECRET (pay-per-use API credits)
  Reddit:   REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, REDDIT_USERNAME, REDDIT_PASSWORD, REDDIT_SUBREDDIT
  Facebook: FB_PAGE_ID, FB_PAGE_TOKEN (a Page access token with pages_manage_posts)
Anything else (no secrets, or POSTING_MODE not 'live') only writes drafts.
"""
import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import time
import urllib.parse
import urllib.request

UA = 'the-call-bot/1.0 (by /u/{})'


def _tag(name):
    return '#' + re.sub(r'[^A-Za-z0-9]', '', name)


def compose(play_id, play, url):
    teams = [t['name'] for t in play['teams']]
    league = play['meta'].split(' · ')[0]
    situation = ', '.join(play['meta'].split(' · ')[1:3])
    impact = ''
    if play.get('impact'):
        who = next(t['name'] for t in play['teams'] if t['key'] == play['impact']['toward'])
        impact = f" It swung win probability {play['impact']['swing']}% toward the {who}."
    x = f"{play['question']} {situation}.{impact}\n\nPick your side, make the call, see how each fan base voted.\n\n{_tag(league)} {_tag(teams[0])} {_tag(teams[1])}\n{url}"
    if len(x) > 280 + len(url) - 23:  # X counts any link as 23 characters
        x = f"{play['question']} {situation}.\n\nMake the call: {url}"
    reddit_title = f"{play['question']} {situation} (vote by fan base)"
    reddit_body = f"{play['desc']}\n\nPick which team you root for (or neutral), make the call, and see the split by fan base: {url}"
    fb = f"{play['question']}\n{situation}.{impact}\n\n{play['desc']}\n\nPick your side and make the call: {url}"
    return {'x': x, 'reddit': {'title': reddit_title[:300], 'body': reddit_body, 'url': url}, 'facebook': fb, 'url': url}


# --- X (OAuth 1.0a user context) -------------------------------------------------

def _oauth1_header(method, url, ck, cs, tk, ts):
    params = {
        'oauth_consumer_key': ck, 'oauth_nonce': secrets.token_hex(16),
        'oauth_signature_method': 'HMAC-SHA1', 'oauth_timestamp': str(int(time.time())),
        'oauth_token': tk, 'oauth_version': '1.0',
    }
    enc = lambda s: urllib.parse.quote(s, safe='~')
    base = '&'.join([method, enc(url), enc('&'.join(f'{enc(k)}={enc(v)}' for k, v in sorted(params.items())))])
    key = f'{enc(cs)}&{enc(ts)}'
    params['oauth_signature'] = base64.b64encode(hmac.new(key.encode(), base.encode(), hashlib.sha1).digest()).decode()
    return 'OAuth ' + ', '.join(f'{enc(k)}="{enc(v)}"' for k, v in sorted(params.items()))


def post_x(text):
    env = os.environ
    url = 'https://api.x.com/2/tweets'
    auth = _oauth1_header('POST', url, env['X_API_KEY'], env['X_API_SECRET'], env['X_ACCESS_TOKEN'], env['X_ACCESS_SECRET'])
    req = urllib.request.Request(url, data=json.dumps({'text': text}).encode(), method='POST',
                                 headers={'Authorization': auth, 'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=30) as r:
        tid = json.load(r)['data']['id']
    return f'https://x.com/i/status/{tid}'


# --- Reddit (script app, posts only to the subreddit you name) ------------------

def post_reddit(post):
    env = os.environ
    ua = UA.format(env['REDDIT_USERNAME'])
    basic = base64.b64encode(f"{env['REDDIT_CLIENT_ID']}:{env['REDDIT_CLIENT_SECRET']}".encode()).decode()
    body = urllib.parse.urlencode({'grant_type': 'password', 'username': env['REDDIT_USERNAME'], 'password': env['REDDIT_PASSWORD']}).encode()
    req = urllib.request.Request('https://www.reddit.com/api/v1/access_token', data=body,
                                 headers={'Authorization': 'Basic ' + basic, 'User-Agent': ua})
    with urllib.request.urlopen(req, timeout=30) as r:
        token = json.load(r)['access_token']
    form = urllib.parse.urlencode({'sr': env['REDDIT_SUBREDDIT'], 'kind': 'link', 'title': post['title'],
                                   'url': post['url'], 'resubmit': 'true', 'api_type': 'json'}).encode()
    req = urllib.request.Request('https://oauth.reddit.com/api/submit', data=form,
                                 headers={'Authorization': 'Bearer ' + token, 'User-Agent': ua})
    with urllib.request.urlopen(req, timeout=30) as r:
        res = json.load(r)['json']
    if res.get('errors'):
        raise RuntimeError(res['errors'])
    return res['data']['url']


# --- Facebook Page ----------------------------------------------------------------

def post_facebook(text, link):
    env = os.environ
    form = urllib.parse.urlencode({'message': text, 'link': link, 'access_token': env['FB_PAGE_TOKEN']}).encode()
    req = urllib.request.Request(f"https://graph.facebook.com/v21.0/{env['FB_PAGE_ID']}/feed", data=form)
    with urllib.request.urlopen(req, timeout=30) as r:
        return 'https://www.facebook.com/' + json.load(r)['id']


PLATFORMS = {
    'x': (('X_API_KEY', 'X_API_SECRET', 'X_ACCESS_TOKEN', 'X_ACCESS_SECRET'), lambda d: post_x(d['x'])),
    'reddit': (('REDDIT_CLIENT_ID', 'REDDIT_CLIENT_SECRET', 'REDDIT_USERNAME', 'REDDIT_PASSWORD', 'REDDIT_SUBREDDIT'), lambda d: post_reddit(d['reddit'])),
    'facebook': (('FB_PAGE_ID', 'FB_PAGE_TOKEN'), lambda d: post_facebook(d['facebook'], d['url'])),
}


def publish(drafts):
    """Post to every platform that is switched on. Returns {platform: url or error}."""
    live = os.environ.get('POSTING_MODE') == 'live'
    results = {}
    for name, (keys, send) in PLATFORMS.items():
        if not live or not all(os.environ.get(k) for k in keys):
            results[name] = 'draft only'
            continue
        try:
            results[name] = send(drafts)
        except Exception as e:  # one platform failing must not stop the others
            detail = e.read().decode()[:300] if hasattr(e, 'read') else str(e)
            results[name] = f'error: {detail}'
    return results
