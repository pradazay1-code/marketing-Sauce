# Lead Scraper — Execution Layer

## Purpose
The actual execution logic for finding and scraping business leads.

## Execution Methods

### Method 1: Web Search Based
Use web search tools to find businesses matching criteria:
1. Search queries to use:
   - "[industry] businesses in [location]"
   - "[industry] near [location] hiring" (indicates growth)
   - "[industry] [location] new" (newly opened)
   - "[industry] without website [location]"
   - "best [industry] in [location]" (find ones with bad reviews)

2. For each result:
   - Extract business name, address, phone, website
   - Check website quality (load speed, mobile, design)
   - Check social media presence
   - Note any obvious marketing gaps

### Method 2: Directory Based
Scrape business directories:
- Google Maps / Google Business
- Yelp
- Better Business Bureau
- Industry-specific directories
- Local chamber of commerce

### Method 3: Social Media Based
Find businesses through social platforms:
- Instagram: Search location tags, industry hashtags
- LinkedIn: Search by industry and location
- Facebook: Search local business pages

## Data Points to Extract
```json
{
  "business_name": "",
  "industry": "",
  "location": "",
  "website": "",
  "website_score": "",
  "phone": "",
  "email": "",
  "owner_name": "",
  "social_media": {
    "instagram": "",
    "facebook": "",
    "linkedin": "",
    "tiktok": ""
  },
  "google_reviews": "",
  "review_score": "",
  "years_in_business": "",
  "pain_points": [],
  "lead_score": "",
  "source": "",
  "date_found": ""
}
```

## Website Quality Assessment
Score 1-10 based on:
- Design modernity (is it from 2010 or 2024?)
- Mobile responsiveness
- Load speed
- Clear CTA presence
- Professional imagery
- SSL certificate
- Contact info easily found
- SEO basics (meta titles, etc.)

Low scores = high opportunity for our services.

## Output
Formatted lead list saved to `memory/leads.md` following the standard lead entry format.
