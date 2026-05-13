# CRM Lead Generation Pipeline

End-to-end SOP for the Aventis CRM: find local businesses without websites → scrape contact info → score by priority → track every deal from first contact through close.

## Architecture

**Layer 1 — Directive:** This file.
**Layer 2 — Orchestration:** You (the agent).
**Layer 3 — Execution:** `execution/crm_*.py` + `crm/index.html`.

```
WebSearch / Discovery  →  raw_leads.json  →  CRM dashboard (crm/index.html)
       ▲                       │                        │
       │              [scoring] │             [pipeline tracking,
       │              [scraping]│              outreach, reports]
       └───  Drag/move  ←───────┴──── stage updates persisted to localStorage
```

## Files

| Path | Purpose |
|------|---------|
| `crm/index.html` | Premium self-contained dashboard. Open in any browser. Persists to localStorage. |
| `execution/crm_find_leads.py` | Discover new MA/RI/CT businesses by type + city. |
| `execution/crm_scrape_contacts.py` | Enrich existing leads with phone + email. |
| `execution/crm_score_leads.py` | Deterministic 0-100 priority scoring engine. |
| `clients/leads/raw_leads.json` | The shared source of truth between Python and the dashboard. |

## Quick Start

```bash
# 1. Open the dashboard
open crm/index.html        # macOS
xdg-open crm/index.html    # Linux

# 2. Find new leads (e.g. 10 bakeries across Rhode Island)
python execution/crm_find_leads.py --type Bakery --state RI --count 10

# 3. Enrich leads that are missing phone/email
python execution/crm_scrape_contacts.py clients/leads/raw_leads.json --limit 20

# 4. Re-score all leads
python execution/crm_score_leads.py clients/leads/raw_leads.json

# 5. Back in the dashboard, click "Import JSON" → select raw_leads.json
```

## Scoring Logic (must match crm/index.html)

| Signal | Points |
|---|---|
| Base | 40 |
| No website | +25 |
| Outdated website | +18 |
| Social-only presence | +14 |
| Valid phone (10+ digits) | +8 |
| Email present | +8 |
| Owner name known | +5 |
| High-LTV business type | +6 |
| Notes mention "new/opening/expanding/ready/launching" | +6 |
| Notes mention "referral/recommended" | +4 |

**Priority bands:** HIGH ≥75 · MEDIUM ≥55 · LOW <55.

If you change one side, update the other. The browser logic is in `scoreLead()` inside `crm/index.html`; the Python copy is in `execution/crm_score_leads.py`.

## Pipeline Stages

The dashboard kanban tracks 7 stages: **New → Contacted → Replied → Meeting → Proposal → Won / Lost.** Drag cards between lanes to advance deals; every move is logged in the lead's activity timeline.

## CRM Dashboard Features

- **Dashboard:** 4 KPIs (Total Leads, Active Deals, Pipeline Value, Hot Leads), activity sparkline, stage distribution, source breakdown, top 5 hottest leads.
- **Leads:** Filterable/searchable table — by priority, state, stage, free-text.
- **Pipeline:** Drag-and-drop kanban with per-stage dollar totals.
- **Map View:** Inline SVG of MA/RI/CT with priority-colored pins per city; hover for popups; pin size scales with lead count.
- **Outreach:** Templated email composer (cold / follow-up / meeting / proposal); sending advances stage from "New" → "Contacted" and logs activity.
- **Reports:** Funnel, conversion rate, response rate, avg deal value, revenue won, breakdown by type and by state.

## Edge Cases & Learnings

- **Schema mismatch:** `raw_leads.json` uses `business_name`/`owner_name`; the dashboard normalizes to `name`/`owner` on import.
- **Phone "N/A":** Treated as missing — the scraper will try to fill it.
- **Owner = "there":** Comes from notes parsing failures; scoring ignores it.
- **Scraping rate limits:** All scripts sleep ~1s between requests and use a custom UA. If DDG blocks you, back off 5+ minutes.
- **Map pins:** Only render for cities listed in `CITY_COORDS` (top ~25 cities in MA/RI/CT). Add new cities to that dict in `crm/index.html` as needed.

## When to Use Each Tool

| You want to... | Use |
|---|---|
| Add one lead manually | Dashboard → "Add Lead" button |
| Discover N new leads of a type | `crm_find_leads.py` |
| Fill in missing contact info | `crm_scrape_contacts.py` |
| Re-rank everything by priority | `crm_score_leads.py` |
| Move a deal forward | Drag the card in Pipeline, or use the stage picker in the lead drawer |
| Send a cold email | Outreach view → pick template → Send (logs activity, advances stage) |
| Review monthly performance | Reports view |
