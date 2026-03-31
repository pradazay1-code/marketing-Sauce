# Directive: Email Client

## Goal
Send professional emails to clients — website deliveries, proposals, follow-ups.

## Inputs
- Recipient email address
- Email type: delivery, proposal, follow-up, cold-outreach
- Client name
- Attachments or links (optional)

## Process
1. Read client info from `clients/{client-name}/CLIENT_SUMMARY.md` if exists
2. Read agency tone from `context/agency.md`
3. Draft email based on type:
   - **Delivery:** "Your website is live! Here's the link..."
   - **Proposal:** "We'd love to help your business grow online..."
   - **Follow-up:** "Just checking in on the website we delivered..."
   - **Cold-outreach:** "We noticed your business doesn't have a website..."
4. Show draft to user for approval before sending
5. Send via Gmail MCP tool (`mcp__gmail__send_message`)

## Email Templates

### Cold Outreach
Subject: Free Website Mockup for {Business Name}

Hi {Owner Name},

I came across {Business Name} and was impressed by your work. I noticed you don't currently have a website — I'd love to help change that.

I run Marketing Sauce, a local digital marketing agency. We build clean, mobile-friendly websites for small businesses in the {State} area.

I'd be happy to put together a free mockup for you — no strings attached. If you like it, we can talk pricing. If not, no worries at all.

Would you be open to a quick 5-minute call this week?

Best,
Marketing Sauce

### Website Delivery
Subject: Your New Website is Live!

Hi {Client Name},

Great news — your website is officially live! You can view it here:
{Website URL}

The site is mobile-friendly and optimized for search engines. Here's a quick summary of what's included:
{Services List}

Let me know if you'd like any changes. We're here to help.

Best,
Marketing Sauce

## Tools
- Gmail MCP (`mcp__gmail__send_message`)
- Always get user approval before sending

## Notes
- Never send without user confirmation
- Keep subject lines under 50 characters
- Always include a clear CTA
