# Skill: Full Pipeline

## Purpose
Run the complete marketing automation pipeline: find leads → build websites → send cold outreach.

## When to Use
- User says "run pipeline", "full pipeline", "find and email leads", "automate outreach"

## Steps

1. **Find Leads** (uses `find-leads` skill)
   ```bash
   python execution/find_leads_web.py --state MA --count 15
   python execution/create_leads_spreadsheet.py
   ```
   - Output: leads spreadsheet + raw_leads.json

2. **Build Websites** (uses `build-site` skill)
   ```bash
   python .claude/skills/build-site/scripts/build_single_site.py --batch clients/leads/raw_leads.json
   ```
   - Generates one HTML site per lead
   - Output: websites in `clients/leads/websites/`

3. **Review with User**
   - Show lead list + generated websites
   - User picks which leads to contact
   - User approves/rejects each website

4. **Cold Outreach** (uses `cold-outreach` skill)
   ```bash
   python .claude/skills/cold-outreach/scripts/generate_outreach.py --leads clients/leads/raw_leads.json
   ```
   - Generate personalized emails with website links
   - Show drafts → get approval → send via Gmail MCP

## Checkpoints (User Must Approve)
- [ ] Leads list looks good
- [ ] Websites look good
- [ ] Email drafts approved
- [ ] Ready to send

## Output
- Leads spreadsheet
- HTML websites per lead
- Sent email log
