"""
LeadPilot — Nominatim search-based scraper. 100% FREE, no API key.

Uses OpenStreetMap's Nominatim search API to find businesses by category+city.
This is a reliable fallback when Overpass is rate-limited because:
  - Different infrastructure than Overpass (separate rate limits)
  - HTTP GET with simple query string (caches well)
  - Returns OSM IDs that we can then fetch details for via Overpass

Etiquette: max 1 req/sec, must include User-Agent with contact email.
"""

import requests
import time

HEADERS = {
    "User-Agent": "LeadPilot/2.0 (lead-generation; contact@onevisionmarketing.io)",
    "Accept": "application/json",
}

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"

SEARCH_TERMS = [
    ("restaurant", "Restaurant/Food"),
    ("cafe", "Restaurant/Food"),
    ("barber shop", "Barbershop"),
    ("hair salon", "Salon/Beauty"),
    ("nail salon", "Salon/Beauty"),
    ("auto repair", "Auto Services"),
    ("landscaping", "Landscaping"),
    ("contractor", "Construction/Contractor"),
    ("tattoo", "Tattoo/Piercing"),
    ("photographer", "Photography"),
    ("gym", "Gym/Fitness"),
    ("bakery", "Restaurant/Food"),
    ("florist", "Events/Entertainment"),
    ("attorney", "Lawyer/Attorney"),
    ("real estate", "Real Estate"),
    ("plumber", "Home Services"),
    ("electrician", "Home Services"),
    ("dentist", "Healthcare/Wellness"),
    ("massage", "Healthcare/Wellness"),
    ("pet grooming", "Pet Services"),
    ("dry cleaner", "Cleaning Services"),
    ("boutique", "Retail/Boutique"),
    ("jewelry", "Retail/Boutique"),
]

CITIES_BY_STATE = {
    "MA": ["Boston", "Worcester", "Springfield", "Cambridge", "Lowell",
           "New Bedford", "Brockton", "Quincy", "Newton", "Somerville",
           "Fall River", "Framingham", "Plymouth"],
    "RI": ["Providence", "Warwick", "Cranston", "Pawtucket", "Newport",
           "Woonsocket", "East Providence"],
    "CT": ["Hartford", "New Haven", "Bridgeport", "Stamford", "Waterbury",
           "Norwalk", "Danbury", "New Britain", "Meriden"],
}

STATE_NAMES = {"MA": "Massachusetts", "RI": "Rhode Island", "CT": "Connecticut"}


def nominatim_search(query, limit=15):
    params = {
        "q": query,
        "format": "json",
        "limit": limit,
        "addressdetails": 1,
        "extratags": 1,
        "namedetails": 1,
        "countrycodes": "us",
    }
    try:
        resp = requests.get(NOMINATIM_URL, params=params, headers=HEADERS, timeout=20)
        if resp.status_code == 200:
            return resp.json(), None
        return [], f"HTTP {resp.status_code}"
    except requests.RequestException as e:
        return [], str(e)[:100]


def parse_result(item, fallback_city, state, our_category):
    extratags = item.get("extratags", {}) or {}
    namedetails = item.get("namedetails", {}) or {}
    addr = item.get("address", {}) or {}

    name = namedetails.get("name") or item.get("display_name", "").split(",")[0].strip()
    if not name or len(name) < 2:
        return None

    phone = (extratags.get("contact:phone") or extratags.get("phone") or "").strip()
    website = (extratags.get("contact:website") or extratags.get("website") or "").strip()
    email = (extratags.get("contact:email") or extratags.get("email") or "").strip()

    # Skip results with no contact info — can't outreach to them
    if not phone and not email and not website:
        return None

    fb = extratags.get("contact:facebook") or extratags.get("facebook") or ""
    ig = extratags.get("contact:instagram") or extratags.get("instagram") or ""

    house = addr.get("house_number", "")
    street = addr.get("road", "")
    address = f"{house} {street}".strip()
    city = addr.get("city") or addr.get("town") or addr.get("village") or fallback_city
    zip_code = addr.get("postcode", "")

    has_website = 1 if website else 0
    has_social = 1 if (fb or ig) else 0

    marketing_score = 0
    if has_website:
        marketing_score += 4
    if has_social:
        marketing_score += 2

    if not has_website and phone:
        priority = "high"
    elif marketing_score <= 2:
        priority = "high"
    elif marketing_score <= 4:
        priority = "medium"
    else:
        priority = "low"

    return {
        "business_name": name,
        "category": our_category,
        "phone": phone,
        "email": email,
        "address": address,
        "city": city,
        "state": state,
        "zip_code": zip_code,
        "has_website": has_website,
        "website_url": website,
        "has_social_media": has_social,
        "social_links": ", ".join(s for s in [fb, ig] if s),
        "marketing_score": marketing_score,
        "priority": priority,
        "source": "Nominatim/OSM",
        "notes": "",
    }


def scrape_nominatim(state="MA", max_per_query=10, only_no_website=False, progress_cb=None):
    cities = CITIES_BY_STATE.get(state, CITIES_BY_STATE["MA"])
    state_name = STATE_NAMES.get(state, state)
    all_leads = []
    seen = set()
    errors = []

    total = len(cities) * len(SEARCH_TERMS[:8])  # cap to first 8 terms per city
    done = 0

    for city in cities:
        for term, category in SEARCH_TERMS[:8]:
            done += 1
            pct = int((done / max(total, 1)) * 100)
            if progress_cb:
                progress_cb(f"Nominatim: {term} in {city}, {state}", len(all_leads), pct)

            query = f"{term} in {city}, {state_name}"
            results, error = nominatim_search(query, limit=max_per_query)

            if error:
                errors.append(f"{city}/{term}: {error}")
                time.sleep(1.2)
                continue

            for item in results:
                lead = parse_result(item, city, state, category)
                if not lead:
                    continue

                if only_no_website and lead["has_website"]:
                    continue

                key = lead["business_name"].lower().strip()
                if key in seen:
                    continue
                seen.add(key)
                all_leads.append(lead)

            time.sleep(1.1)  # respect 1 req/sec etiquette

    if progress_cb:
        progress_cb(f"Nominatim: {state} complete — {len(all_leads)} leads",
                    len(all_leads), 100)

    return all_leads, "; ".join(errors[:5]) if errors else ""


if __name__ == "__main__":
    leads, err = scrape_nominatim("MA", max_per_query=5, only_no_website=False,
                                   progress_cb=lambda s, n, p: print(f"[{p}%] {s} ({n})"))
    print(f"Found {len(leads)} leads")
    for l in leads[:10]:
        print(f"  - {l['business_name']} | {l['phone']} | {l['city']}")
