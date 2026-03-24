# Quality Control — Orchestration Layer

## Purpose
Ensures all outputs from the system meet agency standards before delivery. Prevents the "90% → 70% → 35% decay" problem described in the DOE framework.

## The Decay Problem
If AI produces 90% quality output, and the next task builds on that 90% output, the quality compounds downward:
- Step 1: 90%
- Step 2: 90% × 90% = 81%
- Step 3: 81% × 90% = 73%
- Step 5: ~59%
- Step 10: ~35%

## The Fix: Quality Gates
Every output passes through a quality gate before being used as input for the next step.

### Quality Gate Process
1. **Check against directive** — Does the output follow the SOP?
2. **Check for specificity** — Is it personalized or generic?
3. **Check for accuracy** — Are facts, names, and data correct?
4. **Check for completeness** — Is anything missing?
5. **Check for tone** — Does it match the intended voice?

### Quality Scores
- **95-100%:** Ship it — ready for client/user
- **85-94%:** Minor fixes needed — adjust and re-check
- **70-84%:** Significant revision needed — go back to the directive
- **Below 70%:** Start over — something fundamental is wrong

## Standards by Output Type

### Lead Generation
- Every lead has verified business info
- Pain points based on actual observations
- No duplicate leads
- Scores calculated correctly

### Outreach Messages
- References something SPECIFIC about the business
- Under 100 words
- Clear CTA
- Tone matches channel
- No generic phrases ("I hope this finds you well")

### Websites
- Mobile responsive
- Loads under 3 seconds
- No placeholder content
- SEO basics in place
- All forms working

### Ad Campaigns
- Minimum 3 copy variations
- Targeting is specific (not too broad)
- Budget correctly allocated
- Tracking set up
- Landing page matches ad message

### Content
- Hook stops the scroll
- Brand voice consistent
- No errors
- CTA present
- Hashtags relevant

## Continuous Improvement
- After every task, note what could be improved
- Update directives based on quality patterns
- Track which agents consistently produce high-quality output
- Log quality issues and fixes in `memory/learnings.md`
