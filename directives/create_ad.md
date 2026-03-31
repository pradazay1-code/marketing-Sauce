# Directive: Create Advertisement

## Goal
Generate ad copy for a client across multiple platforms (Google Ads, Facebook, Instagram).

## Inputs
- Client name
- Service/product to advertise
- Target audience
- Budget range (optional)
- Platform (google, facebook, instagram, or all)

## Process
1. Read client info from `clients/{client-name}/CLIENT_SUMMARY.md`
2. Read agency tone from `context/agency.md`
3. Generate ad copy for each platform:
   - **Google Ads:** Headline (30 chars), Description (90 chars), Display URL
   - **Facebook:** Primary text, Headline, Description, CTA
   - **Instagram:** Caption (with hashtags), CTA
4. Include targeting suggestions (location, age, interests)

## Output
- Ad copy saved to `clients/{client-name}/ads/ad-campaign-YYYY-MM-DD.md`

## Notes
- Keep copy short and action-oriented
- Always include a clear CTA (Call Now, Get Quote, Visit Website)
- Use local language (mention city/state)
- Avoid superlatives that can't be proven ("best", "#1")
