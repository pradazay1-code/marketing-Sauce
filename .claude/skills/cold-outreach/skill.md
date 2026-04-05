---
description: Generate and send personalized cold outreach emails to leads via Gmail
tools: Bash, Read, mcp__gmail__send_message
---

# Cold Outreach Skill

## What This Does
Generates personalized cold outreach emails for leads and sends them via Gmail MCP. Always requires user approval before sending.

## Generate Drafts
```bash
python .claude/skills/cold-outreach/scripts/generate_outreach.py \
  --leads clients/leads/raw_leads.json \
  --site-url "https://pradazay1-code.github.io/marketing-Sauce"
```

## Steps

1. **Read leads** from `clients/leads/raw_leads.json` or `outreach_drafts.json`
2. **Generate email** for each lead using the cold-outreach template:
   ```bash
   python execution/email_outreach.py --type cold-outreach \
     --business "Business Name" --owner "Owner" --city "City"
   ```
3. **Save drafts** to `clients/leads/outreach_drafts.json`
4. **Show each draft** to user for approval
5. **Send approved emails** via Gmail MCP:
   ```
   mcp__gmail__send_message(to, subject, body)
   ```
6. **Update status** in `outreach_drafts.json` from `pending_approval` → `sent`

## Email Template Info
- Brand: **One Vision Marketing** (Bridgewater, MA)
- Signed by: **Isaiah Wright**
- Tone: Professional, genuine, NOT salesy
- Services listed: websites, hosting, ads, SEO, social media, growth strategies
- Mentions: RECNA marketing research experience
- CTA: Free website mockup, quick chat

## Rules
- **NEVER send without user approval** — show draft first, wait for confirmation
- If lead has an email, use it. If not, skip and note "no email found"
- Track send status in outreach_drafts.json
- Space emails 30+ seconds apart to avoid spam flags
