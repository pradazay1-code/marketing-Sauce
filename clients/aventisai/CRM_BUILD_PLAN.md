# AventisAI CRM — 2026 Lead Generation & Outreach Platform

**Research, Architecture & Build Plan**

---

## 1. Research — What Makes a 2026 CRM Effective

### The Modern Lead Gen Pipeline

```
DISCOVER  →  ENRICH  →  SCORE  →  STORE  →  OUTREACH  →  TRACK  →  CONVERT
```

Every stage needs to be (1) automated, (2) AI-augmented, and (3) measurable. Tools that only do one stage (just scraping, just CRM, just email) lose to integrated platforms.

### 2026 Best Practices

| Stage | What Top Performers Do | What Most Tools Miss |
|-------|----------------------|---------------------|
| **Discover** | Multi-source (Google Places + Yelp + OSM + LinkedIn) | Single source = thin data |
| **Enrich** | Owner name, email, phone, tech stack, reviews, social | Email-only enrichment |
| **Score** | AI scores fit (ICP match) and intent signals | Manual qualification = bottleneck |
| **Store** | Activity timeline, pipeline stages, tags, notes | Just a contact list |
| **Outreach** | AI-personalized first line, multi-step sequences | Generic templates |
| **Track** | Opens, clicks, replies, sentiment | No feedback loop |
| **Convert** | Automated handoff, calendar booking, follow-up tasks | Manual handoff = drop-off |

### Best Data Sources (2026)

| Source | Cost | Use Case | Quality |
|--------|------|----------|---------|
| **Google Places API** | $200/mo free credit (~11K lookups) | Local business discovery, reviews | ⭐⭐⭐⭐⭐ |
| **Yelp Fusion API** | Free 5K/day | Local restaurants, services | ⭐⭐⭐⭐ |
| **OpenStreetMap Overpass** | Free | Bulk geo-based discovery | ⭐⭐⭐ |
| **Hunter.io** | Free 25/mo, $49/mo for 500 | Email finding | ⭐⭐⭐⭐ |
| **Apollo.io** | Free 50/mo, $49/mo for 1.2K | B2B contacts + emails | ⭐⭐⭐⭐⭐ |
| **Website scraping** | Free (DIY) | Email/phone from "Contact" pages | ⭐⭐⭐ |
| **BuiltWith / Wappalyzer** | Free tier | Detect tech stack (HubSpot? Mailchimp?) | ⭐⭐⭐⭐ |
| **LinkedIn Sales Nav** | $99/mo | Owner names, employee count | ⭐⭐⭐⭐⭐ |

### Best Email Outreach Stack (2026)

| Tier | Tool | Cost | Why |
|------|------|------|-----|
| **DIY** | Gmail MCP + Claude API | ~$5-20/mo | What we already have — AI-personalized, free sending |
| **Pro** | Instantly.ai or Smartlead | $37-39/mo | Built-in warmup, multi-inbox rotation, deliverability |
| **Scale** | Lemlist or Apollo Outreach | $59-99/mo | Multi-channel (email + LinkedIn) |

**Recommendation:** Start with our DIY stack (Gmail + Claude). Switch to Instantly.ai when sending >50 cold emails/day.

---

## 2. Audit — What We Already Have

### Existing System (LeadPilot in `leadgen/`)

| Component | Status | Notes |
|-----------|--------|-------|
| Flask web app (`app.py`) | Working | 647 lines, dashboard + leads + pipeline + map + reports + email |
| Database layer (`database.py`) | Working | 753 lines, SQLite + PostgreSQL adapter, lead/activity/email tables |
| Scrapers | Working | Google Places, Nominatim, OSM Overpass, YellowPages, SoS, business age verifier |
| Email service | Basic | `email_service.py` with default templates, no AI personalization |
| Templates (UI) | Functional | Dashboard, leads, pipeline, map, reports, email pages |
| Lead scoring | Basic | `utils.py` has `calculate_lead_score` |

### Existing Lead Tools (in `execution/`)

| Script | Purpose | Status |
|--------|---------|--------|
| `find_leads.py` | Direct HTTP lead scraper (587 lines) | Works |
| `find_leads_web.py` | WebSearch-based finder | Limited |
| `email_outreach.py` | Email outreach | Basic |
| `seo_audit.py` | SEO audit per lead | Works |

### What's Missing for a 2026-Ready CRM

| Gap | Impact | Fix |
|-----|--------|-----|
| No Google Places API integration | High — best data source unused | Add Places API scraper |
| No email finder/verifier | High — leads have no email | Add Hunter.io + website scraping |
| No AI-personalized outreach | High — generic emails = low reply rate | Claude API for opening lines |
| No AI lead scoring | Med — manual qualification slow | Claude API for ICP scoring |
| No automation engine | Med — manual triggering | Scheduler + drip sequences |
| Generic LeadPilot branding | Low (cosmetic) | Rebrand to AventisAI |
| No tech-stack detection | Med — can't identify SaaS pain | BuiltWith/Wappalyzer detection |
| No multi-step email sequences | High — single touches don't convert | Sequence engine with delays |
| Basic reporting | Low | Add funnel + cohort analytics |

---

## 3. Architecture — AventisAI CRM (2026)

### High-Level Flow

```
┌─────────────────────────────────────────────────────────┐
│                  AVENTISAI CRM PLATFORM                  │
└─────────────────────────────────────────────────────────┘

   DISCOVERY                ENRICHMENT              SCORING
   ─────────                ──────────              ───────
   Google Places   ───┐
   Yelp API       ───┤      Email finder           AI ICP fit
   OSM Overpass    ───┤  →   Tech stack detect  →   Intent signals
   Existing scrapers──┤      Owner lookup            Priority assign
   Manual import  ───┘      Reviews/social          (Claude API)

                                  ↓

   ┌────────────────────────────────────────────────┐
   │           AVENTISAI DATABASE (SQLite/PG)        │
   │  leads  •  activities  •  emails  •  tasks  •   │
   │  pipelines  •  templates  •  campaigns          │
   └────────────────────────────────────────────────┘

                                  ↓

   OUTREACH                 TRACKING               CONVERT
   ────────                 ────────               ───────
   AI-personalized      Open/click/reply         Book call
   Multi-step sequence  Sentiment analysis    →   Hand-off tasks
   Gmail MCP send       Funnel analytics          Auto follow-ups
   Drip automation      Per-lead timeline         Pipeline move
```

### File Structure (After Rebuild)

```
leadgen/
├── app.py                   # Flask app — AventisAI branded
├── database.py              # DB layer (existing, upgraded schema)
├── pg_adapter.py            # PG/SQLite adapter (existing)
├── email_service.py         # Email service (upgraded for sequences)
├── ai_service.py            # NEW — Claude API wrapper for personalization + scoring
├── enrichment_service.py    # NEW — Lead enrichment pipeline
├── automation_engine.py     # NEW — Drip sequences + scheduled tasks
├── scrapers/
│   ├── google_places.py     # NEW/upgraded
│   ├── yelp.py              # NEW
│   ├── osm_overpass.py      # Existing
│   ├── website_enricher.py  # NEW — scrape websites for emails/tech
│   └── ...
├── templates/               # Rebranded AventisAI
│   ├── _layout.html
│   ├── dashboard.html
│   ├── leads.html
│   ├── lead_detail.html
│   ├── pipeline.html
│   ├── campaigns.html       # NEW — email sequences
│   ├── enrichment.html      # NEW — bulk enrichment status
│   └── ...
└── static/                  # CSS/JS — AventisAI theme

execution/
├── aventis_lead_finder.py   # NEW — multi-source lead discovery CLI
├── aventis_enrich.py        # NEW — bulk enrichment runner
├── aventis_outreach.py      # NEW — AI-personalized email sender
└── ...

directives/
└── aventis_crm.md           # NEW — SOP for the platform
```

### Database Schema Additions

```sql
-- New tables to support 2026 features
CREATE TABLE campaigns (
  id, name, status, target_segment_json, sequence_id, created_at
);

CREATE TABLE email_sequences (
  id, name, steps_json  -- [{delay_days, subject, body, condition}]
);

CREATE TABLE sequence_runs (
  id, lead_id, sequence_id, current_step, next_send_at, status
);

CREATE TABLE enrichment_jobs (
  id, lead_id, source, status, result_json, ran_at
);

CREATE TABLE lead_scores (
  lead_id, icp_fit, intent_signal, priority, reasoning, scored_at
);

-- Add to existing leads table
ALTER TABLE leads ADD COLUMN email_verified BOOLEAN;
ALTER TABLE leads ADD COLUMN tech_stack_json TEXT;
ALTER TABLE leads ADD COLUMN owner_name TEXT;
ALTER TABLE leads ADD COLUMN employee_count INT;
ALTER TABLE leads ADD COLUMN icp_score INT;
ALTER TABLE leads ADD COLUMN review_count INT;
ALTER TABLE leads ADD COLUMN review_rating REAL;
ALTER TABLE leads ADD COLUMN segment TEXT;
```

---

## 4. Build Plan — What I'm Doing Now

### Phase 1 (Now): Foundation + Lead Finder

1. ✅ Write this plan doc
2. ⏳ Build `execution/aventis_lead_finder.py` — multi-source lead discovery (Google Places + OSM + web scraping)
3. ⏳ Build `leadgen/enrichment_service.py` — website scraping for emails/phones/tech stack
4. ⏳ Update `database.py` schema with new fields
5. ⏳ Add AventisAI branding to templates

### Phase 2 (Next): AI Personalization

6. ⏳ Build `leadgen/ai_service.py` — Claude API wrapper for openers + scoring
7. ⏳ Build `execution/aventis_outreach.py` — AI-personalized cold email generator
8. ⏳ Upgrade `email_service.py` for sequence support

### Phase 3 (After): Automation + Polish

9. Build `leadgen/automation_engine.py` — drip sequences, scheduled tasks
10. Add campaign UI (new `templates/campaigns.html`)
11. Improve dashboard with funnel charts
12. Write `directives/aventis_crm.md` SOP

---

## 5. Configuration

### API Keys (.env)

```bash
# Free tier sufficient to start
GOOGLE_PLACES_API_KEY=     # Optional — uses $200/mo free credit
HUNTER_API_KEY=             # Optional — free 25/mo
ANTHROPIC_API_KEY=          # Required for AI features (~$5-20/mo for cold outreach)

# Already configured
GMAIL_MCP                   # Email sending
DATABASE_URL                # PostgreSQL on Railway
```

### Default ICP (Ideal Customer Profile) for AventisAI

```
- 5-50 employees
- Has a website (so they know the value of digital)
- Has Google Business listing
- Currently uses 3+ separate SaaS tools (CRM, email, booking)
- Reviews: 10+ Google reviews (established, not brand new)
- Located in MA/RI/CT to start (local trust)
- Industry: any service business (real estate, contractors, restaurants, salons, fitness, professional services)
```

Lead scoring weights:
- 30% — ICP fit (size, industry, geography)
- 25% — Pain signals (multiple tools, poor reviews, no chat widget)
- 20% — Buying signals (recently expanded, hiring, new website)
- 15% — Contactability (verified email, owner identified)
- 10% — Engagement potential (active social, responsive to reviews)
