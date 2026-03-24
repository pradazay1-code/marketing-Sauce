# Lead Generation SOP

## When to Use
Invoked whenever the user asks to find leads, prospects, potential clients, or businesses to reach out to.

## Target Client Profile
- Small to medium businesses that need marketing help
- Businesses with weak or no online presence (bad website, no social media, no ads)
- Local businesses in growth mode (new locations, expanding services)
- E-commerce brands looking to scale
- Businesses currently running ads poorly (wasting budget)

## Tools Required
- Web search (for finding businesses)
- Website analysis (checking their current online presence)
- Social media scanning (checking their social accounts)
- Contact info extraction (finding emails, phone numbers)
- CRM/leads.md (storing qualified leads)

## Step-by-Step Process

### Step 1: Define Search Criteria
- Ask the user for: industry, location, size, and any specific requirements
- If not specified, use defaults from `memory/owner-profile.md`

### Step 2: Find Potential Leads
- Search for businesses matching criteria
- Look for businesses with signs they need marketing help:
  - Outdated or no website
  - Low social media presence
  - No Google Ads or poorly running ads
  - Bad reviews mentioning poor marketing/branding
  - Recently opened businesses (need initial marketing push)

### Step 3: Qualify Each Lead
For each potential lead, gather:
- [ ] Business name
- [ ] Industry/niche
- [ ] Location
- [ ] Website URL (or note if none exists)
- [ ] Social media profiles
- [ ] Contact info (email, phone, decision-maker name)
- [ ] Current marketing assessment (1-10 scale)
- [ ] Pain points identified
- [ ] Estimated deal size potential (small/medium/large)
- [ ] Confidence score (how likely they are to need our services)

### Step 4: Score and Rank
- Score each lead based on:
  - Need level (how badly they need marketing help): 1-10
  - Accessibility (how easy to reach decision-maker): 1-10
  - Deal potential (estimated revenue from client): 1-10
  - Fit (how well they match our ideal client): 1-10
- Total score out of 40, rank leads by score

### Step 5: Save to Pipeline
- Add qualified leads to `memory/leads.md`
- Include all gathered information
- Set status to "New Lead"
- Tag with source and date found

### Step 6: Prepare Outreach
- For top-scored leads, auto-generate personalized outreach drafts
- Save drafts using outreach templates from `templates/`
- Flag leads ready for outreach in the pipeline

## Quality Checks
- [ ] Each lead has a real, verified business
- [ ] Contact info is accurate and up-to-date
- [ ] No duplicate leads in the pipeline
- [ ] Personalization notes are specific (not generic)
- [ ] Pain points are based on actual observations, not assumptions

## Output Format
```
### Lead: [Business Name]
- **Industry:** [industry]
- **Location:** [city, state]
- **Website:** [url or "None"]
- **Contact:** [name, email, phone]
- **Marketing Score:** [1-10] — [brief assessment]
- **Pain Points:** [specific observations]
- **Recommended Approach:** [personalized suggestion]
- **Lead Score:** [X/40]
- **Status:** New Lead
```

## Notes
- Aim for 10-50 leads per search session depending on scope
- Always prioritize quality over quantity
- Update this SOP as we learn what types of leads convert best
