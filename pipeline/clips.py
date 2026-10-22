"""Find an embeddable official video for a game.

Game footage belongs to the leagues and broadcasters, so the bot never downloads or
re-hosts it. It only embeds videos the league itself published on YouTube with
embedding allowed. Those are usually game-highlight packages posted after the game,
not a clip of the single call, so the page also links to the ESPN game page.
Needs YOUTUBE_API_KEY; without it the clip stays empty and the watch link is used.
"""
import json
import os
import urllib.parse
import urllib.request

OFFICIAL_CHANNELS = {
    'nfl': ['UCDVYQ4Zhbm3S2dlz7P1GBDg'],          # NFL
    'college-football': ['UCiWLfSweyRNmLpgEHekhoAg'],  # ESPN
}


def find(play, league, game_start_iso=None):
    key = os.environ.get('YOUTUBE_API_KEY')
    if not key:
        return None
    names = ' '.join(t['name'] for t in play['teams'])
    for channel in OFFICIAL_CHANNELS.get(league, []):
        q = {
            'part': 'snippet', 'type': 'video', 'videoEmbeddable': 'true', 'maxResults': '5',
            'channelId': channel, 'q': names + ' highlights', 'order': 'date', 'key': key,
        }
        if game_start_iso:
            q['publishedAfter'] = game_start_iso
        url = 'https://www.googleapis.com/youtube/v3/search?' + urllib.parse.urlencode(q)
        try:
            with urllib.request.urlopen(url, timeout=20) as r:
                items = json.load(r).get('items') or []
        except Exception as e:  # a missing clip never blocks a play
            print('clip search failed:', e)
            continue
        for it in items:
            title = it['snippet']['title'].lower()
            if all(t['name'].lower() in title for t in play['teams']):
                return 'https://www.youtube.com/embed/' + it['id']['videoId']
    return None
