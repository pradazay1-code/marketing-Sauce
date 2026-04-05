# Skill: Build Site

## Purpose
Generate a self-contained HTML website for a lead or client. Deploy to GitHub Pages.

## When to Use
- User says "build site", "create website", "make a site for [business]"
- Part of the full pipeline after leads are found

## Steps

1. **Get business info**
   - Read from `clients/leads/raw_leads.json` or accept manual input
   - Required: business_name, business_type, city, state
   - Optional: address, phone, description, services list

2. **Generate website**
   ```bash
   python .claude/skills/build-site/scripts/build_single_site.py \
     --name "Business Name" \
     --type "Restaurant" \
     --city "Boston" \
     --state "MA" \
     --output clients/leads/websites/business-name/index.html
   ```
   - Single self-contained HTML file (all CSS/JS inline)
   - Mobile responsive, SEO optimized
   - Unique color scheme per business type

3. **Deploy to GitHub Pages** (optional)
   - Push to `gh-pages` branch under `sites/{slug}/`
   - Live URL: `https://pradazay1-code.github.io/marketing-Sauce/sites/{slug}/`

4. **Verify**
   - File exists and is valid HTML
   - All styles inline (no external dependencies)

## Output
- `clients/leads/websites/{slug}/index.html`
- Optional: live GitHub Pages URL

## Rules
- ALL CSS must be inline in `<style>` tags
- ALL JS must be inline in `<script>` tags
- Use `<img src="images/...">` for portfolio images (user adds their own)
- No external CDN links
