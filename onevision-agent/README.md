# VERA — Business Agent for One Vision Marketing

An AI chief of staff that holds the state of your business, watches it continuously,
and tells you what needs you.

Built for Isaiah Wright / One Vision Marketing Agency. Runs on Vercel.

---

## What she does

| Capability | How it works |
|---|---|
| **Knows the business cold** | A persona written as a 15-year colleague, plus a Postgres knowledge base seeded with your clients, pricing, standards, and frameworks |
| **Reads your email** | Gmail sync every 2 hours, then triage: category, priority, needs-reply, one-line summary, suggested action |
| **Tracks Stripe revenue** | Charges, refunds, subscriptions, and failed payments mirrored locally and attributed to clients |
| **Reviews clients continuously** | Weekly health scoring (0–100) across deliverables, contact recency, and payment history — with alerts and tasks when a score drops |
| **Learns and remembers** | Every durable fact is written to a searchable memory table. Facts that prove useful rank higher over time; superseded facts are archived, not deleted |
| **Alerts you on Telegram** | Push for urgent items, a daily morning brief, and full two-way chat from your phone |
| **Answers anything** | 14 tools give her direct read/write access to clients, deliverables, revenue, email, tasks, alerts, and memory — plus a guarded read-only SQL escape hatch |

Eight tabs: Dashboard · Ask VERA · Clients · Inbox · Revenue · Tasks · Memory · Alerts · Settings.

---

## Setup — about 25 minutes

### 1. Database (5 min)

Any Postgres works. **Neon** is the easiest free option.

1. Sign up at [neon.tech](https://neon.tech) → create a project
2. Copy the connection string (starts `postgres://`)
3. Apply the schema — paste the contents of `db/schema.sql` into Neon's SQL Editor and run it

The schema is idempotent and seeds your three known clients plus eight starting facts.

### 2. Anthropic key (2 min)

[console.anthropic.com](https://console.anthropic.com) → API Keys → create one.

### 3. Deploy to Vercel (5 min)

```bash
cd onevision-agent
npx vercel
```

Or push to GitHub and import at [vercel.com/new](https://vercel.com/new) with **Root Directory** set to `onevision-agent`.

Then add environment variables in **Vercel → Settings → Environment Variables**:

| Variable | Value |
|---|---|
| `DATABASE_URL` | Your Postgres connection string |
| `ANTHROPIC_API_KEY` | `sk-ant-…` |
| `DASHBOARD_PASSWORD` | Whatever you want to log in with |
| `CRON_SECRET` | A long random string — also signs your session cookie |

Redeploy after adding them.

### 4. Telegram (5 min — recommended)

1. Message [@BotFather](https://t.me/BotFather) → `/newbot` → follow prompts
2. Copy the token → `TELEGRAM_BOT_TOKEN`
3. Send your new bot any message
4. Open `https://api.telegram.org/bot<TOKEN>/getUpdates` and find `"chat":{"id":…}`
5. That number → `TELEGRAM_CHAT_ID`

For two-way chat, visit once in your browser:
```
https://your-app.vercel.app/api/telegram/webhook?secret=<YOUR_CRON_SECRET>
```

Then `/brief` and `/status` work as shortcuts, and any other message goes to VERA with full tool access.

### 5. Stripe (2 min — optional)

Dashboard → Developers → API keys → Secret key → `STRIPE_SECRET_KEY`.

Read-only. To attribute revenue to clients automatically, set each client's
`stripe_customer_id` or make sure `contact_email` matches the Stripe billing email.

### 6. Gmail (6 min — optional)

1. [console.cloud.google.com](https://console.cloud.google.com) → new project
2. **APIs & Services → Library** → enable **Gmail API**
3. **OAuth consent screen** → External → add your own email as a test user
4. **Credentials → Create → OAuth client ID → Web application**
   - Authorized redirect URI: `https://your-app.vercel.app/api/oauth/google/callback`
5. Copy client ID + secret → `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET`
6. Redeploy, open `/settings`, click **Connect Gmail**

Scope is `gmail.readonly`. VERA reads and triages; she never sends.

---

## Schedule

Defined in `vercel.json` (UTC):

| Job | Cadence | What it does |
|---|---|---|
| `sync` | Every 2 hours | Pull Gmail + Stripe, triage new mail |
| `watchdog` | Hourly | Deterministic rules — failed payments, silent clients, overdue work. No model call |
| `morning-brief` | Daily 7:30am ET | VERA writes your briefing and pushes it to Telegram |
| `client-review` | Mondays 9am ET | Score every client's health, raise alerts, create tasks |

Every job can be fired manually from **Settings → Run now**.

---

## Architecture

```
app/
  page.tsx                Dashboard
  chat/                   Conversational UI
  clients/[slug]/         Client detail
  inbox/ revenue/ tasks/ memory/ alerts/ settings/
  api/
    chat/                 Agent endpoint
    cron/[job]/           Scheduled jobs (Vercel Cron + manual)
    telegram/webhook/     Two-way Telegram
    oauth/google/         Gmail OAuth

lib/
  db.ts                   Pooled Postgres + row types
  auth.ts                 HMAC session cookie, cron bearer guard
  agent/
    persona.ts            The 15-year-colleague system prompt
    tools.ts              14 tool definitions + executors
    memory.ts             Write / recall / supersede
    run.ts                Tool loop with prompt caching
  integrations/
    gmail.ts  stripe.ts  telegram.ts
  jobs/index.ts           The four scheduled jobs

db/schema.sql             Full schema + seed data
```

### Prompt caching

Request order is `tools → system[0] → system[1] → messages`.

`system[0]` is the frozen persona carrying `cache_control: ephemeral`. `system[1]` is
the live business snapshot, placed *after* the breakpoint so it can change every turn
without invalidating the cached prefix. In practice that means the long persona is
billed at roughly 10% on every turn after the first.

**If you edit `persona.ts` or reorder `TOOLS`, the cache resets on the next request.**
That is expected — just don't interpolate timestamps or IDs into either one.

### Memory

Postgres full-text search ranked by `relevance × importance × proven usefulness`.
No embedding provider needed — one less key, one less failure mode. Near-duplicate
writes reinforce the existing fact rather than creating a second copy. If recall ever
plateaus, add pgvector alongside this ranking rather than replacing it.

---

## Local development

```bash
cd onevision-agent
npm install
cp .env.example .env.local     # fill in DATABASE_URL and ANTHROPIC_API_KEY
psql "$DATABASE_URL" -f db/schema.sql
npm run dev
```

`npm run typecheck` and `npm run build` both pass clean.

---

## Cost

Prompt caching does most of the work here. A typical day — the morning brief, a
handful of chat turns, hourly watchdog runs (no model call), and one weekly review —
lands in the low single-digit dollars. The watchdog is deliberately deterministic so
the hourly cadence costs nothing.

To spend less, set `AGENT_MODEL=claude-sonnet-5`. To spend more for sharper judgment,
leave it on `claude-opus-5`, which is the default.

---

## Security notes

- Single-user auth: password login, HMAC-signed session cookie, 30-day expiry.
- Cron endpoints require `CRON_SECRET` as a bearer token, or an authenticated session.
- The Telegram webhook validates the secret header *and* pins your chat ID.
- Gmail access is read-only. VERA drafts; she does not send.
- `query_database` accepts `SELECT` only and rejects anything containing a write
  keyword, multiple statements, or an unbounded result set.
- The persona explicitly instructs her to treat email content as data, never as
  instructions — the standard prompt-injection guard for an agent that reads mail.
