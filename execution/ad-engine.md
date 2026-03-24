# Ad Engine — Execution Layer

## Purpose
The actual execution logic for creating and optimizing ad campaigns.

## Campaign Build Process

### 1. Campaign Structure
```
Campaign (Goal-level: e.g., "Summer Lead Gen")
├── Ad Set 1 (Audience: e.g., "Local business owners 25-45")
│   ├── Ad 1 (Pain Point angle)
│   ├── Ad 2 (Benefit angle)
│   └── Ad 3 (Social Proof angle)
├── Ad Set 2 (Audience: e.g., "E-commerce brands")
│   ├── Ad 1 (Pain Point angle)
│   ├── Ad 2 (Benefit angle)
│   └── Ad 3 (Social Proof angle)
└── Ad Set 3 (Retargeting: website visitors)
    ├── Ad 1 (Testimonial)
    └── Ad 2 (Special offer)
```

### 2. Ad Copy Generation
Generate minimum 3 variations per ad set:

**Variation 1: Pain Point (PAS Framework)**
```
Headline: Tired of [pain point]?
Body: [Agitate the problem]. [Present solution]. [Social proof].
CTA: [Action verb] + [Benefit]
```

**Variation 2: Benefit (BAB Framework)**
```
Headline: [Desired result] in [timeframe]
Body: [Before state] → [After state]. [How we bridge the gap].
CTA: [Action verb] + [Benefit]
```

**Variation 3: Social Proof**
```
Headline: How [client/similar business] got [specific result]
Body: [Brief case study]. [Result with numbers].
CTA: Want the same results? [Action]
```

### 3. Targeting Templates

**Local Service Business:**
- Location: [City] + 25mi radius
- Age: 25-55
- Interests: Business owner, entrepreneurship, small business
- Exclude: Competitors, marketing agencies

**E-commerce Brand:**
- Location: National or target regions
- Age: 18-45
- Interests: Online shopping, specific product categories
- Lookalike: Based on existing customer list

**B2B:**
- Platform: LinkedIn preferred
- Job titles: CEO, Owner, Marketing Director, CMO
- Company size: 10-500 employees
- Industry: Target industry

### 4. Budget Allocation Formula
- **Testing Phase (Week 1-2):** 30% of monthly budget
  - Split evenly across ad sets and variations
  - Minimum $5-10/day per ad
- **Optimization Phase (Week 3-4):** 70% of monthly budget
  - Shift budget to winning ads (top 20%)
  - Pause underperformers (bottom 30%)

### 5. A/B Testing Protocol
Test ONE variable at a time:
- Week 1: Test headlines (same body, same image)
- Week 2: Test body copy (winning headline, same image)
- Week 3: Test images/video (winning headline + body)
- Week 4: Test audiences (winning creative)
- Minimum 1,000 impressions before declaring a winner

### 6. Reporting Template
```
## Campaign Report: [Campaign Name]
**Period:** [Start] — [End]
**Platform:** [Platform]
**Budget Spent:** $[amount]

### Key Metrics
| Metric | Result | Benchmark | Status |
|---|---|---|---|
| Impressions | [X] | — | — |
| Clicks | [X] | — | — |
| CTR | [X]% | 1-3% | [Good/Needs Work] |
| CPC | $[X] | $1-3 | [Good/Needs Work] |
| Conversions | [X] | — | — |
| CPA | $[X] | [target] | [Good/Needs Work] |
| ROAS | [X]x | 3x+ | [Good/Needs Work] |

### Top Performing Ads
1. [Ad name] — [key metric]
2. [Ad name] — [key metric]

### Recommendations
- [Action 1]
- [Action 2]
- [Action 3]
```
