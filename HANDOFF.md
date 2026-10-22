# Handoff: "The Call" one-page vote (Homer)

Status as of 2026-10-22: **live and saving real votes.** Owner: Matt Stead (GitHub `mcstead11-hash`).

**Update 2026-10-22: the bot.** Matt asked for the whole loop to run on its own: find high-impact referee calls during games, put them on the page, and post them. That's now `pipeline/` plus `.github/workflows/watch-games.yml` (see README "The bot"). Detection and page updates run unattended. Social posting is built but stays in draft mode until Matt approves a sample post, creates the accounts/credentials, and sets the repo variable `POSTING_MODE=live`. This supersedes "picking the disputed play still needs a human" below.

## What it is

Homer is Matt's concept for a sports-only social app where each fan's team allegiance is locked until preseason, so every take shows which team the poster backs. "The Call" is the feature Matt is testing first, as a cheap standalone page. Each page shows one disputed play. Visitors:

1. Pick a side (Team A fan, Team B fan, or Neither/neutral).
2. Make the call (two options, e.g. Catch / No catch).
3. Only then see the split by fan base plus a "neutral verdict".

One vote per person per play, and it's final. Results can be copied or shared with "Post on X" and "Share to Reddit" buttons. The point of the test is whether results like "Bears fans 91% no catch, neutral fans 64% catch" get shared. If they do, the full Homer app gets built around them.

## Where everything lives

| Thing | Location |
|---|---|
| Live page | https://mcstead11-hash.github.io/The-Call-Auto/ |
| Repo (public) | https://github.com/mcstead11-hash/The-Call-Auto (branch `main`, GitHub Pages deploys from `main` root) |
| Database | Supabase project `rlyhkxiqchjzrizzfgwu` (https://rlyhkxiqchjzrizzfgwu.supabase.co), free tier |
| Public key | `sb_publishable_W0AhSmfTVWYt_xOibBKMiQ_GgSS802h` (publishable, safe in the browser; already in `config.js`). Never commit the secret key. |
| Original prototype | https://claude.ai/artifact/UxoDuk6Sybk5supVLSTXjz (Claude artifact; only people in Matt's org can open it; superseded by the live page) |
| Full app mock-up (separate, don't change) | https://claude.ai/artifact/6EMx1VAJ3Zq19RxcVQ1YjB |
| Concept doc | https://claude.ai/artifact/CwpdyoXWFi6gjEDvFJv4my |

## Repo files

- `index.html`: the whole page. Static, no build step. Loads `config.js`, `plays.json`, and supabase-js `2.117.0` from jsdelivr. Dark "scoreboard" style: Barlow Condensed + Inter, amber accent `#F5B83D`.
- `plays.json`: the play content. `current` = play shown at the plain URL; any play opens at `?play=<id>`.
- `config.js`: Supabase URL + publishable key. If both are empty, the page runs in "preview mode" (in-memory votes, banner shown).
- `schema.sql`: the database setup (already run on the live project).
- `og.png`: 1200×630 link-preview image (generic "Was it a catch?" card). The `og:`/`twitter:` tags in `index.html` point to the live URL.
- `README.md`: setup and play-posting instructions.

## Database design

- Table `public.votes(play_id, user_id default auth.uid(), team, pick 'a'|'b', created_at)`, primary key `(play_id, user_id)`, so one vote per person per play.
- Each visitor gets a Supabase **anonymous sign-in** (enabled in Auth settings), stored in their browser.
- RLS policies: authenticated users can insert only their own row and select only their own row. No update/delete policies, so votes are final.
- Totals come from `public.tally(p_play)`, a `security definer` function that anon and authenticated can execute. Nobody can read other people's rows.
- Gotcha hit during setup: the project needed explicit `grant select, insert on public.votes to authenticated;` (now in `schema.sql`).
- Known limit: clearing browser data or using a private window gives a fresh anonymous user and another vote. That's acceptable for a test. Before a big push, turn on Supabase CAPTCHA for sign-ins.
- The page shows the underlying error in brackets when voting can't start or a vote doesn't save (added for debugging; fine to keep).

## Posting a new play (the main recurring task)

Add an entry to `plays.json`, set `current` to its id, commit, and push to `main`. Pages redeploys in about a minute. Never reuse a play id, because votes are keyed by it.

```json
"lions-vikings-pi-q4": {
  "sample": false,
  "meta": "NFL · Lions 24, Vikings 21 · Q4 0:48 · 2nd & 10 at MIN 38",
  "question": "Was it pass interference?",
  "desc": "Deep shot down the sideline, contact before the ball arrives. No flag.",
  "clip": "https://www.youtube.com/embed/VIDEO_ID",
  "teams": [
    { "key": "DET", "name": "Lions", "color": "#0076B6" },
    { "key": "MIN", "name": "Vikings", "color": "#4F2683" }
  ],
  "options": { "a": "Flag", "b": "No flag" },
  "favors": { "a": "DET", "b": "MIN" },
  "open": true
}
```

- `teams[].key`: 1–4 capital letters (the database enforces this); `N` is reserved for neutral.
- `favors`: which team each answer helps; drives the "you called it against your own team" line.
- `clip`: optional; an embeddable URL (iframe) or a direct `.mp4`/`.webm`.
- `open: false` closes voting and shows the final split to everyone.
- The current sample play (`gb-chi-sideline-catch`, Packers–Bears) is **made up** and labeled "Sample play". Replace it with a real play before sharing publicly.
- `og.png` and the `og:title` are generic ("Was it a catch?"). Per-play preview images would need per-play HTML pages or an image service; not built.

## Decisions made with Matt

- Keep the full Homer mock-up untouched; The Call is a separate minimal test.
- Host publicly (GitHub Pages + Supabase) rather than as a Claude artifact, because artifacts with stored data only open for people in Matt's org.
- **X:** originally manual because write access needed a ~$200/month tier. X moved to pay-per-use in 2026 (about $0.20 per post with a link, no monthly plan), so the bot can post once Matt adds credentials and approves.
- **Reddit:** big subs (r/nfl, r/CFB, team subs) ban self-promotion and bot posting; an automated account there would get banned. The bot only posts to a subreddit Matt runs (`REDDIT_SUBREDDIT`). Reddit also requires approval for new API apps.
- **Facebook:** posts only to a Facebook Page Matt admins (Graph API Page token). Groups can't be posted to by API.
- **Video:** never re-host game footage (copyright). Link to the ESPN game page; embed official league YouTube highlights when a `YOUTUBE_API_KEY` is set.
- Picking the disputed play still needs a human; a live data feed can't reliably detect "controversial".

## Open ideas / next steps

1. Post a real disputed play during the next game (Matt sends teams, situation, and a clip link).
2. Draft X posts and Reddit-appropriate wording for each play.
3. Optional: per-play preview images, Supabase CAPTCHA, a simple results archive page of past plays.
4. If shares take off: revisit X API automation, then the full Homer app.

## Bot notes for an agent

- ESPN's CDN (Akamai) returns 403 to unknown User-Agents; `pipeline/espn.py` sends a Mozilla-style one. The Claude cloud container can't reach ESPN at all; test through Actions (Run workflow with a past date and "Only print").
- ESPN `winprobability[i]` is the home win probability *after* play i (checked against touchdowns).
- Play-by-play team codes differ from team abbreviations (HST=HOU, BLT=BAL, ARZ=ARI, LA=LAR, WAS=WSH; college: KAN, WISC, RUT...). `detect.team_for` handles these.
- State (which ESPN plays were used, daily counts, queued posts) is `pipeline/state.json`, committed by the workflow.

## Environment notes for an agent

- The cloud container used so far could push to GitHub but was **blocked from reaching `*.supabase.co` and `*.github.io`**, so live testing had to be done by Matt in his browser. GitHub's API path for Pages settings was also blocked; Matt turned Pages on himself. GitHub Actions run history (the `pages build and deployment` workflow) is a reliable way to confirm a deploy.
- The schema was tested locally against Postgres 16 with a stub `auth` schema: duplicate vote rejected, update/delete no-ops, forged `user_id` blocked by RLS, anon sees only totals.
