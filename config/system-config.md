# System Configuration

## Environment
- **Primary Tool:** Claude Code (via IDE — Windsurf/Cursor)
- **Framework:** DOE (Directive-Orchestration-Execution)
- **Language:** Plain English SOPs → AI-executed tasks

## Directory Map
```
marketing-Sauce/
├── CLAUDE.md                    → Master config (loaded first every session)
├── directives/                  → SOPs for every task
│   ├── lead-generation-sop.md
│   ├── client-outreach-sop.md
│   ├── website-creation-sop.md
│   ├── ad-management-sop.md
│   ├── content-creation-sop.md
│   ├── client-onboarding-sop.md
│   ├── sales-framework-sop.md
│   └── research-sop.md
├── orchestration/               → The brain — routing, quality, memory
│   ├── task-router.md
│   ├── quality-control.md
│   └── memory-manager.md
├── execution/                   → The worker — scripts, engines, tools
│   ├── lead-scraper.md
│   ├── outreach-engine.md
│   ├── website-engine.md
│   └── ad-engine.md
├── agents/                      → Specialized agents
│   ├── lead-finder-agent.md
│   ├── outreach-agent.md
│   ├── website-builder-agent.md
│   ├── ad-manager-agent.md
│   ├── content-creator-agent.md
│   ├── client-onboarding-agent.md
│   ├── sales-framework-agent.md
│   ├── research-agent.md
│   └── analytics-agent.md
├── memory/                      → Persistent memory system
│   ├── owner-profile.md
│   ├── clients.md
│   ├── leads.md
│   ├── session-log.md
│   ├── learnings.md
│   ├── goals.md
│   └── dream-100.md
├── templates/                   → Reusable templates
│   ├── outreach-email-templates.md
│   ├── proposal-template.md
│   ├── content-calendar-template.md
│   ├── client-report-template.md
│   └── welcome-email-template.md
├── scripts/                     → Executable scripts (future)
├── tools/                       → Third-party tool configs (future)
└── config/
    └── system-config.md         → This file
```

## Quick Reference — How to Use
| What You Want | What to Say |
|---|---|
| Find new leads | "find me 20 leads in [industry] in [city]" |
| Draft outreach | "draft outreach for top 10 leads" |
| Build a website | "build a website for [client name]" |
| Create ads | "create a Google Ads campaign for [client]" |
| Write content | "create a content calendar for [client] for next month" |
| Onboard a client | "onboard [client name]" |
| Prep for a call | "prep me for a sales call with [prospect]" |
| Research something | "research [topic/industry/competitor]" |
| Check analytics | "show me the campaign results for [client]" |
| Review pipeline | "show me my leads pipeline" |
| Update goals | "update my goals" |
| Session recap | "what did we do last session?" |

## System Rules
1. Always load CLAUDE.md first
2. Read the relevant directive before any task
3. Save everything to memory
4. Quality over speed
5. Ask before assuming
6. Update session log after every session
7. Personalize everything
8. Protect client data
9. Continuously improve
10. This system grows with the business
