"""
Business age verifier — given a business name + state, returns its formation date.

Layered approach (tries cheapest/most reliable source first):
1. OpenCorporates API (free, aggregates all 50 state SOS registries)
2. Google Maps oldest review date (proxy for "first appeared online")
3. Yellow Pages "years in business" field (already in lead data)
4. State SOS direct scrape (MA + RI; CT requires Salesforce automation)

Returns:
    {
        "is_new": True | False | None,
        "formation_date": "2025-03-14" | None,
        "source": "OpenCorporates" | "GoogleMaps" | "YellowPages" | "MA_SOS" | None,
        "confidence": "high" | "medium" | "low" | "unknown",
        "raw_year": 2025 | None,
    }
"""

import re
import time
import requests
from datetime import datetime
from urllib.parse import quote_plus

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36 LeadPilot/1.0",
    "Accept": "application/json, text/html;q=0.9",
}

NEW_BUSINESS_YEARS = {2025, 2026}
CURRENT_YEAR = datetime.now().year


def _normalize_name(name):
    """Strip punctuation/suffixes for fuzzy matching."""
    if not name:
        return ""
    n = name.lower()
    for suffix in [" llc", " l.l.c.", " inc", " inc.", " corp", " corporation",
                   " co.", " ltd", " limited", " pllc", " pa", " pc", " lp"]:
        n = n.replace(suffix, "")
    return re.sub(r"[^a-z0-9]", "", n)


def _name_match(found, query, threshold=0.7):
    """Loose match — found contains query, or query contains found, or 70%+ char overlap."""
    f = _normalize_name(found)
    q = _normalize_name(query)
    if not f or not q:
        return False
    if q in f or f in q:
        return True
    common = sum(1 for c in q if c in f)
    return (common / max(len(q), 1)) >= threshold


def _parse_year(date_str):
    """Pull a 4-digit year out of any date string."""
    if not date_str:
        return None
    m = re.search(r"(20\d{2})", str(date_str))
    return int(m.group(1)) if m else None


def verify_via_opencorporates(name, state, timeout=10):
    """
    Query OpenCorporates for incorporation_date.
    Free tier: 50 req/month unauthenticated, 200/month with key.
    """
    url = "https://api.opencorporates.com/v0.4/companies/search"
    params = {
        "q": name,
        "jurisdiction_code": f"us_{state.lower()}",
        "per_page": 5,
        "order": "score",
    }
    try:
        resp = requests.get(url, params=params, headers=HEADERS, timeout=timeout)
        if resp.status_code == 403 or resp.status_code == 429:
            return None  # Rate limited
        if resp.status_code != 200:
            return None
        data = resp.json()
        results = data.get("results", {}).get("companies", [])
        for r in results:
            company = r.get("company", {})
            found_name = company.get("name", "")
            if not _name_match(found_name, name):
                continue
            inc_date = company.get("incorporation_date")
            year = _parse_year(inc_date)
            if year:
                return {
                    "is_new": year in NEW_BUSINESS_YEARS,
                    "formation_date": inc_date,
                    "source": "OpenCorporates",
                    "confidence": "high",
                    "raw_year": year,
                    "matched_name": found_name,
                    "company_url": company.get("opencorporates_url", ""),
                }
    except (requests.RequestException, ValueError):
        return None
    return None


def verify_via_google_maps(name, city, state, timeout=10):
    """
    Search Google Maps for the business and look at oldest review date.
    Proxy: if oldest review is 2025+, business is likely new.
    """
    query = f"{name} {city} {state}"
    url = f"https://www.google.com/search?q={quote_plus(query)}+reviews&tbm=lcl"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=timeout)
        if resp.status_code != 200:
            return None
        text = resp.text
        review_dates = re.findall(r"(\d+)\s+(?:year|month|week|day)s?\s+ago", text)
        if not review_dates:
            return None
        max_age_years = 0
        for amt in review_dates:
            n = int(amt)
            if n >= 2020 and n <= CURRENT_YEAR:
                max_age_years = max(max_age_years, CURRENT_YEAR - n)
        if max_age_years == 0 and review_dates:
            max_age_years = max(int(d) for d in review_dates if int(d) < 100)
        oldest_year = CURRENT_YEAR - max_age_years if max_age_years else None
        if oldest_year:
            return {
                "is_new": oldest_year in NEW_BUSINESS_YEARS,
                "formation_date": f"{oldest_year}-01-01",
                "source": "GoogleMaps",
                "confidence": "medium",
                "raw_year": oldest_year,
                "note": f"Oldest review ~{max_age_years}y ago",
            }
    except requests.RequestException:
        return None
    return None


def verify_via_yellowpages_years(years_in_business_text):
    """
    Parse YP 'years in business' string we already have on leads.
    e.g. 'YRS WITH 1' or '2 Years In Business' → year count.
    """
    if not years_in_business_text:
        return None
    m = re.search(r"(\d+)", str(years_in_business_text))
    if not m:
        return None
    years = int(m.group(1))
    formation_year = CURRENT_YEAR - years
    return {
        "is_new": formation_year in NEW_BUSINESS_YEARS,
        "formation_date": f"{formation_year}-01-01",
        "source": "YellowPages",
        "confidence": "low",
        "raw_year": formation_year,
        "note": f"YP self-report: {years} yrs in business",
    }


def verify_business_age(name, state, city="", years_in_business="", use_google=False):
    """
    Main entry point. Tries each source, returns first high-confidence hit.

    Args:
        name: business name (e.g. "Joe's Auto Repair LLC")
        state: 2-letter state code (e.g. "MA")
        city: optional, helps Google Maps fallback
        years_in_business: optional, YP self-report from existing lead data
        use_google: if True, will scrape Google as fallback (slower, riskier)

    Returns:
        Verification dict (see module docstring) or "unknown" stub.
    """
    if not name or not state:
        return {"is_new": None, "formation_date": None, "source": None,
                "confidence": "unknown", "raw_year": None}

    # 1. Try OpenCorporates (most reliable, free)
    result = verify_via_opencorporates(name, state)
    if result:
        return result

    # 2. Try YP self-report (already in lead data, free)
    if years_in_business:
        result = verify_via_yellowpages_years(years_in_business)
        if result and result.get("confidence") != "unknown":
            return result

    # 3. Optional Google fallback (rate limited, fragile)
    if use_google and city:
        result = verify_via_google_maps(name, city, state)
        if result:
            return result

    return {
        "is_new": None,
        "formation_date": None,
        "source": None,
        "confidence": "unknown",
        "raw_year": None,
    }


def filter_new_businesses(leads, max_results=None, use_google=False, sleep=0.6):
    """
    Filter a list of leads to only those formed in 2025/2026.
    Adds verification metadata to each lead.

    Args:
        leads: list of dicts with at least {business_name, state}
        max_results: stop after N verified-new leads
        use_google: enable Google Maps fallback (default False)
        sleep: seconds between API calls (rate limiting)
    """
    new_leads = []
    unknown_count = 0
    rejected_count = 0

    for i, lead in enumerate(leads):
        if max_results and len(new_leads) >= max_results:
            break

        result = verify_business_age(
            name=lead.get("business_name", ""),
            state=lead.get("state", ""),
            city=lead.get("city", ""),
            years_in_business=lead.get("years_in_business", ""),
            use_google=use_google,
        )

        if result.get("is_new") is True:
            lead["formation_date"] = result.get("formation_date")
            lead["age_source"] = result.get("source")
            lead["age_confidence"] = result.get("confidence")
            new_leads.append(lead)
        elif result.get("is_new") is False:
            rejected_count += 1
        else:
            unknown_count += 1

        time.sleep(sleep)

    return {
        "new_leads": new_leads,
        "stats": {
            "total_checked": i + 1 if leads else 0,
            "verified_new": len(new_leads),
            "verified_old": rejected_count,
            "unknown": unknown_count,
        },
    }


if __name__ == "__main__":
    test_cases = [
        ("Akira Real Estate", "MA", "Boston"),
        ("Dunkin Donuts", "MA", "Boston"),
        ("North Atlantic Tattoo", "MA", "New Bedford"),
    ]
    print("Testing business age verifier...\n")
    for name, state, city in test_cases:
        result = verify_business_age(name, state, city)
        print(f"{name} ({state})")
        print(f"  → is_new: {result.get('is_new')}")
        print(f"  → formation_date: {result.get('formation_date')}")
        print(f"  → source: {result.get('source')}")
        print(f"  → confidence: {result.get('confidence')}\n")
        time.sleep(1)
