---
description: Generate self-contained HTML websites for leads or clients
tools: Bash, Write, Read
---

# Build Site Skill

## What This Does
Generates professional, mobile-friendly, self-contained HTML websites for leads from `raw_leads.json` or for individual clients.

## Single Site
```bash
python .claude/skills/build-site/scripts/build_single_site.py \
  --name "Joe's Barbershop" \
  --type "Barbershop" \
  --city "Boston" \
  --state "MA"
```

## Batch (All Leads)
```bash
python .claude/skills/build-site/scripts/build_single_site.py \
  --batch clients/leads/raw_leads.json
```

## Steps

1. **Read lead data** from `clients/leads/raw_leads.json` or CLI args
2. **Generate HTML** — single self-contained file with:
   - All CSS inline (no external stylesheets)
   - Mobile responsive design
   - Unique color scheme per business type
   - Sections: Nav, Hero, About, Services, Hours, CTA, Footer
   - `<img src="images/...">` tags for photos (user adds their own)
3. **Save to** `clients/leads/websites/{slug}/index.html`
4. **Deploy** to GitHub Pages (optional, on user request)

## Website Requirements
- Single HTML file, fully self-contained
- Mobile-first responsive design
- SEO meta tags (title, description)
- Clean, professional look
- Contact section with placeholder phone/email
- Google Maps embed placeholder

## Output
- `clients/leads/websites/{business-slug}/index.html`
