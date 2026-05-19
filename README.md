# AventisAI — 2026 Marketing Agency CRM

Full-stack lead generation & outreach platform: multi-source discovery, AI-personalized cold emails, automation engine, and analytics dashboard.

## Deploy (Free, 10 Minutes)

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/pradazay1-code/marketing-Sauce)

**Full guide:** [DEPLOY.md](./DEPLOY.md) — Render + Supabase = $0/month forever, data persists.

## What's In Here

| Component | Path | Purpose |
|-----------|------|---------|
| **CRM Web App** | `leadgen/app.py` | Flask dashboard — leads, pipeline, reports, automation |
| **Lead Finder** | `execution/aventis_lead_finder.py` | Multi-source discovery + enrichment + ICP scoring |
| **Outreach Engine** | `execution/aventis_outreach.py` | AI-personalized cold email sequences |
| **Automation Engine** | `leadgen/automation_engine.py` | Scheduled discovery + follow-up automation |
| **Content AI** | `execution/generate_instagram.py` + `generate_content_visuals.py` | Instagram content + visuals generator |
| **Directives** | `directives/` | SOPs for each workflow |

## Quick Start (Local)

```bash
pip install -r requirements.txt
python leadgen/app.py
# Open http://localhost:5000
```

## Run a Test Lead Discovery

```bash
python execution/aventis_lead_finder.py --demo --city Boston --state MA --count 10 --enrich --score --save-db
```

## Architecture

3-layer system: **Directive** (SOPs in `directives/`) → **Orchestration** (Claude reads directives, routes work) → **Execution** (Python scripts in `execution/`). See [CLAUDE.md](./CLAUDE.md) for full agent instructions.

## License

Private. All rights reserved.
