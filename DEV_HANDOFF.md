# Dev Handoff — MOX Collective World Cup Bracket

Hi! This is a small, self-contained web app: a World Cup bracket pool for the MOX
Collective crew. This note is the quick orientation; `README.md` has the full
detail.

## What it is
- Everyone builds a knockout bracket (Round of 32 → Champion), one matchup at a time.
- A leaderboard scores predictions as real results come in (round weights: R32=1, R16=2, QF=4, SF=8, Final/Champion=16).
- A shared "Bracket" view shows the live tournament tree.
- An admin panel (password-gated) sets results manually or syncs them from a free football API.

## Stack (deliberately minimal)
- **Backend:** one Python file, `api/index.py`, using only the standard library
  (plus `psycopg2` on Vercel). No framework.
- **Frontend:** vanilla HTML/CSS/JS in `public/` (no build step). MOX-branded, dark, Gyst font embedded.
- **Storage:** auto-selected.
  - No `POSTGRES_URL` → **SQLite** file (`bracket.db`) for local dev. Zero setup.
  - `POSTGRES_URL` present → **Postgres** (this is what Vercel uses).
  - Tables are created automatically on first run; the bracket seed is `api/tournament.json`.

## Run locally
```bash
python api/index.py        # needs Python 3.8+ ; no pip install required for local/SQLite
```
Open http://localhost:8000  (Windows: double-click `start.bat`).

Env vars (all optional): `PORT` (8000), `ADMIN_PASSWORD` (default `mox`),
`FOOTBALL_DATA_API_KEY` (free key from football-data.org enables live result sync).

## Deploy to Vercel (the intended host)
1. Push this folder to a Git repo and **Import** it into Vercel (no build settings needed —
   `vercel.json` + `requirements.txt` are included).
2. **Storage → Create Database → Postgres**, connect it to the project. Vercel injects
   `POSTGRES_URL` automatically — that's the only thing the app needs to switch to Postgres.
3. Add env vars: `ADMIN_PASSWORD` (and optionally `FOOTBALL_DATA_API_KEY`).
4. Deploy. Brackets persist in Postgres across redeploys/cold starts.

`vercel.json` rewrites every `/api/*` request to the single function `api/index.py`;
the `public/` folder is served as static by the platform.

## Heads-up / things to know
- **The Postgres path hasn't been exercised against a live Postgres yet** — it was
  developed and fully tested on the SQLite backend (identical code path; the only
  difference is the driver and `?`→`%s` placeholder translation, which is handled in
  one helper). The SQL is standard and parameterized. If anything trips on first
  deploy it'll be small (connection/SSL or a placeholder edge case) — easy fix.
- **No auth on submitting/viewing** — anyone with the URL can submit a bracket. Fine
  for a private crew link; add a shared gate if you want it locked down.
- **No live auto-refresh** — the Bracket/Leaderboard update when you load the page.
  Polling every ~60s would be a small add if desired.
- **Teams & bracket** live in `api/tournament.json` (real 2026 R32 matchups + feeder
  paths). Edit there if matchups change; re-seed by clearing the `tournament` row in
  the DB (Admin → "Clear all results" re-saves the structure as-is).
- No images/photos are stored — players are identified by name + initials avatar.

## Layout
```
api/index.py          backend (serverless handler + local server)
api/tournament.json   bracket seed (teams + structure)
public/               frontend (index.html, app.js, styles.css, fonts/, assets/)
vercel.json           routing + file bundling
requirements.txt      psycopg2-binary (Postgres driver; used on Vercel only)
start.bat             local launcher (Windows)
README.md             full docs
```
