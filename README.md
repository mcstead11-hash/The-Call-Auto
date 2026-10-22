# Homer: The Call (public test page)

A one-page vote on a single disputed play. Pick your side, make the call, then see the split by fan base and the neutral verdict. One final vote per person per play.

## Files

| File | What it is |
|---|---|
| `index.html` | The page. Static, no build step. |
| `plays.json` | The plays. `current` is the one shown at the plain link; any play opens at `?play=<id>`. |
| `config.js` | Supabase address and public key. Empty = preview mode (votes not saved). |
| `schema.sql` | Database setup for Supabase. Run once. |
| `og.png` | Link preview image for X, Reddit and group chats. |

## One-time setup (about 10 minutes)

1. **Supabase** (free tier is plenty): create a project at supabase.com.
   - SQL Editor: paste `schema.sql` and run it.
   - Authentication > Sign In / Providers: turn on **Allow anonymous sign-ins**.
   - Project Settings > API: copy the Project URL (Connect button) and the publishable key (`sb_publishable_...`, or the legacy `anon` key) into `config.js`. Never put the secret key in this repo.
2. **GitHub Pages**: push these files to the public repo `mcstead11-hash/The-Call-Auto`, then Settings > Pages > Deploy from branch `main`, folder `/`.
   The page goes live at `https://mcstead11-hash.github.io/The-Call-Auto/`. If the repo or address differs, update the `og:` and `twitter:` tags in `index.html`.

## Posting a new play

Add an entry to `plays.json`, set `current` to its id, and push. Fields:

- `meta`: league, score, clock, down and distance.
- `question`, `desc`: the call in question and what happened.
- `clip`: optional. An embeddable video URL (for example a YouTube embed link) or a direct `.mp4`.
- `teams`: the two teams, with a short key (1 to 4 capital letters), name and color.
- `options`: the two answers, `a` and `b`.
- `favors`: which team each answer helps, so the page can spot fans voting against their own team.
- `open`: `false` closes voting and shows the final split to everyone.
- `sample`: `true` labels it as a sample play.

Votes are stored per play id, so never reuse an id.

## How votes are protected

- Each visitor gets an anonymous Supabase sign-in, stored in their browser.
- The database allows one vote per person per play and has no edit or delete rule, so votes are final.
- Visitors can read only their own vote; everyone else sees totals through the `tally` function.
- Limit: someone who clears their browser data or uses a private window can vote again. That is fine for a test. Before a big launch, turn on Supabase's CAPTCHA option for sign-ins.

## The bot (automatic plays)

`.github/workflows/watch-games.yml` runs every 5 minutes (GitHub may delay scheduled runs by a few minutes at busy times). During live NFL and FBS games it:

1. Reads ESPN's public play-by-play and win-probability feed (`pipeline/espn.py`).
2. Scores every accepted judgment-call penalty and replay review by how much it moved win probability, weighted by how disputable that kind of call is, with extra weight late in close games and for touchdowns or turnovers a flag erased (`pipeline/detect.py`). Procedural flags (false start, delay of game, offside) are ignored. A missed call with no flag leaves no trace in the feed, so the bot can't find those.
3. Builds the play card with a question that fits the call ("Was it pass interference?", "Was it a catch?", "Was it targeting?"), the teams and colors, the score and situation, and which answer helps which team (`pipeline/card.py`).
4. Adds it to `plays.json`, makes it `current`, and writes a share page at `p/<play-id>/` so links show that play's question in previews (`pipeline/page.py`).
5. Writes post drafts for X, Reddit and Facebook to `drafts/<play-id>.json`, and posts them only when posting is switched on (`pipeline/social.py`, `pipeline/post.py`).

Limits so it doesn't flood the page or feeds: at most 2 plays per game, 8 per day, 10 minutes apart, and only calls from the last 25 minutes. Change them with repository variables `MAX_PER_GAME`, `MAX_PER_DAY`, `THRESHOLD` (default 15; higher means pickier).

**Video:** game footage belongs to the leagues and broadcasters, so the bot never downloads or re-hosts clips. Each play links to its ESPN game page. With a `YOUTUBE_API_KEY` secret, it also embeds the game's official highlight video from the league's YouTube channel when one is up (usually after the game, and the whole highlight package, not just the one call).

**Try it on a past day:** Actions > Watch games > Run workflow, enter a date like `20261018`, keep "Only print" ticked, and read the log.

**Pause it:** Actions > Watch games > ⋯ > Disable workflow.

### Turning on posting

Posting stays in draft mode until the repository variable `POSTING_MODE` is `live`. Each platform also needs its own secrets (Settings > Secrets and variables > Actions):

| Platform | Secrets | Notes |
|---|---|---|
| X | `X_API_KEY`, `X_API_SECRET`, `X_ACCESS_TOKEN`, `X_ACCESS_SECRET` | Pay-per-use API credits; posts with a link cost about $0.20 each. App needs Read and Write. |
| Reddit | `REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET`, `REDDIT_USERNAME`, `REDDIT_PASSWORD`, variable `REDDIT_SUBREDDIT` | Script app. Only point it at a subreddit you run; r/nfl and r/CFB ban bot and self-promo posts. |
| Facebook | `FB_PAGE_ID`, `FB_PAGE_TOKEN` | A Facebook Page you admin, with a long-lived Page token that has `pages_manage_posts`. |

A platform with missing secrets is skipped; the others still post. Results are written back into the play's `drafts/` file.
