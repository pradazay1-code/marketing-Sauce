# Directive: SEO Audit

## Goal
Analyze a client's website for SEO issues and generate a report with actionable fixes.

## Inputs
- Client name
- Website URL or local HTML file path

## Process
1. Read the client's HTML file
2. Check for these SEO elements:
   - Title tag (exists, length 50-60 chars)
   - Meta description (exists, length 150-160 chars)
   - H1 tag (exactly one)
   - H2/H3 hierarchy (proper nesting)
   - Image alt tags (all images have alt text)
   - Mobile viewport meta tag
   - Open Graph tags (og:title, og:description, og:image)
   - Canonical URL
   - Schema markup (LocalBusiness)
   - Page load considerations (inline CSS vs external, image optimization notes)
   - Internal/external link structure
3. Score each item as PASS / FAIL / WARNING
4. Generate fix recommendations

## Output
- SEO report saved to `clients/{client-name}/seo-report.md`
- Summary with score (X/12 checks passed)

## Script
- `execution/seo_audit.py`
