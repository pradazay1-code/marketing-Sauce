"""
OpenStreetMap Overpass API scraper — 100% FREE, no API key required.

Returns local businesses with phone numbers, addresses, websites.
Better than Google Places for our use case because:
- Completely free (community-maintained data)
- No rate limits beyond fair use (~10k requests/day)
- Returns websites + phone in single request (no detail call needed)
- Coverage is comparable in MA/RI/CT for established businesses

Docs: https://wiki.openstreetmap.org/wiki/Overpass_API
"""

import requests
import time
from collections import defaultdict

OVERPASS_URLS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.openstreetmap.ru/api/interpreter",
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
    ("shop", "bakery", "Restaurant/Food"),
    ("shop", "hairdresser", "Salon/Beauty"),
    ("shop", "beauty", "Salon/Beauty"),
    ("shop", "tattoo", "Tattoo/Piercing"),
    ("shop", "car_repair", "Auto Services"),
    ("shop", "florist", "Events/Entertainment"),
    ("amenity", "veterinary", "Pet Services"),
    ("shop", "pet_grooming", "Pet Services"),
    ("leisure", "fitness_centre", "Gym/Fitness"),
    ("amenity", "dentist", "Healthcare/Wellness"),
    ("amenity", "doctors", "Healthcare/Wellness"),
    ("amenity", "clinic", "Healthcare/Wellness"),
    ("shop", "dry_cleaning", "Cleaning Services"),
    ("shop", "laundry", "Cleaning Services"),
    ("shop", "massage", "Healthcare/Wellness"),
    ("amenity", "kindergarten", "Childcare/Education"),
    ("amenity", "childcare", "Childcare/Education"),
    ("office", "lawyer", "Lawyer/Attorney"),
    ("office", "estate_agent", "Real Estate"),
    ("office", "accountant", "Other"),
    ("shop", "boutique", "Retail/Boutique"),
    ("shop", "clothes", "Retail/Boutique"),
    ("shop", "jewelry", "Retail/Boutique"),
    ("shop", "shoes", "Retail/Boutique"),
    ("craft", "carpenter", "Construction/Contractor"),
    ("craft", "electrician", "Home Services"),
    ("craft", "plumber", "Home Services"),
    ("craft", "hvac", "Home Services"),
    ("craft", "painter", "Construction/Contractor"),
    ("craft", "photographer", "Photography"),
]


def build_query(lat, lng, radius_meters=8000):
    """Build Overpass QL query for businesses within radius of point."""
    tag_queries = []
    for key, value, _ in OSM_BUSINESS_TAGS:
        tag_queries.append(f'  node["{key}"="{value}"](around:{radius_meters},{lat},{lng});')
        tag_queries.append(f'  way["{key}"="{value}"](around:{radius_meters},{lat},{lng});')

    return f"""
[out:json][timeout:60];
(
{chr(10).join(tag_queries)}
);
out center tags;
""".strip()


def query_overpass(query, max_retries=3):
    """Query Overpass API with fallback servers and retry logic."""
    last_error = None
    for url in OVERPASS_URLS:
        for attempt in range(max_retries):
            try:
                resp = requests.post(url, data={"data": query}, timeout=90)
                if resp.status_code == 200:
                    return resp.json(), None
                if resp.status_code == 429:
                    time.sleep(5 * (attempt + 1))
                    continue
                last_error = f"HTTP {resp.status_code}"
            except requests.RequestException as e:
                last_error = str(e)
                time.sleep(2)
        time.sleep(1)
    return None, last_error or "All Overpass servers failed"


def category_for_element(element):
    tags = element.get("tags", {})
    for key, value, category in OSM_BUSINESS_TAGS:
        if tags.get(key) == value:
            return category
    return "Other"


def parse_element(element, city, state):
    """Convert OSM element to lead dict."""
    tags = element.get("tags", {})
    name = tags.get("name", "").strip()
    if not name:
        return None

    phone = (tags.get("contact:phone") or tags.get("phone") or "").strip()
    website = (tags.get("contact:website") or tags.get("website") or "").strip()
    email = (tags.get("contact:email") or tags.get("email") or "").strip()

    addr_parts = []
    if tags.get("addr:housenumber"):
        addr_parts.append(tags["addr:housenumber"])
    if tags.get("addr:street"):
        addr_parts.append(tags["addr:street"])
    address = " ".join(addr_parts).strip()

    osm_city = tags.get("addr:city", city).strip()
    zip_code = tags.get("addr:postcode", "").strip()

    has_website = 1 if website else 0
    has_social = 1 if (tags.get("contact:facebook") or tags.get("contact:instagram")) else 0

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
        "marketing_score": marketing_score,
        "priority": priority,
        "source": "OpenStreetMap Overpass",
        "notes": f"Found via OSM. {tags.get('description', '')}".strip(),
    }


def scrape_overpass(state="MA", max_per_city=50, only_no_website=False):
    """
    Scrape businesses from OpenStreetMap for a given state.
    Returns leads with phone numbers prioritized.
    """
    cities = CITIES.get(state, CITIES["MA"])
    all_leads = []
    seen_names = set()
    city_counts = defaultdict(int)
    errors = []

    for city_name, lat, lng in cities:
        if city_counts[city_name] >= max_per_city:
            continue

        query = build_query(lat, lng, radius_meters=6000)
        data, error = query_overpass(query)

        if error:
            errors.append(f"{city_name}: {error}")
            continue

        if not data:
            continue

        for element in data.get("elements", []):
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

            if not lead["phone"]:
                continue

            seen_names.add(name_key)
            city_counts[city_name] += 1
            all_leads.append(lead)

        time.sleep(2)

    return all_leads, "; ".join(errors) if errors else ""


if __name__ == "__main__":
    print("Testing Overpass API scraper (FREE — no API key needed)...")
    leads, error = scrape_overpass("MA", max_per_city=5, only_no_website=True)
    print(f"\nFound {len(leads)} leads without websites in MA")
    if error:
        print(f"Errors: {error}")
    for lead in leads[:10]:
        print(f"  - {lead['business_name']} ({lead['city']}, {lead['state']}) Phone: {lead['phone']}")
