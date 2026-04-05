# Directive: Email Client — One Vision Marketing

## Goal
Send professional emails to clients — cold outreach, website deliveries, proposals, follow-ups.
All emails represent One Vision Marketing (Bridgewater, MA).

## Inputs
- Recipient email address
- Email type: cold-outreach, delivery, follow-up, proposal
- Business name, owner/client name, city
- Website URL (for delivery emails)

## Process
1. Read client info from `clients/{client-name}/CLIENT_SUMMARY.md` if exists
2. Read agency tone from `context/agency.md`
3. Generate email draft: `python execution/email_outreach.py --type <type> --business "Name" --owner "Owner" --city "City"`
4. Show draft to user for approval before sending
5. Send via Gmail MCP tool (`mcp__gmail__send_message`)

## Email Types

### Cold Outreach
- Subject: "Helping {Business Name} Grow Online"
- Tone: Genuine, community-focused, NOT salesy
- Mentions: All services (websites, hosting, ads, client growth, SEO)
- Mentions: RECNA marketing research experience in Bridgewater
- Offers: Free website mockup, no strings attached
- CTA: Quick chat this week

### Website Delivery
- Subject: "Your New Website is Live — {Business Name}"
- Includes: Website URL, what's included, offer to make changes
- Mentions: Future growth services available

### Follow-Up
- Subject: "Just checking in — {Business Name}"
- Tone: Relaxed, no pressure
- Reiterates: Free mockup offer
- CTA: Reply or schedule a chat

### Proposal
- Subject: "Growth Plan for {Business Name}"
- Lists: Website + hosting, ads, SEO, growth strategies
- Mentions: RECNA experience
- CTA: Move forward or ask questions

## Rules
- NEVER send without user confirmation
- Keep subject lines under 60 characters
- Always include a clear but soft CTA
- Sign off as "Pradazay, One Vision Marketing, Bridgewater, MA"
- Never sound money-hungry — focus on helping the business grow
- Frame services as solutions to their problems, not products to sell

## Tools
- `python execution/email_outreach.py` — Generate email drafts
- Gmail MCP (`mcp__gmail__send_message`) — Send emails
