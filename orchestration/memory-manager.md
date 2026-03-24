# Memory Manager — Orchestration Layer

## Purpose
Manages the system's memory to ensure nothing is ever forgotten. Controls what gets saved, where it gets saved, and when to retrieve past information.

## Memory Architecture

### `/memory/` Directory Structure
```
memory/
├── owner-profile.md      → Who the owner is, preferences, goals
├── clients.md            → All client information and history
├── leads.md              → Lead pipeline and statuses
├── session-log.md        → What was done each session
├── learnings.md          → Insights, wins, mistakes, improvements
├── goals.md              → Short and long-term business goals
└── dream-100.md          → Top 100 target clients/brands
```

## When to Read Memory
- **Start of every session:** Read `session-log.md` to know what happened last
- **Before any task:** Check relevant memory files for context
- **Before outreach:** Read `leads.md` for lead details
- **Before client work:** Read `clients.md` for client info
- **Before strategy:** Read `learnings.md` for past insights

## When to Write to Memory
- **After finding leads:** Update `leads.md`
- **After client interaction:** Update `clients.md`
- **After every session:** Update `session-log.md`
- **After learning something new:** Update `learnings.md`
- **After goals change:** Update `goals.md`
- **When owner shares preferences:** Update `owner-profile.md`

## Memory File Formats

### Session Log Entry
```
## Session: [Date]
**Duration:** [approx time]
**Tasks Completed:**
- [Task 1 with outcome]
- [Task 2 with outcome]

**Key Decisions:**
- [Decision made and why]

**Next Steps:**
- [What to do next session]

**Learnings:**
- [Anything new learned]
```

### Lead Entry
```
### [Business Name] — Score: [X/40]
- **Status:** [New | Outreach Sent | Responded | Call Scheduled | Proposal Sent | Won | Lost]
- **Industry:** [industry]
- **Location:** [location]
- **Contact:** [name, email, phone]
- **Pain Points:** [observations]
- **Last Action:** [what was done and when]
- **Next Action:** [what to do next]
- **Notes:** [any relevant context]
```

### Client Entry
```
### [Client Name]
- **Status:** [Active | Onboarding | Paused | Completed]
- **Services:** [what we do for them]
- **Start Date:** [date]
- **Contact:** [name, email, phone]
- **Brand:** [colors, fonts, voice notes]
- **Monthly Budget:** [amount]
- **Key Deliverables:** [what we owe them]
- **Performance:** [latest metrics]
- **Notes:** [preferences, history, special requests]
```

## Memory Hygiene
- Review and clean up memory files monthly
- Archive old/inactive leads (move to bottom of file)
- Keep session log entries concise — details in learnings
- Flag outdated information for review
- Never delete history — archive it instead
