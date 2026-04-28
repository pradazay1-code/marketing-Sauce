"""
Google Places API scraper for finding businesses without websites.
Requires GOOGLE_PLACES_API_KEY in .env file.

Free tier: $200/month credit covers ~7,000 requests = ~230/day.
"""

import os
import requests
import time
from collections import defaultdict
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("GOOGLE_PLACES_API_KEY", "")

SEARCH_CATEGORIES = [
    "restaurant", "barber shop", "hair salon", "beauty salon",
    "gym", "fitness center", "auto repair", "contractor",
    "landscaping", "tattoo", "bakery", "cafe",
    "cleaning service", "photography studio", "pet grooming",
    "florist", "daycare", "food truck", "nail salon",
    "massage", "yoga studio", "boxing gym", "mechanic",
]

TARGET_CITIES = {
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
    ],
    "RI": [
        ("Providence", 41.8240, -71.4128),
        ("Warwick", 41.7001, -71.4162),
        ("Cranston", 41.7798, -71.4373),
        ("Pawtucket", 41.8787, -71.3826),
        ("East Providence", 41.8137, -71.3701),
        ("Newport", 41.4901, -71.3128),
        ("Woonsocket", 42.0029, -71.5148),
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
    ],
}


def search_places(query, lat, lng, radius=8000):
    if not API_KEY:
        return [], "No GOOGLE_PLACES_API_KEY set in .env"

    url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
    params = {
        "key": API_KEY,
        "location": f"{lat},{lng}",
        "radius": radius,
        "keyword": query,
    }

    try:
        resp = requests.get(url, params=params, timeout=15)
        data = resp.json()

        if data.get("status") not in ("OK", "ZERO_RESULTS"):
            return [], data.get("status", "Unknown error")

        leads = []
        for place in data.get("results", []):
            name = place.get("name", "")
            address = place.get("vicinity", "")

            has_website = False
            website_url = ""
            phone = ""

            place_id = place.get("place_id")
            if place_id:
                detail = get_place_details(place_id)
                if detail:
                    has_website = bool(detail.get("website"))
                    website_url = detail.get("website", "")
                    phone = detail.get("formatted_phone_number", "")
                time.sleep(0.1)

            leads.append({
                "business_name": name,
                "address": address,
                "phone": phone,
                "has_website": int(has_website),
                "website_url": website_url,
            })

        return leads, ""

    except Exception as e:
        return [], str(e)


def get_place_details(place_id):
    if not API_KEY:
        return None

    url = "https://maps.googleapis.com/maps/api/place/details/json"
    params = {
        "key": API_KEY,
        "place_id": place_id,
        "fields": "website,formatted_phone_number,name,formatted_address",
    }

    try:
        resp = requests.get(url, params=params, timeout=10)
        data = resp.json()
        if data.get("status") == "OK":
            return data.get("result", {})
    except Exception:
        pass
    return None


def find_businesses_without_websites(state="MA", categories=None, max_per_city=10):
    """
    Search each city for each category, return only businesses without websites.
    """
    if categories is None:
        categories = SEARCH_CATEGORIES[:5]

    cities = TARGET_CITIES.get(state, TARGET_CITIES["MA"])
    all_leads = []
    seen_names = set()
    city_counts = defaultdict(int)

    for city_name, lat, lng in cities:
        for category in categories:
            if city_counts[city_name] >= max_per_city:
                break

            results, error = search_places(category, lat, lng)
            if error:
                continue

            for lead in results:
                if lead["has_website"]:
                    continue
                if lead["business_name"].lower() in seen_names:
                    continue
                if city_counts[city_name] >= max_per_city:
                    break

                seen_names.add(lead["business_name"].lower())
                city_counts[city_name] += 1
                lead["city"] = city_name
                lead["state"] = state
                lead["category"] = category.title()
                lead["source"] = "Google Places API"
                lead["marketing_score"] = 0
                lead["priority"] = "high" if lead.get("phone") else "medium"
                all_leads.append(lead)

            time.sleep(0.2)

    return all_leads


if __name__ == "__main__":
    if not API_KEY:
        print("Set GOOGLE_PLACES_API_KEY in .env to use this scraper.")
        print("Get a key at: https://console.cloud.google.com/apis/credentials")
        print("Enable 'Places API' and 'Places API (New)' in your project.")
        print("\nFree tier: $200/month credit covers ~7,000 requests.")
    else:
        print("Testing Google Places API...")
        leads = find_businesses_without_websites("MA", ["barber shop"], max_per_city=3)
        print(f"Found {len(leads)} businesses without websites")
        for lead in leads[:5]:
            print(f"  - {lead['business_name']} ({lead['city']}, {lead['state']}) Phone: {lead.get('phone', 'N/A')}")
