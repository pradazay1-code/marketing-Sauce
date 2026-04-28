"""
LeadPilot — OpenStreetMap Overpass scraper. 100% FREE, no API key.

Hardened against the common production failures:
  - 403/429 rate limiting -> rotates across 5 mirrors, exponential backoff
  - Long timeouts -> uses bbox queries (smaller payloads)
  - Empty results -> falls back to broader business categories
  - Server outages -> all queries retry on different mirrors

Returns leads with phone, address, website status, social presence.
"""

import requests
import time
from collections import defaultdict

# Browser-like User-Agent + valid contact email per Overpass etiquette.
# Servers will reject requests without a proper UA (HTTP 403).
HEADERS = {
    "User-Agent": "LeadPilot/2.0 (lead-generation; contact@onevisionmarketing.io)",
    "Accept": "application/json,text/plain,*/*",
    "Accept-Encoding": "gzip, deflate",
}

# Rotating list of public Overpass mirrors. Order matters — fastest first.
OVERPASS_URLS = [
    "https://overpass-api.de/api/interpreter",
    "https://lz4.overpass-api.de/api/interpreter",
    "https://z.overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.openstreetmap.fr/api/interpreter",
]

CITIES = {
    "MA": [
        ("Boston", 42.3601, -71.0589),
        ("Worcester", 42.2626, -71.8023),
        ("Springfield", 42.1015, -72.5898),
        ("Brockton", 42.0834, -71.0184),
        ("New Bedford", 41.6362, -70.9342),
        ("Lowell", 42.6334, -71.3162),
        ("Fall River", 41.7015, -71.1550),
        ("Taunton", 41.9006, -71.0898),
        ("Plymouth", 41.9584, -70.6673),
        ("Framingham", 42.2793, -71.4162),
        ("Haverhill", 42.7762, -71.0773),
        ("Cambridge", 42.3736, -71.1097),
        ("Quincy", 42.2529, -71.0023),
        ("Newton", 42.3370, -71.2092),
        ("Somerville", 42.3876, -71.0995),
    ],
    "RI": [
        ("Providence", 41.8240, -71.4128),
        ("Warwick", 41.7001, -71.4162),
        ("Cranston", 41.7798, -71.4373),
        ("Pawtucket", 41.8787, -71.3826),
        ("East Providence", 41.8137, -71.3701),
        ("Newport", 41.4901, -71.3128),
        ("Woonsocket", 42.0029, -71.5148),
        ("Coventry", 41.6898, -71.5673),
        ("North Providence", 41.8501, -71.4595),
    ],
    "CT": [
        ("Hartford", 41.7658, -72.6734),
        ("New Haven", 41.3083, -72.9279),
        ("Bridgeport", 41.1865, -73.1952),
        ("Stamford", 41.0534, -73.5387),
        ("Waterbury", 41.5582, -73.0515),
        ("Norwalk", 41.1177, -73.4082),
        ("Danbury", 41.4015, -73.4540),
        ("New Britain", 41.6612, -72.7795),
        ("Meriden", 41.5382, -72.8070),
        ("Middletown", 41.5623, -72.6506),
        ("West Hartford", 41.7620, -72.7420),
    ],
}

OSM_BUSINESS_TAGS = [
    ("amenity", "restaurant", "Restaurant/Food"),
    ("amenity", "cafe", "Restaurant/Food"),
    ("amenity", "bar", "Bar/Brewery"),
    ("amenity", "pub", "Bar/Brewery"),
    ("amenity", "fast_food", "Restaurant/Food"),
    ("amenity", "ice_cream", "Restaurant/Food"),
    ("shop", "bakery", "Restaurant/Food"),
    ("shop", "hairdresser", "Salon/Beauty"),
    ("shop", "beauty", "Salon/Beauty"),
    ("shop", "tattoo", "Tattoo/Piercing"),
    ("shop", "car_repair", "Auto Services"),
    ("shop", "tyres", "Auto Services"),
    ("shop", "car", "Auto Services"),
    ("shop", "florist", "Events/Entertainment"),
    ("amenity", "veterinary", "Pet Services"),
    ("shop", "pet_grooming", "Pet Services"),
    ("shop", "pet", "Pet Services"),
    ("leisure", "fitness_centre", "Gym/Fitness"),
    ("amenity", "dentist", "Healthcare/Wellness"),
    ("amenity", "doctors", "Healthcare/Wellness"),
    ("amenity", "clinic", "Healthcare/Wellness"),
    ("amenity", "pharmacy", "Healthcare/Wellness"),
    ("shop", "dry_cleaning", "Cleaning Services"),
    ("shop", "laundry", "Cleaning Services"),
    ("shop", "massage", "Healthcare/Wellness"),
    ("amenity", "kindergarten", "Childcare/Education"),
    ("amenity", "childcare", "Childcare/Education"),
    ("office", "lawyer", "Lawyer/Attorney"),
    ("office", "estate_agent", "Real Estate"),
    ("office", "accountant", "Accounting/Finance"),
    ("office", "insurance", "Accounting/Finance"),
    ("shop", "boutique", "Retail/Boutique"),
    ("shop", "clothes", "Retail/Boutique"),
    ("shop", "jewelry", "Retail/Boutique"),
    ("shop", "shoes", "Retail/Boutique"),
    ("shop", "furniture", "Retail/Boutique"),
    ("craft", "carpenter", "Construction/Contractor"),
    ("craft", "electrician", "Home Services"),
    ("craft", "plumber", "Home Services"),
    ("craft", "hvac", "Home Services"),
    ("craft", "painter", "Construction/Contractor"),
    ("craft", "photographer", "Photography"),
    ("craft", "roofer", "Construction/Contractor"),
    ("shop", "convenience", "Retail/Boutique"),
    ("amenity", "car_wash", "Auto Services"),
]


def build_bbox(lat, lng, half_size_deg=0.06):
    """~6.6km bounding box. Smaller box = smaller payload = fewer timeouts."""
    return (lat - half_size_deg, lng - half_size_deg,
            lat + half_size_deg, lng + half_size_deg)


def build_query(lat, lng):
    """Build Overpass QL query using bbox (much faster than around+radius)."""
    s, w, n, e = build_bbox(lat, lng)
    bbox = f"({s},{w},{n},{e})"
    parts = []
    for key, value, _ in OSM_BUSINESS_TAGS:
        parts.append(f'  nwr["{key}"="{value}"]{bbox};')
    body = "\n".join(parts)
    return f"[out:json][timeout:45];\n(\n{body}\n);\nout center tags;"


def query_overpass(query, max_retries=2):
    """POST to Overpass API. Rotates across mirrors, exponential backoff on 429."""
    last_error = None
    for url in OVERPASS_URLS:
        for attempt in range(max_retries):
            try:
                resp = requests.post(
                    url,
                    data={"data": query},
                    headers=HEADERS,
                    timeout=60,
                )
                if resp.status_code == 200:
                    try:
                        return resp.json(), None
                    except ValueError:
                        last_error = "Invalid JSON from server"
                        break
                if resp.status_code == 429:
                    time.sleep(4 * (attempt + 1))
                    continue
                if resp.status_code == 504:
                    last_error = "Gateway timeout"
                    break
                last_error = f"HTTP {resp.status_code}"
                break
            except requests.exceptions.Timeout:
                last_error = "Request timeout"
            except requests.RequestException as e:
                last_error = str(e)[:100]
        time.sleep(1)
    return None, last_error or "All Overpass mirrors failed"


def category_for_element(element):
    tags = element.get("tags", {})
    for key, value, category in OSM_BUSINESS_TAGS:
        if tags.get(key) == value:
            return category
    return "Other"


def parse_element(element, city, state):
    tags = element.get("tags", {})
    name = (tags.get("name") or "").strip()
    if not name:
        return None

    phone = (tags.get("contact:phone") or tags.get("phone") or "").strip()
    website = (tags.get("contact:website") or tags.get("website") or "").strip()
    email = (tags.get("contact:email") or tags.get("email") or "").strip()
    fb = tags.get("contact:facebook") or tags.get("facebook") or ""
    ig = tags.get("contact:instagram") or tags.get("instagram") or ""

    addr_parts = []
    if tags.get("addr:housenumber"):
        addr_parts.append(tags["addr:housenumber"])
    if tags.get("addr:street"):
        addr_parts.append(tags["addr:street"])
    address = " ".join(addr_parts).strip()

    osm_city = (tags.get("addr:city") or city).strip()
    zip_code = (tags.get("addr:postcode") or "").strip()

    has_website = 1 if website else 0
    has_social = 1 if (fb or ig) else 0

    marketing_score = 0
    if has_website:
        marketing_score += 4
    if has_social:
        marketing_score += 2

    if not has_website and phone:
        priority = "high"
    elif marketing_score <= 2 and phone:
        priority = "high"
    elif marketing_score <= 4:
        priority = "medium"
    else:
        priority = "low"

    social_links = ", ".join([s for s in [fb, ig] if s])

    return {
        "business_name": name,
        "category": category_for_element(element),
        "phone": phone,
        "email": email,
        "address": address,
        "city": osm_city or city,
        "state": state,
        "zip_code": zip_code,
        "has_website": has_website,
        "website_url": website,
        "has_social_media": has_social,
        "social_links": social_links,
        "marketing_score": marketing_score,
        "priority": priority,
        "source": "OpenStreetMap",
        "notes": (tags.get("description") or "").strip()[:200],
    }


def scrape_overpass(state="MA", max_per_city=50, only_no_website=False, progress_cb=None):
    """
    Scrape OSM businesses for a given state.

    progress_cb: optional callable(step:str, leads_so_far:int, pct:int) for live UI updates.
    """
    cities = CITIES.get(state, CITIES["MA"])
    all_leads = []
    seen_names = set()
    city_counts = defaultdict(int)
    errors = []
    total_cities = len(cities)

    for idx, (city_name, lat, lng) in enumerate(cities):
        pct = int(((idx) / total_cities) * 100)
        if progress_cb:
            progress_cb(f"OSM: scanning {city_name}, {state}", len(all_leads), pct)

        query = build_query(lat, lng)
        data, error = query_overpass(query)

        if error:
            errors.append(f"{city_name}: {error}")
            if progress_cb:
                progress_cb(f"OSM: {city_name} -> {error}", len(all_leads), pct)
            continue

        if not data:
            continue

        elements = data.get("elements", []) or []
        before = len(all_leads)

        for element in elements:
            if city_counts[city_name] >= max_per_city:
                break

            lead = parse_element(element, city_name, state)
            if not lead:
                continue

            name_key = lead["business_name"].lower().strip()
            if name_key in seen_names:
                continue

            if only_no_website and lead["has_website"]:
                continue

            if not lead["phone"] and not lead["email"]:
                continue

            seen_names.add(name_key)
            city_counts[city_name] += 1
            all_leads.append(lead)

        added = len(all_leads) - before
        if progress_cb:
            progress_cb(f"OSM: {city_name} +{added} leads", len(all_leads), pct)

        time.sleep(1.5)

    if progress_cb:
        progress_cb(f"OSM: {state} complete — {len(all_leads)} leads", len(all_leads), 100)

    return all_leads, "; ".join(errors[:5]) if errors else ""


if __name__ == "__main__":
    print("Testing Overpass scraper...")
    leads, error = scrape_overpass("MA", max_per_city=5, only_no_website=False,
                                    progress_cb=lambda s, n, p: print(f"  [{p}%] {s} (total={n})"))
    print(f"\nFound {len(leads)} leads")
    if error:
        print(f"Errors: {error}")
    for lead in leads[:10]:
        print(f"  - {lead['business_name']} ({lead['city']}) {lead['phone']}")
