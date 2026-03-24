# Outreach Engine — Execution Layer

## Purpose
The actual execution logic for creating and managing outreach campaigns.

## Execution Flow

### 1. Load Lead Data
- Read target leads from `memory/leads.md`
- Pull all available info for personalization

### 2. Deep Research Per Lead
For each lead, before writing:
- Visit website → note 2-3 specific issues
- Check social media → note activity level and quality
- Read reviews → note customer sentiment themes
- Check for running ads → note quality
- Find personal detail → recent news, awards, events

### 3. Generate Messages
Using templates from `directives/client-outreach-sop.md`:

**Email Generation:**
```
Subject: [Personalized subject referencing their business]

Hey [First Name],

[Specific observation about their business — NOT generic]

[What we can do for them — tied to the observation]

[Brief social proof — result or credential]

[Low-pressure CTA]

[Your Name]
```

**Batch Processing:**
- Process leads in batches of 10
- Each message takes 2-3 minutes of research + writing
- Save all drafts before presenting to user

### 4. Follow-Up Sequence Generation
For each lead, pre-generate:
- Day 3 follow-up
- Day 7 follow-up (new angle)
- Day 14 break-up message

### 5. Status Tracking
Update each lead in `memory/leads.md`:
- Date outreach sent
- Channel used
- Message sent (or reference)
- Response status
- Follow-up schedule

## Anti-Spam Best Practices
- Never send more than 50 cold emails per day
- Personalize every single message (no mass copy-paste)
- Include an easy opt-out
- Don't use spammy subject lines
- Space out sending times (not all at once)
