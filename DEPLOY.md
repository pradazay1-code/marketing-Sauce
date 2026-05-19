# AventisAI CRM — Free Deployment Guide

Deploy your CRM **100% free, forever**, with your data safely stored.

**Total time:** 10 minutes
**Cost:** $0/month forever
**Stack:** Render (free web hosting) + Supabase (free Postgres database)

---

## Why This Setup?

| Component | Why |
|-----------|-----|
| **Render free tier** | Free web hosting, no credit card. Sleeps after 15 min idle (cold start ~30 sec). |
| **Supabase free Postgres** | 500 MB database, free forever, **your leads are saved permanently** even when Render sleeps. |

**Important:** Render's free tier has an ephemeral filesystem — if you use SQLite, your data is wiped every time it sleeps or restarts. Supabase Postgres solves this completely.

---

## Step 1 — Create Free Postgres on Supabase (3 minutes)

1. Go to **https://supabase.com** and click **Sign up** (use GitHub for fastest signup)
2. Click **New Project**
3. Fill in:
   - **Name:** `aventisai-crm`
   - **Database Password:** Generate a strong one — **save this somewhere**
   - **Region:** Pick closest to you (e.g., `US East`)
   - **Plan:** Free
4. Wait ~1 minute for the project to spin up
5. In the left sidebar, click the gear icon → **Database**
6. Scroll down to **Connection string** → click the **URI** tab
7. Copy the connection string. It looks like:
   ```
   postgresql://postgres.xxxxxxxx:[YOUR-PASSWORD]@aws-0-us-east-1.pooler.supabase.com:6543/postgres
   ```
8. Replace `[YOUR-PASSWORD]` with your actual database password
9. **Save this final string** — you'll paste it into Render next

---

## Step 2 — Deploy to Render (5 minutes)

### Option A: One-click deploy (recommended)
1. Go to **https://render.com** and sign up (use GitHub for fastest signup)
2. Click **New +** → **Blueprint**
3. Connect your GitHub account if prompted
4. Select repo: **`pradazay1-code/marketing-Sauce`**
5. Branch: **`claude/marketing-agency-backend-Efh39`** (or `main` after merging the PR)
6. Render reads `render.yaml` automatically and shows the service config
7. Click **Apply**
8. Render will now build & deploy. Takes ~3-5 minutes.

### Option B: Manual setup
1. Sign in to Render → **New +** → **Web Service**
2. Connect repo `pradazay1-code/marketing-Sauce`, branch `claude/marketing-agency-backend-Efh39`
3. Settings:
   - **Name:** `aventisai-crm`
   - **Runtime:** Python 3
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `gunicorn wsgi:app --bind 0.0.0.0:$PORT --workers 2 --timeout 120`
   - **Plan:** Free
4. Click **Create Web Service**

---

## Step 3 — Connect Render to Supabase (2 minutes)

1. In Render, open your service → **Environment** tab
2. Click **Add Environment Variable** and add:

| Key | Value |
|-----|-------|
| `DATABASE_URL` | *(paste your Supabase connection string from Step 1)* |
| `DASHBOARD_PASSWORD` | *(any password you want for login)* |
| `PYTHON_VERSION` | `3.11` |

3. Optional API keys (you can add these later):

| Key | Where to Get It |
|-----|-----------------|
| `ANTHROPIC_API_KEY` | https://console.anthropic.com — enables AI-personalized emails |
| `GOOGLE_PLACES_API_KEY` | https://console.cloud.google.com — better lead discovery |
| `HUNTER_API_KEY` | https://hunter.io — email finder (25 free/month) |
| `AVENTIS_SENDER_NAME` | Your name (e.g., `Pradip`) |
| `AVENTIS_SENDER_EMAIL` | Your sender email |

4. Click **Save Changes** — Render will auto-redeploy with the new env vars

---

## Step 4 — Access Your Live CRM

1. In Render, look for your service URL — it'll be like:
   ```
   https://aventisai-crm.onrender.com
   ```
2. Open it in a browser
3. Log in with the username `admin` (or anything) and the `DASHBOARD_PASSWORD` you set
4. **You're live.**

---

## Important Notes

### Free Tier Behavior
- **App sleeps after 15 min idle.** First visit after sleeping takes ~30 sec to wake up. This is fine for personal use — you'll barely notice once it's up.
- **Your data is always safe** because it lives in Supabase, not Render.
- **750 instance hours/month free.** If you run a single service 24/7 you'll be under this limit.

### Keep It Awake (Optional)
If you want to avoid the cold start, you can use a free uptime monitor to ping your `/api/health` endpoint every 14 minutes:
- **https://cron-job.org** — free, simple cron jobs
- **https://uptimerobot.com** — free 5-min interval pings

Add this URL to ping: `https://aventisai-crm.onrender.com/api/health`

### Upgrade Path
- **Render Starter:** $7/mo — no sleeping, custom domain, more RAM
- **Supabase Pro:** $25/mo — only needed if you exceed 500 MB of leads (that's ~50,000+ leads)

---

## Local Development

You can still run locally:

```bash
python leadgen/app.py
```

To use Supabase locally too, create `.env`:

```bash
DATABASE_URL=postgresql://postgres.xxx:password@...
DASHBOARD_PASSWORD=local
ANTHROPIC_API_KEY=sk-...
```

Without `DATABASE_URL`, the app falls back to SQLite at `leadgen/leads.db` (perfect for testing).

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| Build fails: "psycopg2 install error" | Already in `requirements.txt` as `psycopg2-binary` — should be fine |
| App shows "Application Error" | Check Render logs → most likely `DATABASE_URL` is missing or malformed |
| Login prompts forever | `DASHBOARD_PASSWORD` env var not set |
| Database connection refused | Supabase URL must use port `6543` (pooler) not `5432` (direct) |
| Slow first load | Normal — free tier cold start. Set up an uptime monitor if it bothers you. |

---

## Total Monthly Cost: **$0**

Forever. Your leads are safe in Supabase. Your CRM runs on Render. No credit card required for either.
