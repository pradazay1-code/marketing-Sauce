---
description: Generate and send personalized cold outreach emails to leads via GitHub Actions
tools: Bash, Read, mcp__github__push_files, mcp__github__create_or_update_file
---

# Cold Outreach Skill

## What This Does
Generates personalized cold outreach emails for leads and sends them via GitHub Actions automated workflow. User says "send emails" → agent triggers the pipeline.

## Generate Drafts
```bash
python .claude/skills/cold-outreach/scripts/generate_outreach.py \
  --leads clients/leads/raw_leads.json \
  --site-url "https://pradazay1-code.github.io/marketing-Sauce"
```

## How to Send Emails (Automated)

When the user says "send emails":

1. **Update outreach_drafts.json** with pending emails (status: `pending_approval`)
2. **Push changes** to main branch
3. **Create trigger file** `.github/triggers/send-emails.json` on main branch with:
   ```json
   {"trigger": "send-emails", "timestamp": "<ISO timestamp>"}
   ```
4. The GitHub Actions workflow auto-fires on push and sends all pending emails
5. The workflow commits status updates back to the repo

### Trigger via GitHub MCP:
```
mcp__github__create_or_update_file(
  owner: "pradazay1-code",
  repo: "marketing-Sauce", 
  path: ".github/triggers/send-emails.json",
  content: '{"trigger": "send-emails", "timestamp": "..."}',
  message: "Trigger email send",
  branch: "main"
)
```

## Steps (Full Flow)

1. **Read leads** from `clients/leads/raw_leads.json` or `outreach_drafts.json`
2. **Generate email** for each lead using the cold-outreach template:
   ```bash
   python execution/email_outreach.py --type cold-outreach \
     --business "Business Name" --owner "Owner" --city "City"
   ```
3. **Save drafts** to `clients/leads/outreach_drafts.json`
4. **Show each draft** to user for approval
5. **Push outreach_drafts.json** to main via GitHub MCP
6. **Create trigger file** to fire the GitHub Actions workflow
7. **Workflow sends emails** and commits status updates automatically

## Email Template Info
- Brand: **One Vision Marketing** (Bridgewater, MA)
- Signed by: **Isaiah Wright**
- Tone: Professional, genuine, NOT salesy
- Services listed: websites, hosting, ads, SEO, social media, growth strategies
- Mentions: RECNA marketing research experience
- CTA: Free website mockup, quick chat

## Rules
- **NEVER send without user approval** — show draft first, wait for confirmation
- **ALWAYS build a custom website for each lead BEFORE drafting the email** — use `build_single_site.py` with the lead's name, type, city, state. Every email MUST include a link to that lead's unique site (not the generic agency homepage).
- **NEVER use `https://pradazay1-code.github.io/marketing-Sauce/` as the website link in an email** — that is the agency homepage, not a lead's custom site.
- The correct URL format is: `https://pradazay1-code.github.io/marketing-Sauce/clients/leads/websites/{slug}/`
- After building the site, set `website_built: true`, `website_path`, and `website_url` in `outreach_drafts.json` before writing the email body.
- If lead has an email, use it. If not, skip and note "no email found"
- Track send status in outreach_drafts.json
- Space emails 30+ seconds apart to avoid spam flags
