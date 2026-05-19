# Directive: AventisAI CRM — Lead Generation & Outreach

## Goal
Operate the AventisAI CRM end-to-end: discover new business leads in target areas, enrich them with contact info and tech stack signals, score them for ICP fit, store in the CRM, and run AI-personalized outreach campaigns.

## System Components

| Component | Location | Purpose |
|-----------|----------|---------|
| **Lead Finder** | `execution/aventis_lead_finder.py` | Multi-source discovery (Google Places, OSM) + enrichment |
| **Outreach Engine** | `execution/aventis_outreach.py` | AI-personalized email generation + campaigns |
| **CRM Dashboard** | `leadgen/app.py` (Flask) | Web UI for leads, pipeline, reports |
| **Database** | `leadgen/database.py` | SQLite (local) / PostgreSQL (production) |
| **Email Templates** | `execution/aventis_outreach.py` → CAMPAIGNS dict | Multi-step sequence templates |

## Inputs

### For Lead Discovery
- City (e.g., "Boston", "Worcester")
- State (MA, RI, CT)
- Business type (optional: restaurant, salon, contractor, real_estate_agency, etc.)
- Count (default: 20)

### For Outreach
- Campaign key: `intro`, `followup_1`, `followup_2`, `breakup`
- Filter: `min_score`, `status`, `days_since`, `limit`

## API Keys (.env)

```bash
# Optional — better data quality
GOOGLE_PLACES_API_KEY=     # Free $200/mo credit (~11K lookups)
HUNTER_API_KEY=             # Free 25 email finds/mo

# Required for AI-personalized openers (recommended)
ANTHROPIC_API_KEY=          # ~$5-20/mo for 1000s of personalized emails

# Sender identity for cold emails
AVENTIS_SENDER_NAME=Pradip
AVENTIS_SENDER_EMAIL=pradip@aventismarketing.com
```

Without API keys, the system falls back to:
- OSM Overpass for discovery (free, lower quality)
- Template-based openers (no AI personalization)
- Demo mode for testing (`--demo` flag)

## Daily Workflow

### Morning: Discover New Leads
```bash
# Find 30 leads in target city, enrich with web scraping, score by ICP, save to CRM
python execution/aventis_lead_finder.py \
  --city Worcester --state MA --type restaurant \
  --count 30 --enrich --save-db
```

### Mid-day: Review + Approve Leads
1. Open the dashboard: `python leadgen/app.py` (or visit the Railway URL)
2. Go to **Leads** page
3. Filter by `priority=HIGH` and `status=new`
4. Mark unfit leads as `lost`, tag good ones with relevant labels

### Afternoon: Generate Outreach
```bash
# Generate AI-personalized intro emails for top 10 HIGH-score leads
python execution/aventis_outreach.py \
  --campaign intro --min-score 75 --limit 10

# Review the drafts JSON file before sending
cat clients/leads/outreach_drafts/intro_$(date +%F).json
```

### Send (with Approval)
After reviewing drafts:
```python
# Use Gmail MCP — for each approved draft:
mcp__gmail__send_message(
    to=draft["to_email"],
    subject=draft["subject"],
    body=draft["body"],
)
```

Or use the existing `execution/send_outlook_email.py` script.

### Mark as Contacted
```bash
# When you actually send the emails, log them in the CRM
python execution/aventis_outreach.py \
  --campaign intro --min-score 75 --limit 10 --mark-contacted
```

## Weekly Workflow

### Monday: Pipeline Review
- Open `/pipeline` page
- Review leads in `contacted` stage — any responses?
- Move responded leads to `qualified` or `proposal`
- Drag dead leads to `lost`

### Wednesday: Follow-up #1
```bash
# Send follow-up to leads contacted 3+ days ago with no response
python execution/aventis_outreach.py \
  --campaign followup_1 --status contacted --days-since 3 --limit 20
```

### Friday: Follow-up #2 (value-add)
```bash
# Send value-add follow-up to leads contacted 7+ days ago
python execution/aventis_outreach.py \
  --campaign followup_2 --status contacted --days-since 7 --limit 20
```

### After 14 days: Breakup Email
```bash
python execution/aventis_outreach.py \
  --campaign breakup --status contacted --days-since 14 --limit 50
```

## ICP (Ideal Customer Profile) for AventisAI

**Best fit:**
- 5-50 employees
- Has Google Business listing with 20+ reviews
- Uses 3+ separate SaaS tools (CRM + email + booking + chat)
- Located in MA/RI/CT (local trust)
- Service business: real estate, restaurants, contractors, salons, fitness, professional services

**Score weighting (0-100):**
- 30% — Geographic fit (MA/RI/CT primary)
- 25% — Pain signals (multiple SaaS tools we replace)
- 20% — Establishment (reviews, age, social presence)
- 15% — Contactability (email + phone + website)
- 10% — Engagement potential (active social, no chat widget = opportunity)

## Lead Sources

The finder uses sources in this fallback order:
1. **Google Places API** (if `GOOGLE_PLACES_API_KEY` set) — best quality, reviews + phone
2. **OpenStreetMap Overpass** — free, decent for restaurants/cafes/shops
3. **Demo data** (`--demo` flag) — for testing without external APIs

After discovery, every lead is enriched by:
1. **Website scraping** — emails, phones, social links, tech stack detection
2. **Hunter.io** (optional) — verified emails by domain
3. **AI scoring** (optional) — Claude qualifies fit with reasoning

## Tech Stack Detection (Pain Signals)

The system automatically detects these tools on a lead's website:
- HubSpot, Mailchimp, Constant Contact, ConvertKit, ActiveCampaign (email/CRM)
- Calendly (booking)
- Intercom, Drift, Tidio, Crisp (chat)
- ClickFunnels, Kajabi, Podia (funnels)
- WordPress, Squarespace, Wix, Shopify (CMS)

The more "pain tools" detected → the higher the ICP score → the better fit for AventisAI consolidation pitch.

## Campaign Sequences

| Campaign | Trigger | Tone |
|----------|---------|------|
| `intro` | Initial cold contact | Curious, specific, brief |
| `followup_1` | 3 days, no response | Direct, restated value |
| `followup_2` | 7 days, no response | Value-add (free idea, no pitch) |
| `breakup` | 14 days, no response | Polite, leave door open |

Each campaign has 3-5 subject line variants (rotated randomly to avoid spam filters) and a personalized first line generated by Claude (when API key set).

## Output Files

| File | Contents |
|------|----------|
| `leadgen/leads.db` | SQLite database (leads, activities, emails, etc.) |
| `clients/leads/aventis_leads_<city>_<date>.json` | Backup JSON exports from discovery |
| `clients/leads/outreach_drafts/<campaign>_<date>.json` | Generated email drafts for review |

## Troubleshooting

### "No leads found" in discovery
- External APIs may be blocked → try `--demo` mode first to confirm pipeline works
- Set `GOOGLE_PLACES_API_KEY` for reliable production data
- Check city is in `CITY_COORDS` dict (or let Nominatim geocode)

### Outreach generates generic openers
- Set `ANTHROPIC_API_KEY` to enable Claude personalization
- Make sure leads have been enriched (`--enrich` during discovery) so tech stack is detected

### Database errors
- Run `python leadgen/database.py` to initialize tables
- Check `DATABASE_URL` env var if using PostgreSQL
- Falls back to SQLite at `leadgen/leads.db` if PG connection fails

## Future Enhancements (Not Yet Built)

- [ ] Persist enrichment data (tech_stack, review_count) in dedicated DB columns
- [ ] Automation engine (cron jobs for daily discovery + sequence sending)
- [ ] Multi-inbox rotation for cold email warmup
- [ ] LinkedIn enrichment for owner names
- [ ] Reply detection + auto-routing to qualified stage
- [ ] Funnel analytics dashboard (open rates, reply rates, conversion)
- [ ] Webhook integrations (Slack notifications, calendar booking)
