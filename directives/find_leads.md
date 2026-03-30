# Directive: Find Leads (Small Businesses Without Websites)

## Goal
Find small businesses and startups in Massachusetts, Rhode Island, and Connecticut that either have no website or were recently created. Output a spreadsheet with contact info, owner details, and business overview.

## Target Profile
- **Geography:** MA, RI, CT
- **Business size:** Small/local — no chains, no franchises
- **Key filter:** No website OR newly registered businesses
- **Categories:** Restaurants, salons, barbershops, contractors, landscaping, auto repair, cleaning services, tattoo shops, photography, catering, fitness studios, pet services, tutoring, handyman, florists, bakeries, food trucks, daycare, event planning, and more

## Data Sources (Free)
1. **Secretary of State — New Business Filings**
   - MA: https://corp.sec.state.ma.us/corpweb/CorpSearch/CorpSearch.aspx
   - RI: https://business.sos.ri.gov/
   - CT: https://business.ct.gov/
   - These show recently registered businesses (LLCs, DBAs, etc.)

2. **Yellow Pages / YP.com**
   - Search by category + city
   - Filter for listings without website URLs

3. **Yelp**
   - Search by category + location
   - Filter for businesses without website links

4. **Google Maps (no API needed)**
   - Search via web scraping
   - Look for businesses with no website listed

## Execution
- **Script:** `execution/find_leads.py`
- **Output:** `clients/leads/leads_YYYY-MM-DD.xlsx`

## Output Columns
| Column | Description |
|--------|-------------|
| Business Name | Name of the business |
| Category | Type of business (restaurant, salon, etc.) |
| Description | Brief overview of what they do |
| Phone | Phone number |
| Owner Name | Owner/principal name (from SOS filings if available) |
| Address | Street address |
| City | City |
| State | MA, RI, or CT |
| Has Website | Yes/No |
| Website URL | URL if they have one (to verify) |
| Source | Where the lead was found |
| Date Found | Date the lead was pulled |
| Notes | Any additional context |

## Edge Cases & Lessons Learned
- Rate limit all requests (2-3 second delays between requests)
- Some businesses may have a Facebook page but no real website — these are still leads
- Verify phone numbers are 10 digits
- Skip results that look like national chains (McDonald's, Subway, etc.)
- SOS filings may not have phone numbers — cross-reference with YP/Yelp
