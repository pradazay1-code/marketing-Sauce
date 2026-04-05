---
description: End-to-end pipeline — find leads, build websites, send outreach emails
tools: WebSearch, Bash, Write, Read, mcp__gmail__send_message
---

# Full Pipeline Skill

## What This Does
Runs the complete marketing automation pipeline: Find Leads → Build Websites → Generate Outreach → Send Emails.

## Pipeline Flow
```
WebSearch → raw_leads.json → build_single_site.py → websites/ → generate_outreach.py → outreach_drafts.json → Gmail MCP
```

## Steps

### Step 1: Find Leads
```bash
python execution/find_leads_web.py --state MA --count 15
```
Output: `clients/leads/raw_leads.json`

### Step 2: Build Websites
```bash
python .claude/skills/build-site/scripts/build_single_site.py \
  --batch clients/leads/raw_leads.json
```
Output: `clients/leads/websites/{slug}/index.html`

### Step 3: Generate Outreach Emails
```bash
python .claude/skills/cold-outreach/scripts/generate_outreach.py \
  --leads clients/leads/raw_leads.json \
  --site-url "https://pradazay1-code.github.io/marketing-Sauce"
```
Output: `clients/leads/outreach_drafts.json`

### Step 4: Send Emails (requires user approval)
- Show each draft to user
- Send approved drafts via `mcp__gmail__send_message`
- Update status in `outreach_drafts.json`

## Checkpoints
- After Step 1: Confirm lead count and quality with user
- After Step 2: Confirm websites look good
- After Step 3: Show email drafts for approval
- After Step 4: Report send results

## Notes
- Each step can be run independently via its own skill
- Always pause for user approval before sending emails
- If any step fails, fix and retry before continuing
