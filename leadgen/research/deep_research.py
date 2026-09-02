"""Deep research orchestration.

Two entry points:

  research_lead(lead)          one business -> find site, scrape, audit, store
  discover_prospects(...)      industry + location -> new, deduped leads

Both are written to run inside a single serverless invocation, so each does a
bounded amount of work and reports what it did rather than looping until
finished. Callers batch them.
"""

import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from research import firecrawl_client as fc
from research import mapbox_client as mb
from research import industries as ind
from research.marketing_audit import audit, one_line_pitch
from research.dedupe import dedupe_batch, domain_key


def research_lead(lead, geocode=True, save=True):
    """Full research pass on one lead.

    1. Locate their website if the CRM does not already have one
    2. Scrape it
    3. Audit for marketing gaps
    4. Pull contact details off the page
    5. Geocode for the map
    6. Store everything

    Returns the audit result plus what was discovered. A business with no
    website still produces a complete result -- that absence is the strongest
    buying signal in the whole system.
    """
    from database import save_research, update_lead

    lead_id = lead.get("id")
    website = (lead.get("website_url") or "").strip()
    discovered = {"found_website": False, "contacts": {}, "geocoded": False}
    page, error = None, ""

    # ---- 1. find the site ------------------------------------------------
    if not website and fc.is_configured():
        hit = fc.find_official_site(
            lead.get("business_name", ""), lead.get("city", ""),
            lead.get("state", ""))
        if hit.get("url"):
            website = hit["url"]
            discovered["found_website"] = True
        elif hit.get("error"):
            error = hit["error"]

    # ---- 2. scrape -------------------------------------------------------
    if website and fc.is_configured():
        page = fc.scrape(website)
        if not page.get("ok"):
            error = page.get("error", "")
            # A site that will not load is a real finding, not a failed scan --
            # audit() treats a missing page the same as no page.
            page = None
        else:
            discovered["contacts"] = fc.extract_contacts(page)

    # ---- 3. audit --------------------------------------------------------
    lead_for_audit = dict(lead)
    if website:
        lead_for_audit["website_url"] = website
        lead_for_audit["has_website"] = 1
    result = audit(lead_for_audit, page)
    result["one_line_pitch"] = one_line_pitch(
        result, lead.get("business_name", "This business"))

    # ---- 4. write back ---------------------------------------------------
    if save and lead_id:
        updates = {}
        if discovered["found_website"] and website:
            updates["website_url"] = website
            updates["has_website"] = 1
            updates["domain"] = domain_key(website)
        elif website:
            updates["domain"] = domain_key(website)

        emails = discovered.get("contacts", {}).get("emails") or []
        if emails and not (lead.get("email") or "").strip():
            updates["email"] = emails[0]

        if not (lead.get("industry") or "").strip():
            updates["industry"] = ind.classify(
                lead.get("business_name"), lead.get("category"),
                lead.get("business_type"))

        # ---- 5. geocode --------------------------------------------------
        if geocode and mb.is_configured() and not lead.get("latitude"):
            g = mb.geocode_lead(lead)
            if g.get("ok"):
                updates["latitude"] = g["lat"]
                updates["longitude"] = g["lng"]
                discovered["geocoded"] = True

        if updates:
            update_lead(lead_id, updates, log_activity=False)

        save_research(lead_id, result, page=page,
                      contacts=discovered.get("contacts"), error=error)

    result["discovered"] = discovered
    result["website"] = website
    result["error"] = error
    return result


def research_batch(leads, geocode=True):
    """Research several leads, collecting per-lead errors rather than aborting."""
    out = []
    for lead in leads:
        try:
            r = research_lead(lead, geocode=geocode)
            out.append({
                "lead_id": lead.get("id"),
                "business_name": lead.get("business_name"),
                "score": r["marketing_need_score"],
                "grade": r["grade"],
                "top_gaps": r["top_gaps"],
                "ok": True,
            })
        except Exception as e:
            out.append({
                "lead_id": lead.get("id"),
                "business_name": lead.get("business_name"),
                "ok": False, "error": str(e)[:200],
            })
    return out


def discover_prospects(industry_key, city, state, limit=10,
                       exclude_with_website=False):
    """Find new businesses in an industry and location via Firecrawl search.

    Deduped against the entire existing CRM before anything is written, so a
    business you already contacted never reappears as a fresh lead.

    Returns counts plus the rejected duplicates and why, because "found 40,
    added 3" is only trustworthy if you can see what happened to the other 37.
    """
    from database import add_lead, all_lead_dedupe_fields

    if not fc.is_configured():
        return {"ok": False, "error": "FIRECRAWL_API_KEY is not set",
                "added": 0, "duplicates": [], "candidates": 0}

    terms = ind.search_terms(industry_key) or [industry_key.replace("_", " ")]
    label = ind.industry_label(industry_key)

    candidates, seen_urls = [], set()
    for term in terms[:3]:                       # bound the credit spend
        res = fc.search(f"{term} in {city}, {state}", limit=limit)
        if not res["ok"]:
            return {"ok": False, "error": res["error"], "added": 0,
                    "duplicates": [], "candidates": 0}
        for r in res["results"]:
            url = r["url"]
            dk = domain_key(url)
            if not dk or dk in seen_urls:
                continue
            # Directory pages describe many businesses, not one -- importing
            # them creates junk leads named "Top 10 Landscapers in Brockton".
            if any(d in dk for d in (
                    "yelp.com", "yellowpages.com", "bbb.org", "angi.com",
                    "thumbtack.com", "houzz.com", "facebook.com", "reddit.com",
                    "tripadvisor.com", "mapquest.com", "indeed.com",
                    "wikipedia.org", "youtube.com", "nextdoor.com")):
                continue
            seen_urls.add(dk)
            candidates.append({
                "business_name": _clean_name(r["title"]),
                "website_url": url,
                "domain": dk,
                "city": city,
                "state": state,
                "industry": industry_key,
                "category": label,
                "business_type": label,
                "has_website": 1,
                "source": f"Firecrawl: {term}",
                "date_found": datetime.now().date().isoformat(),
                "status": "new",
                "notes": (r.get("description") or "")[:400],
            })

    if exclude_with_website:
        candidates = [c for c in candidates if not c.get("website_url")]

    unique, dupes = dedupe_batch(candidates, all_lead_dedupe_fields())

    added = 0
    for lead in unique:
        try:
            if add_lead(lead):
                added += 1
        except Exception as e:
            print(f"[Discover] add_lead failed for "
                  f"{lead.get('business_name')}: {str(e)[:120]}")

    return {
        "ok": True,
        "error": "",
        "industry": industry_key,
        "industry_label": label,
        "location": f"{city}, {state}",
        "candidates": len(candidates),
        "added": added,
        "duplicates": [{"name": d[0]["business_name"], "reason": d[1]}
                       for d in dupes],
        "duplicate_count": len(dupes),
    }


def _clean_name(title):
    """Turn a search-result title into a plausible business name.

    Titles arrive as "Joe's Landscaping | Lawn Care in Brockton MA - Home".
    Everything after the first separator is site chrome.
    """
    if not title:
        return "Unknown"
    name = title.split("|")[0].split(" - ")[0].split("–")[0].strip()
    for suffix in ("Home", "Homepage", "Official Site", "Welcome"):
        if name.endswith(suffix) and len(name) > len(suffix) + 3:
            name = name[: -len(suffix)].strip(" -|")
    return (name or title)[:120]


def status():
    """Which research integrations are live — drives the UI banners."""
    return {
        "firecrawl": {
            "configured": fc.is_configured(),
            "env": "FIRECRAWL_API_KEY",
        },
        "mapbox": {
            "configured": mb.is_configured(),
            "env": "MAPBOX_ACCESS_TOKEN",
            "permanent": not os.getenv("MAPBOX_ALLOW_TEMPORARY"),
        },
    }
