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

## Setup — no terminal required

Everything below happens in a browser. Nothing is tied to one computer.

### 1. Database — Neon (free, 3 min)

1. [neon.tech](https://neon.tech) → sign up → create a project
2. Copy the connection string (starts `postgres://`)

That is all. You will apply the schema from the deployed app in step 4.

### 2. Gemini API key (2 min)

[aistudio.google.com/apikey](https://aistudio.google.com/apikey) → Create API key.
The free tier is generous enough to run VERA.

### 3. Deploy to Vercel (5 min)

The repo is already on GitHub, so:

1. [vercel.com/new](https://vercel.com/new) → Import your repository
2. Set **Root Directory** to `onevision-agent`
3. Deploy

Then **Settings → Environment Variables**, add these four, and redeploy:

| Variable | Value |
|---|---|
| `DATABASE_URL` | your Neon string |
| `GEMINI_API_KEY` | your AI Studio key |
| `DASHBOARD_PASSWORD` | whatever you want to log in with |
| `CRON_SECRET` | a long random string — also signs your session cookie |

### 4. Initialize the database (30 sec)

Open this once in any browser:

```
https://<your-app>.vercel.app/api/setup?secret=<YOUR_CRON_SECRET>
```

It creates all 11 tables and loads your seed data — the three clients and eight
facts about your pricing and standards. Idempotent, so hitting it twice is fine.

### 5. Verify

```
https://<your-app>.vercel.app/api/health?secret=<YOUR_CRON_SECRET>
```

Returns `"status": "ready"`, or a list of exactly what is failing and how to fix
each one. It also confirms your Gemini model ID is valid and lists the available
alternatives if it is not.

Then open the app and sign in.

---

## Optional integrations

### Telegram (5 min)

1. Message [@BotFather](https://t.me/BotFather) → `/newbot` → follow prompts
2. Token → `TELEGRAM_BOT_TOKEN`
3. Send your bot any message
4. Open `https://api.telegram.org/bot<TOKEN>/getUpdates`, find `"chat":{"id":…}`
5. That number → `TELEGRAM_CHAT_ID`

For two-way chat, visit once:
`https://<your-app>.vercel.app/api/telegram/webhook?secret=<CRON_SECRET>`

Then `/brief` and `/status` work as shortcuts, and anything else goes to VERA
with full tool access.

### Stripe (2 min)

Dashboard → Developers → API keys → Secret key → `STRIPE_SECRET_KEY`. Read-only.

To attribute revenue per client, set each client's `stripe_customer_id`, or make
sure `contact_email` matches the Stripe billing email.

### Gmail (6 min)

1. [console.cloud.google.com](https://console.cloud.google.com) → new project
2. **APIs & Services → Library** → enable **Gmail API**
3. **OAuth consent screen** → External → add your own email as a test user
4. **Credentials → Create → OAuth client ID → Web application**
   - Redirect URI: `https://<your-app>.vercel.app/api/oauth/google/callback`
5. Client ID + secret → `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET`
6. Redeploy, open `/settings`, click **Connect Gmail**

Scope is `gmail.readonly`. VERA reads and triages; she never sends.

---

## Switching model providers

One variable:

```
LLM_PROVIDER=gemini      # default, uses GEMINI_API_KEY
LLM_PROVIDER=anthropic   # uses ANTHROPIC_API_KEY
```

Both providers implement the same interface in `lib/agent/provider.ts`. Nothing
downstream — tools, memory, jobs, UI — changes. Override the specific model with
`GEMINI_MODEL` or `ANTHROPIC_MODEL`.

One difference worth knowing: Anthropic supports an explicit cache breakpoint, so
the persona is billed at roughly 10% after the first turn. Gemini does implicit
caching on repeated prefixes instead — you still get a discount, you just do not
control where the boundary sits.

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

`runAgent` hands the provider two separate strings: the frozen persona, and the
volatile business snapshot. Each provider places its own cache boundary between
them — Anthropic sets an explicit `cache_control` breakpoint after the persona;
Gemini relies on implicit prefix caching.

Either way the rule is the same: **never interpolate timestamps, UUIDs, or
per-request values into `persona.ts`**, and add new tools to the END of the
`TOOLS` array. Both would shift the prefix and reset the cache on every call.

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
cp .env.example .env.local     # fill in DATABASE_URL and GEMINI_API_KEY
npm run setup                  # applies the schema, no psql needed
npm run dev
```

Local development is entirely optional — the deployed app is the source of truth.

`npm run typecheck` and `npm run build` both pass clean.

---

## Cost

Prompt caching does most of the work here. A typical day — the morning brief, a
handful of chat turns, hourly watchdog runs (no model call), and one weekly review —
lands in the low single-digit dollars. The watchdog is deliberately deterministic so
the hourly cadence costs nothing.

Gemini's free tier covers a lot of this outright. If you move to a paid tier and
want to trim further, point `GEMINI_MODEL` at a Flash-Lite variant for the
triage and watchdog work.

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
