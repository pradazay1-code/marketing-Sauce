# Skill: Find Leads

## Purpose
Find small businesses in MA/RI/CT that need websites or marketing help. Output a structured leads spreadsheet.

## When to Use
- User says "find leads", "get leads", "find businesses", "prospect"
- Part of the full pipeline

## Steps

1. **Set parameters**
   - State: default MA (accept RI, CT)
   - Count: default 15 (max 50 per run to stay efficient)
   - Types: restaurants, barbershops, retail shops, bakeries, salons, contractors, etc.

2. **Run lead finder script**
   ```bash
   python execution/find_leads_web.py --state MA --count 15
   ```
   - Script uses WebSearch to find newly opened businesses without websites
   - Outputs JSON to `clients/leads/raw_leads.json`

3. **Generate spreadsheet**
   ```bash
   python execution/create_leads_spreadsheet.py
   ```
   - Reads `raw_leads.json` and outputs formatted Excel to `clients/leads/`

4. **Verify output**
   - Check spreadsheet has correct columns: No., Business Name, Type, City, State, Address, Phone, Online Presence, Website Status, Notes, Priority
   - Confirm no duplicates with existing leads

## Output
- `clients/leads/leads_YYYY-MM-DD.xlsx`
- `clients/leads/raw_leads.json`

## Edge Cases
- WebSearch rate limits: add 5s delay between searches
- Duplicate leads: check against existing spreadsheets before adding
- No results for a category: skip and try next category
