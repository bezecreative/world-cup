# MOX Collective · World Cup Bracket

A dark, MOX-branded World Cup bracket game. Everyone builds a knockout bracket
(Round of 32 → Champion), results auto-update from a live football API (with a
manual override), and a leaderboard ranks who's calling it best so far.

The same code runs two ways:

| | Storage | Use |
|---|---|---|
| **Local** | SQLite file (`bracket.db`) | dev / quick self-host. Zero setup. |
| **Vercel** | Vercel Postgres | hosted for the whole crew. One resource to create — no Blob store, no file storage. |

It picks the backend automatically: if `POSTGRES_URL` is set it uses Postgres, otherwise SQLite.

---

## Run locally

```bash
python api/index.py
```

Then open **http://localhost:8000**. On Windows you can double-click **`start.bat`**.

Config (all optional, via environment variables):

| Variable | Default | Purpose |
|---|---|---|
| `PORT` | `8000` | local port |
| `ADMIN_PASSWORD` | `mox` | gate for the Admin tab (results / lock / sync) |
| `FOOTBALL_DATA_API_KEY` | — | free key from [football-data.org](https://www.football-data.org/) for live sync |

---

## Deploy to Vercel

You'll do four things in the Vercel dashboard; I've already set up the code.

1. **Push this folder to a Git repo** (GitHub/GitLab/Bitbucket) and **Import** it
   into Vercel (New Project → Import). No build settings needed — `vercel.json`
   and `requirements.txt` are already here.

2. **Create a Postgres store**: in the project, go to **Storage → Create Database
   → Postgres**, and connect it to the project. Vercel automatically injects the
   `POSTGRES_URL` environment variable — that's all the app needs. Tables are
   created on first run.

3. **Add environment variables** (Project → Settings → Environment Variables):
   - `ADMIN_PASSWORD` → your chosen admin password
   - `FOOTBALL_DATA_API_KEY` → optional, for live result sync

4. **Deploy.** Visit the project URL and share it with the crew.

That's it. Brackets live in Postgres, so they persist across redeploys and cold starts.

> Tip: lock brackets (Admin → Lock brackets) once the knockouts kick off so no
> one edits after the games start.

---

## How it works

- **Build yours** — name → pick every matchup one at a time → champion → lock in.
- **Bracket** — the live tournament tree (connectors light up as games finish).
- **Leaderboard** — points. Round weights: R32 = 1, R16 = 2, QF = 4, SF = 8, Final/Champion = 16.
- **Players** — browse everyone's full bracket; correct picks turn green as results land.
- **Admin** (password-gated) — sync live results, set winners manually, lock/unlock, clear results.

## Teams / bracket

The real 2026 knockout bracket (teams + Round-of-32 pairings + feeder paths) lives
in **`api/tournament.json`** — this is the seed loaded into the database on first
run. Edit it there if matchups change, then clear the `tournament` row (Admin →
Clear all results re-saves; or drop the row in Postgres) to reseed.

## Project layout

```
api/index.py          the app (serverless handler + local server; SQLite or Postgres)
api/tournament.json   seed bracket (teams, structure)
public/               frontend (index.html, app.js, styles.css, Gyst font, MOX assets)
vercel.json           Vercel routing (/api/* -> function) + file bundling
requirements.txt      psycopg2-binary (Postgres driver, used on Vercel only)
```
