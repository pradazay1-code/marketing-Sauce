---
description: Find small businesses in MA/RI/CT that need websites and marketing services
tools: WebSearch, Write, Bash
---

# Find Leads Skill

## What This Does
Finds small businesses without websites in Massachusetts, Rhode Island, and Connecticut. Outputs structured lead data to `clients/leads/raw_leads.json`.

## Steps

1. **Set target parameters**
   - State: MA (default), RI, or CT
   - Count: how many leads to find (default 15)
   - Business types: restaurants, barbershops, salons, contractors, retail shops, auto repair, bakeries, etc.

2. **Search for leads**
   - Use WebSearch to find "new businesses opened [city] [state] 2025"
   - Search "businesses without websites [city] [state]"
   - Search "[business type] [city] no website"
   - Focus on businesses that opened recently (2024-2026)

3. **For each lead, capture:**
   - Business name
   - Business type
   - City, State
   - Address (if found)
   - Phone (if found)
   - Owner name (if found)
   - Online presence (social media, Yelp, Google listing)
   - Website status (No Website, Social Only, Outdated)
   - Priority (HIGH/MEDIUM/LOW)

4. **Run the script**
   ```
   python execution/find_leads_web.py --state MA --count 15
   ```

5. **Output**
   - Save to `clients/leads/raw_leads.json`
   - Also generate Excel spreadsheet via `python execution/create_leads_spreadsheet.py`

## Edge Cases
- If WebSearch returns 529 errors, add 10-15 second delays between searches
- Deduplicate by business name + city
- Skip chains/franchises — focus on independent businesses only
- If no phone/owner found, mark as "N/A" not blank
