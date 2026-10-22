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
