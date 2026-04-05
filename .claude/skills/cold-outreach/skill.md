# Skill: Cold Outreach

## Purpose
Send personalized cold outreach emails to leads offering a free website mockup.

## When to Use
- User says "email leads", "send outreach", "cold email", "reach out"
- Part of the full pipeline after websites are built

## Steps

1. **Load leads**
   - Read from `clients/leads/raw_leads.json`
   - Filter: only leads with status "No Website" and priority "HIGH" or "MEDIUM"

2. **Generate emails**
   ```bash
   python .claude/skills/cold-outreach/scripts/generate_outreach.py \
     --leads clients/leads/raw_leads.json \
     --output clients/leads/outreach_drafts.json
   ```
   - Personalizes subject + body per lead
   - Includes link to their mockup website if available

3. **Show drafts for approval**
   - Display each email draft to user
   - User approves, edits, or skips each one
   - NEVER send without explicit user approval

4. **Send approved emails**
   - Use `mcp__gmail__send_message` for each approved email
   - Log sent emails to `clients/leads/outreach_log.json`

5. **Schedule follow-ups**
   - Mark leads as "contacted" in the log
   - Follow-up emails go out 5-7 days later (user triggers manually)

## Output
- `clients/leads/outreach_drafts.json` — generated drafts
- `clients/leads/outreach_log.json` — sent email log

## Rules
- ALWAYS get user approval before sending ANY email
- Keep subject lines under 50 characters
- Use agency tone from `context/agency.md`
- Include clear CTA (5-minute call)
- Never attach files — link to the mockup site instead
