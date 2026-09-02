# AventisAI CRM — Vercel Deployment

Import the repo on Vercel and it runs. No terminal required.

The app still runs on Render unchanged — every serverless adaptation is behind a
`VERCEL` environment check, so the same codebase serves both.

---

## Deploy (5 minutes)

### 1. Database

You need Postgres. **Vercel's filesystem is read-only except `/tmp`, and `/tmp`
is wiped between invocations** — there is no SQLite fallback here, by design.
The app fails with a clear error rather than silently accepting writes that
disappear.

Keep using your existing **Supabase** database. Grab the connection string from
Supabase → Settings → Database → Connection string → **URI** tab.

Use the **pooled** connection (port `6543`, host contains `pooler`). Serverless
opens a connection per invocation and a direct connection will exhaust Postgres
connection limits under any real traffic.

### 2. Import to Vercel

1. [vercel.com/new](https://vercel.com/new) → **Import Git Repository**
2. Select **`pradazay1-code/marketing-Sauce`**
3. Framework Preset: **Other** (it auto-detects `api/index.py`)
4. Leave Root Directory as `./`
5. **Deploy**

The first build will fail if `DATABASE_URL` is missing. That is expected — add
the env vars next, then redeploy.

### 3. Environment variables

**Project Settings → Environment Variables.** Add these, then **Redeploy**.

| Variable | Required | Value |
|---|---|---|
| `DATABASE_URL` | **yes** | Supabase pooled URI (port 6543) |
| `DASHBOARD_PASSWORD` | **yes** | Login password (blank = no auth at all) |
| `CRON_SECRET` | **yes** | Long random string — authorizes the cron endpoints |
| `SECRET_KEY` | recommended | Any long random string |
| `ANTHROPIC_API_KEY` | optional | Content AI tab |
| `GOOGLE_PLACES_API_KEY` | optional | Places scraper |
| `HUNTER_API_KEY` | optional | Email enrichment |
| `AVENTIS_SENDER_NAME` | optional | Outbound email |
| `AVENTIS_SENDER_EMAIL` | optional | Outbound email |

`DASHBOARD_PASSWORD` uses HTTP Basic auth — the browser prompts on first visit,
username can be anything.

### 4. Verify

Open your deployment URL. You should get the dashboard.

If you see the error page, the message names the cause. The usual one is a
`DATABASE_URL` missing `?sslmode=require`.

---

## What changed, and why

Four things in the original build are incompatible with serverless. Each one is
now handled rather than removed, so behaviour on Render is identical.

### 1. Background threads → a database work queue

The scraper used to be a `Thread` that outlived the HTTP response:

```python
thread = Thread(target=run_in_background, daemon=True)
thread.start()
return jsonify({"success": True})     # function dies here on Vercel
```

A serverless function is killed the moment it returns, so that thread never
runs. Instead, `/api/run-scraper` now writes one row per (source, state) pair
into a `scrape_queue` table and returns immediately. Each call to
`/api/scrape-step` claims the oldest pending row, runs that single source
in-process, and reports what remains.

The queue lives in Postgres because **serverless keeps no memory between
invocations** — an in-process list would vanish.

`daily_runner.py` already exposed `run_overpass()`, `run_nominatim()`,
`run_yellowpages()` and `run_sos_scrapers()` as separate functions, so this
needed no scraper changes. One source against one state finishes well inside the
60-second budget; the old design budgeted 1,800 seconds for all of them at once.

### 2. 30-minute subprocess → per-step invocation

```python
subprocess.run(cmd, timeout=1800)     # Vercel's ceiling is 60s
```

Gone on serverless. The same work now happens as N short invocations.

### 3. Always-on scheduler → Vercel Cron

`AutomationScheduler` was a `while True` loop in a daemon thread. There is no
always-on process on serverless to host it. `run_scheduled_cycle()` was
extracted from that loop so it can be called directly, and Vercel Cron hits
`/api/cron/automation` daily instead.

On serverless, that cycle *enqueues* discovery rather than running it —
`run_daily_discovery` shells out with a 300s timeout, which also exceeds the
function limit.

### 4. SQLite fallback → hard failure

The original fell back to SQLite when Postgres was unreachable. On serverless
that would accept writes into `/tmp` that vanish on the next request, which
looks like data loss rather than an outage. It now raises with a message naming
the fix.

---

## How scraping behaves now

Press a scraper button and the dashboard drives the queue itself, one step at a
time, sequentially so requests never overlap. Progress updates per step instead
of continuously.

**If you close the tab mid-run, the queue survives.** The daily cron picks it up,
one step per day. To finish it immediately, reopen the dashboard and press the
same source again — a 409 response resumes driving the existing queue rather
than starting a second one.

Cancel with the reset button, which clears both the status flag and the queue.

### Cron schedule

Defined in `vercel.json` (UTC):

| Path | Schedule | Purpose |
|---|---|---|
| `/api/cron/scrape-step` | `0 9 * * *` | Drains one queued step |
| `/api/cron/automation` | `30 9 * * *` | Runs the automation cycle |

**Vercel Hobby allows 2 cron jobs, once per day each.** That is exactly what is
configured. On Pro you can raise the frequency — `0 */2 * * *` on the scrape
step would drain a queue much faster.

Both endpoints authorize on `CRON_SECRET` (Vercel sends it as a bearer token),
and both accept `?secret=` so you can trigger them manually from a browser.

---

## Trade-offs worth knowing

**Scraping is slower here.** A full 3-source × 3-state run is 9 sequential
requests instead of one continuous process. Each has cold-start overhead. It
works, but Render ran it faster.

**Cold starts still exist**, they are just shorter — roughly 1–3 seconds against
Render free's ~30, because the container is smaller.

**Connection pooling matters.** Every invocation opens its own Postgres
connection. Use Supabase's pooled string or you will hit connection limits.

**Both platforms still work.** Nothing here is Vercel-only — Render deploys from
the same commit with no changes, and `render.yaml` is untouched. If you want to
compare them side by side, run both and point a domain at whichever wins.

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Error page: "DATABASE_URL is not set" | Env var missing | Add it, redeploy |
| Error page: "PostgreSQL unavailable" | Bad string or SSL | Append `?sslmode=require` |
| `504` on a scraper step | One source exceeded 60s | Run that source against a single state |
| Scraper stalls at N/9 | Tab closed | Reopen and press the source again, or wait for cron |
| Cron returns 401 | `CRON_SECRET` mismatch | Confirm the value in Project Settings |
| Build fails on size | Bundle over the limit | Drop `Pillow` and `openpyxl` from `requirements.txt` — the web app does not import them |

---

## Local development

Unchanged:

```bash
pip install -r requirements.txt
python wsgi.py
```

Without `VERCEL` set, the app uses background threads and the SQLite fallback
exactly as before. To exercise the serverless paths locally, set `VERCEL=1` and
point `DATABASE_URL` at a real Postgres.
