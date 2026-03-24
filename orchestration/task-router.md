# Task Router — Orchestration Layer

## Purpose
The brain of the system. When a request comes in, the task router determines which agent(s) and directive(s) to activate, what tools are needed, and how to handle errors.

## Routing Logic

### Request → Agent Mapping
| User Says (keywords) | Primary Agent | Directive | Secondary Agent |
|---|---|---|---|
| "find leads", "get prospects", "find businesses" | lead-finder | lead-generation-sop | outreach (for prep) |
| "reach out", "send emails", "draft messages" | outreach | client-outreach-sop | sales-framework (if call prep needed) |
| "build website", "create site", "landing page" | website-builder | website-creation-sop | content-creator (for copy) |
| "create ads", "run campaign", "manage ads" | ad-manager | ad-management-sop | website-builder (for landing pages) |
| "create content", "write posts", "content calendar" | content-creator | content-creation-sop | — |
| "onboard client", "new client", "set up client" | client-onboarding | client-onboarding-sop | all (based on services) |
| "sales call", "prep for call", "create proposal" | sales-framework | sales-framework-sop | research (for pre-call) |
| "research", "analyze", "look into" | research | research-sop | — |
| "show results", "analytics", "how's campaign" | analytics | ad-management-sop | — |
| "what did we do", "last session", "catch me up" | — | — | Read memory/session-log.md |
| "update goals", "my goals" | — | — | Edit memory/goals.md |
| "show pipeline", "my leads" | — | — | Read memory/leads.md |

### Multi-Agent Tasks
Some requests require multiple agents working together:

**"Get me 20 leads and draft outreach for the top 5"**
1. lead-finder agent runs first → saves leads
2. outreach agent runs second → drafts messages for top 5

**"Build a website and create social content for [client]"**
1. website-builder agent runs → builds site
2. content-creator agent runs → creates content
(These can run in parallel)

**"Onboard [client] — they need a website, ads, and content"**
1. client-onboarding agent runs first → sets up client file
2. website-builder, ad-manager, and content-creator run in parallel

## Error Handling

### If a tool fails:
1. Log the error
2. Try an alternative approach
3. If still failing, ask the user for guidance
4. Never silently fail — always report what happened

### If output quality is low:
1. Re-read the directive
2. Check if all required inputs were gathered
3. Regenerate with more specific instructions
4. Ask user for clarification if needed

### If a task is ambiguous:
1. Check memory files for context
2. Reference similar past tasks from session-log
3. If still unclear, ask the user — don't guess

## Pre-Execution Checklist
Before any agent runs:
- [ ] Correct directive loaded?
- [ ] All required inputs gathered?
- [ ] Memory files checked for relevant context?
- [ ] Output format clear?
- [ ] User expectations set?

## Post-Execution Checklist
After any agent completes:
- [ ] Output meets quality standards from directive?
- [ ] Results saved to appropriate memory file?
- [ ] Session log updated?
- [ ] User informed of results?
- [ ] Any follow-up tasks identified?
