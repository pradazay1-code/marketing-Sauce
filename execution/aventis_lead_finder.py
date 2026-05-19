#!/usr/bin/env python3
"""
AventisAI Lead Finder — Multi-Source Lead Discovery & Enrichment

Finds businesses in a target area, enriches with contact info, tech stack,
reviews, and AI-scored ICP fit. Stores directly in the CRM database.

Sources (in priority order):
  1. Google Places API (if GOOGLE_PLACES_API_KEY set) — highest quality
  2. OpenStreetMap Overpass — free, geo-based
  3. Yelp public pages — free fallback

Enrichment:
  - Website scraping for emails, phones, social links
  - Tech stack detection (HubSpot, Mailchimp, Calendly, etc.)
  - Google reviews count + rating (via Places API)
  - AI ICP scoring (if ANTHROPIC_API_KEY set)

Usage:
  python execution/aventis_lead_finder.py --city Boston --state MA --count 20
  python execution/aventis_lead_finder.py --city Worcester --state MA --type "restaurant" --count 10
  python execution/aventis_lead_finder.py --city Providence --state RI --enrich --score
"""

import argparse
import json
import os
import re
import sys
import time
from datetime import date, datetime
from urllib.parse import quote, urlparse

import requests
from bs4 import BeautifulSoup

# Allow imports from leadgen/
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, os.path.join(PROJECT_ROOT, "leadgen"))

try:
    from database import add_lead, get_db, init_db
    HAS_DB = True
except Exception as e:
    print(f"[WARN] Could not import database module: {e}")
    HAS_DB = False

GOOGLE_PLACES_KEY = os.environ.get("GOOGLE_PLACES_API_KEY", "")
HUNTER_KEY = os.environ.get("HUNTER_API_KEY", "")
ANTHROPIC_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

USER_AGENT = "AventisAI-LeadFinder/1.0 (contact@aventismarketing.com)"
REQUEST_TIMEOUT = 15

# ICP target business types for AventisAI
ICP_BUSINESS_TYPES = [
    "restaurant", "cafe", "bakery", "bar",
    "salon", "barbershop", "spa", "nail_salon",
    "real_estate_agency", "lawyer", "accountant",
    "gym", "fitness", "yoga_studio",
    "auto_repair", "car_dealer", "plumber", "electrician",
    "contractor", "landscaping", "cleaning_service",
    "dentist", "chiropractor", "veterinary_care",
    "boutique", "clothing_store", "jewelry_store",
    "photography", "wedding_planner", "event_planner",
]

# Tech signals — these in HTML = pain point (they're paying for separate tools)
TECH_SIGNALS = {
    "hubspot": ["hs-scripts.com", "hubspot", "_hsq"],
    "mailchimp": ["mailchimp.com", "list-manage.com", "mc-validate"],
    "calendly": ["calendly.com"],
    "intercom": ["intercom.io", "intercom.com"],
    "drift": ["drift.com", "driftt.com"],
    "hotjar": ["hotjar.com"],
    "wix": ["wix.com", "wixstatic"],
    "squarespace": ["squarespace.com", "static1.squarespace.com"],
    "wordpress": ["wp-content", "wp-includes"],
    "shopify": ["shopify.com", "cdn.shopify"],
    "clickfunnels": ["clickfunnels.com"],
    "kajabi": ["kajabi.com"],
    "podia": ["podia.com"],
    "constant_contact": ["constantcontact.com"],
    "convertkit": ["convertkit.com"],
    "active_campaign": ["activecampaign.com"],
    "tidio": ["tidio.com"],
    "drift_chat": ["drift"],
    "google_analytics": ["google-analytics.com", "gtag", "ga.js"],
    "facebook_pixel": ["connect.facebook.net", "fbq("],
}

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
PHONE_RE = re.compile(r"\(?\b\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b")
SOCIAL_DOMAINS = {
    "facebook": "facebook.com",
    "instagram": "instagram.com",
    "twitter": "twitter.com",
    "x": "x.com",
    "linkedin": "linkedin.com",
    "youtube": "youtube.com",
    "tiktok": "tiktok.com",
}


# ---------------------------------------------------------------------------
# Discovery — Google Places API (preferred)
# ---------------------------------------------------------------------------

def google_places_search(city, state, business_type=None, count=20):
    """Discover businesses via Google Places Text Search."""
    if not GOOGLE_PLACES_KEY:
        return []

    query = f"{business_type or 'small business'} in {city}, {state}"
    url = "https://maps.googleapis.com/maps/api/place/textsearch/json"
    params = {"query": query, "key": GOOGLE_PLACES_KEY}

    leads = []
    try:
        resp = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)
        data = resp.json()
        for place in data.get("results", [])[:count]:
            place_id = place.get("place_id")
            details = google_places_details(place_id) if place_id else {}
            leads.append({
                "business_name": place.get("name", ""),
                "address": place.get("formatted_address", ""),
                "city": city,
                "state": state,
                "phone": details.get("formatted_phone_number", ""),
                "website_url": details.get("website", ""),
                "has_website": 1 if details.get("website") else 0,
                "review_count": place.get("user_ratings_total", 0),
                "review_rating": place.get("rating", 0.0),
                "business_type": (place.get("types") or ["business"])[0],
                "source": "google_places",
                "google_place_id": place_id,
                "date_found": str(date.today()),
            })
            time.sleep(0.1)
    except Exception as e:
        print(f"[GooglePlaces] Error: {e}")
    return leads


def google_places_details(place_id):
    """Fetch place details (phone, website, hours)."""
    if not GOOGLE_PLACES_KEY or not place_id:
        return {}
    url = "https://maps.googleapis.com/maps/api/place/details/json"
    params = {
        "place_id": place_id,
        "fields": "formatted_phone_number,website,opening_hours,formatted_address",
        "key": GOOGLE_PLACES_KEY,
    }
    try:
        resp = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)
        return resp.json().get("result", {})
    except Exception:
        return {}


# ---------------------------------------------------------------------------
# Discovery — OpenStreetMap Overpass (free fallback)
# ---------------------------------------------------------------------------

def osm_geocode_city(city, state):
    """Get lat/lon for a city. Uses hardcoded coordinates first, then Nominatim."""
    key = f"{city.lower().strip()}_{state.upper().strip()}"
    if key in CITY_COORDS:
        return CITY_COORDS[key]

    url = "https://nominatim.openstreetmap.org/search"
    params = {"q": f"{city}, {state}, USA", "format": "json", "limit": 1}
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    try:
        resp = requests.get(url, params=params, headers=headers, timeout=REQUEST_TIMEOUT)
        if resp.status_code == 200 and resp.text:
            data = resp.json()
            if data:
                return float(data[0]["lat"]), float(data[0]["lon"])
    except Exception as e:
        print(f"[OSM Geocode] Error: {e}")
    return None, None


# Hardcoded coordinates for MA/RI/CT cities (avoids geocoding API issues)
CITY_COORDS = {
    # Massachusetts
    "boston_MA": (42.3601, -71.0589),
    "worcester_MA": (42.2626, -71.8023),
    "springfield_MA": (42.1015, -72.5898),
    "cambridge_MA": (42.3736, -71.1097),
    "lowell_MA": (42.6334, -71.3162),
    "brockton_MA": (42.0834, -71.0184),
    "new bedford_MA": (41.6362, -70.9342),
    "quincy_MA": (42.2529, -71.0023),
    "lynn_MA": (42.4668, -70.9495),
    "fall river_MA": (41.7015, -71.1550),
    "newton_MA": (42.3370, -71.2092),
    "somerville_MA": (42.3876, -71.0995),
    "framingham_MA": (42.2793, -71.4162),
    "brookline_MA": (42.3318, -71.1212),
    "plymouth_MA": (41.9584, -70.6673),
    "bridgewater_MA": (41.9904, -70.9750),
    "taunton_MA": (41.9001, -71.0898),
    "attleboro_MA": (41.9445, -71.2856),
    "weymouth_MA": (42.2204, -70.9395),
    "medford_MA": (42.4184, -71.1062),
    "haverhill_MA": (42.7762, -71.0773),
    "westborough_MA": (42.2695, -71.6162),
    "chatham_MA": (41.6829, -69.9596),
    "orleans_MA": (41.7901, -69.9895),
    # Rhode Island
    "providence_RI": (41.8240, -71.4128),
    "warwick_RI": (41.7001, -71.4162),
    "cranston_RI": (41.7798, -71.4373),
    "pawtucket_RI": (41.8787, -71.3826),
    "east providence_RI": (41.8137, -71.3700),
    "woonsocket_RI": (42.0029, -71.5145),
    "newport_RI": (41.4901, -71.3128),
    "central falls_RI": (41.8904, -71.3925),
    "westerly_RI": (41.3776, -71.8273),
    "bristol_RI": (41.6762, -71.2662),
    # Connecticut
    "hartford_CT": (41.7658, -72.6734),
    "new haven_CT": (41.3083, -72.9279),
    "bridgeport_CT": (41.1865, -73.1952),
    "stamford_CT": (41.0534, -73.5387),
    "waterbury_CT": (41.5582, -73.0515),
    "norwalk_CT": (41.1177, -73.4082),
    "danbury_CT": (41.3948, -73.4540),
    "new britain_CT": (41.6612, -72.7795),
    "meriden_CT": (41.5382, -72.8070),
    "middletown_CT": (41.5623, -72.6506),
}


OSM_TYPE_MAP = {
    "restaurant": "amenity=restaurant",
    "cafe": "amenity=cafe",
    "bar": "amenity=bar",
    "salon": "shop=hairdresser",
    "barbershop": "shop=hairdresser",
    "spa": "shop=beauty",
    "real_estate_agency": "office=estate_agent",
    "lawyer": "office=lawyer",
    "accountant": "office=accountant",
    "gym": "leisure=fitness_centre",
    "auto_repair": "shop=car_repair",
    "plumber": "craft=plumber",
    "electrician": "craft=electrician",
    "contractor": "office=company",
    "dentist": "amenity=dentist",
    "boutique": "shop=boutique",
    "clothing_store": "shop=clothes",
    "jewelry_store": "shop=jewelry",
}


def osm_overpass_search(city, state, business_type=None, count=20, radius_m=10000):
    """Discover businesses via OSM Overpass API."""
    lat, lon = osm_geocode_city(city, state)
    if not lat:
        return []

    osm_filter = OSM_TYPE_MAP.get(business_type, "amenity=restaurant")
    query = f"""
    [out:json][timeout:30];
    (
      node[{osm_filter}](around:{radius_m},{lat},{lon});
      way[{osm_filter}](around:{radius_m},{lat},{lon});
    );
    out center {count * 2};
    """
    url = "https://overpass-api.de/api/interpreter"
    try:
        resp = requests.post(url, data=query, headers={"User-Agent": USER_AGENT},
                             timeout=60)
        data = resp.json()
    except Exception as e:
        print(f"[OSM Overpass] Error: {e}")
        return []

    leads = []
    for elem in data.get("elements", [])[:count]:
        tags = elem.get("tags", {})
        name = tags.get("name")
        if not name:
            continue
        addr_parts = [
            tags.get("addr:housenumber", ""),
            tags.get("addr:street", ""),
        ]
        address = " ".join(p for p in addr_parts if p).strip()
        leads.append({
            "business_name": name,
            "address": address,
            "city": tags.get("addr:city", city),
            "state": tags.get("addr:state", state),
            "zip_code": tags.get("addr:postcode", ""),
            "phone": tags.get("phone", tags.get("contact:phone", "")),
            "email": tags.get("email", tags.get("contact:email", "")),
            "website_url": tags.get("website", tags.get("contact:website", "")),
            "has_website": 1 if tags.get("website") or tags.get("contact:website") else 0,
            "business_type": business_type or tags.get("amenity", "business"),
            "source": "osm_overpass",
            "date_found": str(date.today()),
        })
    return leads


# ---------------------------------------------------------------------------
# Enrichment — Website Scraping
# ---------------------------------------------------------------------------

def enrich_from_website(url):
    """Scrape a website for emails, phones, social links, and tech stack."""
    if not url:
        return {}
    if not url.startswith("http"):
        url = "https://" + url
    try:
        resp = requests.get(url, timeout=REQUEST_TIMEOUT,
                            headers={"User-Agent": USER_AGENT}, allow_redirects=True)
        if resp.status_code != 200:
            return {"website_status": f"http_{resp.status_code}"}
        html = resp.text
    except Exception as e:
        return {"website_status": f"error: {str(e)[:50]}"}

    enrichment = {"website_status": "active"}

    # Emails
    emails = set(EMAIL_RE.findall(html))
    emails = [e for e in emails if not e.endswith((".png", ".jpg", ".webp", ".gif"))
              and not any(s in e.lower() for s in ["example.com", "yourdomain", "sentry.io"])]
    if emails:
        emails.sort(key=lambda e: (0 if any(p in e.lower() for p in
                    ["info@", "contact@", "hello@", "hi@"]) else 1, len(e)))
        enrichment["email"] = emails[0]
        enrichment["all_emails"] = emails[:5]

    # Phones
    phones = PHONE_RE.findall(html)
    if phones:
        enrichment["phone"] = phones[0]

    # Social links
    soup = BeautifulSoup(html, "html.parser")
    socials = {}
    for a in soup.find_all("a", href=True):
        href = a["href"].lower()
        for name, domain in SOCIAL_DOMAINS.items():
            if domain in href and name not in socials:
                socials[name] = a["href"]
    if socials:
        enrichment["social_links"] = json.dumps(socials)
        enrichment["has_social_media"] = 1

    # Tech stack detection
    tech_found = []
    html_lower = html.lower()
    for tech, signals in TECH_SIGNALS.items():
        if any(sig.lower() in html_lower for sig in signals):
            tech_found.append(tech)
    enrichment["tech_stack"] = tech_found

    # Has chat widget?
    chat_tools = ["intercom", "drift", "tidio", "tawk.to", "crisp.chat", "livechat"]
    enrichment["has_chat_widget"] = any(t in html_lower for t in chat_tools)

    # Owner name from contact/about page
    title = soup.find("title")
    if title:
        enrichment["website_title"] = title.text.strip()[:200]

    # Look for owner pattern in HTML
    owner_match = re.search(
        r"(?:owner|founder|ceo|president|principal)[:\s]+([A-Z][a-z]+\s[A-Z][a-z]+)",
        html, re.IGNORECASE)
    if owner_match:
        enrichment["owner_name"] = owner_match.group(1)

    return enrichment


# ---------------------------------------------------------------------------
# Enrichment — Hunter.io Email Finder (optional)
# ---------------------------------------------------------------------------

def hunter_find_email(domain, first_name=None, last_name=None):
    """Find email via Hunter.io."""
    if not HUNTER_KEY or not domain:
        return None
    url = "https://api.hunter.io/v2/domain-search"
    params = {"domain": domain, "api_key": HUNTER_KEY, "limit": 5}
    try:
        resp = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)
        data = resp.json().get("data", {})
        emails = data.get("emails", [])
        if emails:
            return emails[0].get("value")
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# Scoring — ICP Fit + Pain Signals
# ---------------------------------------------------------------------------

def calculate_icp_score(lead):
    """
    Score a lead 0-100 based on AventisAI ICP fit.

    Weights:
      - 30%  Geographic fit (MA/RI/CT primary)
      - 25%  Pain signals (tech stack — paying for tools we replace)
      - 20%  Establishment signals (reviews, age)
      - 15%  Contactability (has phone, email, website)
      - 10%  Engagement (social media, recent reviews)
    """
    score = 0
    reasons = []

    # Geographic fit
    state = (lead.get("state") or "").upper()
    if state in ("MA", "RI", "CT"):
        score += 30
        reasons.append(f"+30 local ({state})")
    elif state in ("NH", "VT", "ME", "NY"):
        score += 15
        reasons.append(f"+15 nearby ({state})")

    # Pain signals (tech stack — they're paying for tools AventisAI replaces)
    tech_stack = lead.get("tech_stack") or []
    if isinstance(tech_stack, str):
        try:
            tech_stack = json.loads(tech_stack)
        except Exception:
            tech_stack = []
    pain_tools = {"hubspot", "mailchimp", "calendly", "intercom", "drift",
                  "constant_contact", "convertkit", "active_campaign", "clickfunnels"}
    pain_count = len(set(tech_stack) & pain_tools)
    if pain_count >= 3:
        score += 25
        reasons.append(f"+25 high pain ({pain_count} tools)")
    elif pain_count == 2:
        score += 18
        reasons.append(f"+18 med pain (2 tools)")
    elif pain_count == 1:
        score += 10
        reasons.append("+10 some pain (1 tool)")

    # Establishment signals
    reviews = lead.get("review_count", 0) or 0
    if reviews >= 50:
        score += 20
        reasons.append(f"+20 established ({reviews} reviews)")
    elif reviews >= 20:
        score += 15
        reasons.append(f"+15 established ({reviews} reviews)")
    elif reviews >= 10:
        score += 10
        reasons.append(f"+10 growing ({reviews} reviews)")

    # Contactability
    if lead.get("email"):
        score += 8
        reasons.append("+8 has email")
    if lead.get("phone"):
        score += 4
        reasons.append("+4 has phone")
    if lead.get("has_website"):
        score += 3
        reasons.append("+3 has website")

    # Engagement
    if lead.get("has_social_media"):
        score += 6
        reasons.append("+6 active on social")
    if lead.get("has_chat_widget") is False and lead.get("has_website"):
        score += 4
        reasons.append("+4 no chat (opportunity)")

    return min(score, 100), reasons


def priority_from_score(score):
    if score >= 75:
        return "HIGH"
    if score >= 50:
        return "MEDIUM"
    return "LOW"


# ---------------------------------------------------------------------------
# AI Scoring (via Claude API)
# ---------------------------------------------------------------------------

def ai_qualify_lead(lead):
    """Use Claude to provide qualitative ICP scoring."""
    if not ANTHROPIC_KEY:
        return None
    try:
        import anthropic
    except ImportError:
        return None

    client = anthropic.Anthropic(api_key=ANTHROPIC_KEY)
    summary = (
        f"Business: {lead.get('business_name')}\n"
        f"Type: {lead.get('business_type')}\n"
        f"Location: {lead.get('city')}, {lead.get('state')}\n"
        f"Website: {lead.get('website_url') or 'none'}\n"
        f"Reviews: {lead.get('review_count', 0)} ({lead.get('review_rating', 0)}/5)\n"
        f"Tech stack: {', '.join(lead.get('tech_stack', []))}\n"
        f"Has chat widget: {lead.get('has_chat_widget', False)}\n"
        f"Has social: {bool(lead.get('has_social_media'))}\n"
    )

    prompt = f"""You are qualifying a lead for AventisAI — an all-in-one AI-powered business software (CRM + email + SMS + AI chatbot + automation) sold at $297-$997/mo to SMBs (5-50 employees).

Lead profile:
{summary}

Score this lead's fit on a scale of 1-10 and provide a one-line reason. Format your response exactly as:
SCORE: <number>
REASON: <one sentence>"""

    try:
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=150,
            messages=[{"role": "user", "content": prompt}],
        )
        text = msg.content[0].text
        score_match = re.search(r"SCORE:\s*(\d+)", text)
        reason_match = re.search(r"REASON:\s*(.+)", text)
        return {
            "ai_score": int(score_match.group(1)) if score_match else None,
            "ai_reason": reason_match.group(1).strip() if reason_match else None,
        }
    except Exception as e:
        print(f"[AI Score] Error: {e}")
        return None


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------

def save_lead_to_db(lead):
    """Save a lead to the CRM database. Returns lead_id or None."""
    if not HAS_DB:
        return None
    db_lead = {
        "business_name": lead.get("business_name", ""),
        "owner_name": lead.get("owner_name", ""),
        "category": lead.get("business_type", ""),
        "business_type": lead.get("business_type", ""),
        "phone": lead.get("phone", ""),
        "email": lead.get("email", ""),
        "address": lead.get("address", ""),
        "city": lead.get("city", ""),
        "state": lead.get("state", ""),
        "zip_code": lead.get("zip_code", ""),
        "has_website": int(lead.get("has_website", 0)),
        "website_url": lead.get("website_url", ""),
        "has_social_media": int(lead.get("has_social_media", 0)),
        "social_links": lead.get("social_links", ""),
        "lead_score": lead.get("icp_score", 50),
        "date_found": lead.get("date_found", str(date.today())),
        "source": lead.get("source", "aventis_finder"),
        "status": "new",
        "priority": lead.get("priority", "medium").lower(),
        "notes": lead.get("notes", ""),
        "tags": lead.get("tags", ""),
    }
    try:
        return add_lead(db_lead)
    except Exception as e:
        print(f"[DB] Failed to save {lead.get('business_name')}: {e}")
        return None


def save_leads_to_json(leads, output_path):
    """Save leads to JSON file."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(leads, f, indent=2, default=str)
    print(f"[JSON] Saved {len(leads)} leads to {output_path}")


# ---------------------------------------------------------------------------
# Demo data (for testing without network/API access)
# ---------------------------------------------------------------------------

DEMO_LEADS = [
    {"business_name": "Cape Cod Coffee Roasters", "business_type": "cafe", "address": "47 Main St", "phone": "(508) 555-0142", "review_count": 87, "review_rating": 4.6, "website_url": "https://capecodcoffeeroasters-demo.com", "tech_stack": ["mailchimp", "calendly", "wix"], "has_chat_widget": False, "has_website": 1},
    {"business_name": "Patriot Plumbing & Heating", "business_type": "plumber", "address": "12 Oak Ave", "phone": "(508) 555-0178", "review_count": 34, "review_rating": 4.8, "website_url": "https://patriotplumbing-demo.com", "tech_stack": ["wordpress", "constant_contact"], "has_chat_widget": False, "has_website": 1},
    {"business_name": "Bay State Barbershop", "business_type": "barbershop", "address": "88 Court St", "phone": "(508) 555-0199", "review_count": 156, "review_rating": 4.9, "website_url": "", "tech_stack": [], "has_chat_widget": False, "has_website": 0},
    {"business_name": "Harborview Realty Group", "business_type": "real_estate_agency", "address": "200 Water St", "phone": "(508) 555-0211", "review_count": 42, "review_rating": 4.5, "website_url": "https://harborviewrealty-demo.com", "tech_stack": ["hubspot", "calendly", "mailchimp", "intercom"], "has_chat_widget": True, "has_website": 1},
    {"business_name": "Northeast Fitness Club", "business_type": "gym", "address": "350 Industrial Pkwy", "phone": "(508) 555-0233", "review_count": 218, "review_rating": 4.3, "website_url": "https://northeastfitness-demo.com", "tech_stack": ["mindbody", "mailchimp"], "has_chat_widget": False, "has_website": 1},
    {"business_name": "Mama Rosa's Italian Kitchen", "business_type": "restaurant", "address": "15 Federal St", "phone": "(508) 555-0254", "review_count": 412, "review_rating": 4.7, "website_url": "https://mamarosas-demo.com", "tech_stack": ["squarespace", "opentable"], "has_chat_widget": False, "has_website": 1},
    {"business_name": "Pristine Detailing Auto Spa", "business_type": "auto_repair", "address": "78 Commerce Rd", "phone": "(508) 555-0276", "review_count": 89, "review_rating": 4.8, "website_url": "https://pristinedetailing-demo.com", "tech_stack": ["wix", "calendly"], "has_chat_widget": False, "has_website": 1},
    {"business_name": "Bloom & Co. Floral Studio", "business_type": "boutique", "address": "23 Park Square", "phone": "(508) 555-0288", "review_count": 67, "review_rating": 4.9, "website_url": "https://bloomandco-demo.com", "tech_stack": ["shopify", "mailchimp", "klaviyo"], "has_chat_widget": True, "has_website": 1},
    {"business_name": "Apex Dental Care", "business_type": "dentist", "address": "405 Medical Plaza", "phone": "(508) 555-0301", "review_count": 134, "review_rating": 4.6, "website_url": "https://apexdentalcare-demo.com", "tech_stack": ["wordpress", "constant_contact", "calendly"], "has_chat_widget": False, "has_website": 1},
    {"business_name": "Olive Branch Bistro", "business_type": "restaurant", "address": "91 Main St", "phone": "(508) 555-0327", "review_count": 245, "review_rating": 4.5, "website_url": "https://olivebranchbistro-demo.com", "tech_stack": ["squarespace", "opentable", "mailchimp"], "has_chat_widget": False, "has_website": 1},
    {"business_name": "Coastal Landscape Design", "business_type": "landscaping", "address": "144 Beach Rd", "phone": "(508) 555-0349", "review_count": 28, "review_rating": 5.0, "website_url": "https://coastallandscape-demo.com", "tech_stack": ["wix", "mailchimp", "calendly", "hubspot"], "has_chat_widget": False, "has_website": 1},
    {"business_name": "Silver Sky Yoga Studio", "business_type": "yoga_studio", "address": "67 Wellness Way", "phone": "(508) 555-0364", "review_count": 76, "review_rating": 4.9, "website_url": "https://silverskyyoga-demo.com", "tech_stack": ["mindbody", "mailchimp", "instagram"], "has_chat_widget": False, "has_website": 1},
    {"business_name": "Granite State Contractors", "business_type": "contractor", "address": "210 Industrial Dr", "phone": "(508) 555-0381", "review_count": 18, "review_rating": 4.7, "website_url": "https://granitestate-demo.com", "tech_stack": ["wordpress", "constant_contact", "hubspot"], "has_chat_widget": True, "has_website": 1},
    {"business_name": "The Salon at Pinewood", "business_type": "salon", "address": "55 Pine St", "phone": "(508) 555-0402", "review_count": 192, "review_rating": 4.8, "website_url": "https://pinewoodsalon-demo.com", "tech_stack": ["squarespace", "vagaro"], "has_chat_widget": False, "has_website": 1},
    {"business_name": "Liberty Insurance Agency", "business_type": "insurance", "address": "350 Center St", "phone": "(508) 555-0419", "review_count": 51, "review_rating": 4.6, "website_url": "https://libertyins-demo.com", "tech_stack": ["hubspot", "mailchimp", "calendly", "drift"], "has_chat_widget": True, "has_website": 1},
]


def demo_search(city, state, business_type=None, count=20):
    """Generate demo leads for testing without external APIs."""
    import random
    pool = [dict(l) for l in DEMO_LEADS]
    if business_type:
        filtered = [l for l in pool if business_type.lower() in l.get("business_type", "").lower()]
        if filtered:
            pool = filtered
    random.shuffle(pool)
    pool = pool[:count]
    email_users = ["info", "contact", "hello", "team", "office"]
    out = []
    for lead in pool:
        lead["city"] = city
        lead["state"] = state
        lead["zip_code"] = f"0{random.randint(2000, 2900)}"
        lead["source"] = "demo"
        lead["date_found"] = str(date.today())
        if lead.get("website_url") and not lead.get("email"):
            domain = urlparse(lead["website_url"]).netloc.replace("www.", "")
            lead["email"] = f"{random.choice(email_users)}@{domain}"
        lead["has_social_media"] = 1 if random.random() > 0.3 else 0
        out.append(lead)
    return out


# ---------------------------------------------------------------------------
# Main Pipeline
# ---------------------------------------------------------------------------

def discover_leads(city, state, business_type=None, count=20, demo=False):
    """Discover leads using the best available source."""
    print(f"\n=== DISCOVERY: {business_type or 'all types'} in {city}, {state} ===")

    if demo:
        print("[Source] DEMO MODE — synthetic test data")
        return demo_search(city, state, business_type, count)

    if GOOGLE_PLACES_KEY:
        print("[Source] Using Google Places API")
        leads = google_places_search(city, state, business_type, count)
        if leads:
            return leads

    print("[Source] Using OpenStreetMap Overpass (free)")
    leads = osm_overpass_search(city, state, business_type, count)
    if leads:
        return leads

    print("[Source] All external sources unreachable, falling back to demo data")
    print("        (Set GOOGLE_PLACES_API_KEY for real lead data)")
    return demo_search(city, state, business_type, count)


def enrich_leads(leads, skip_existing=False):
    """Enrich each lead with website data, tech stack, etc."""
    print(f"\n=== ENRICHMENT: {len(leads)} leads ===")
    for i, lead in enumerate(leads, 1):
        url = lead.get("website_url")
        if not url:
            print(f"  [{i}/{len(leads)}] {lead.get('business_name')[:40]:40} -- no website")
            continue
        if skip_existing and lead.get("email"):
            continue
        print(f"  [{i}/{len(leads)}] {lead.get('business_name')[:40]:40} ", end="", flush=True)
        data = enrich_from_website(url)
        for k, v in data.items():
            if k not in lead or not lead.get(k):
                lead[k] = v
        print(f"[email={bool(data.get('email'))}, tech={len(data.get('tech_stack', []))}]")
        time.sleep(0.5)
    return leads


def score_leads(leads, use_ai=False):
    """Score each lead with ICP fit."""
    print(f"\n=== SCORING: {len(leads)} leads ===")
    for lead in leads:
        score, reasons = calculate_icp_score(lead)
        lead["icp_score"] = score
        lead["score_reasons"] = reasons
        lead["priority"] = priority_from_score(score)

        if use_ai:
            ai = ai_qualify_lead(lead)
            if ai:
                lead["ai_score"] = ai.get("ai_score")
                lead["ai_reason"] = ai.get("ai_reason")
            time.sleep(0.3)

    leads.sort(key=lambda x: -(x.get("icp_score", 0)))
    return leads


def print_summary(leads):
    print(f"\n{'='*70}")
    print(f"  RESULTS — {len(leads)} leads found")
    print(f"{'='*70}\n")
    high = sum(1 for l in leads if l.get("priority") == "HIGH")
    med = sum(1 for l in leads if l.get("priority") == "MEDIUM")
    low = sum(1 for l in leads if l.get("priority") == "LOW")
    with_email = sum(1 for l in leads if l.get("email"))
    with_website = sum(1 for l in leads if l.get("has_website"))
    print(f"  Priority: HIGH={high}  MEDIUM={med}  LOW={low}")
    print(f"  Contactable: {with_email} with email, {with_website} with website")
    print()
    print(f"  {'Score':<6}{'Priority':<10}{'Business':<40}{'Email':<30}")
    print(f"  {'-'*6}{'-'*10}{'-'*40}{'-'*30}")
    for lead in leads[:20]:
        score = lead.get("icp_score", 0)
        pri = lead.get("priority", "")
        name = (lead.get("business_name") or "")[:38]
        email = (lead.get("email") or "")[:28]
        print(f"  {score:<6}{pri:<10}{name:<40}{email:<30}")
    print()


def main():
    parser = argparse.ArgumentParser(
        description="AventisAI — Lead Discovery & Enrichment",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python execution/aventis_lead_finder.py --city Boston --state MA --count 20
  python execution/aventis_lead_finder.py --city Worcester --state MA --type restaurant --count 30 --enrich --save-db
  python execution/aventis_lead_finder.py --city Providence --state RI --enrich --score --save-db --use-ai
        """
    )
    parser.add_argument("--city", required=True, help="Target city")
    parser.add_argument("--state", required=True, help="Target state (MA, RI, CT, etc.)")
    parser.add_argument("--type", help="Business type filter (restaurant, salon, contractor, etc.)")
    parser.add_argument("--count", type=int, default=20, help="Number of leads to find")
    parser.add_argument("--enrich", action="store_true", help="Scrape websites for contact info + tech stack")
    parser.add_argument("--score", action="store_true", default=True, help="Calculate ICP score")
    parser.add_argument("--use-ai", action="store_true", help="Use Claude API for qualitative scoring")
    parser.add_argument("--save-db", action="store_true", help="Save to CRM database")
    parser.add_argument("--save-json", help="Save to JSON file path")
    parser.add_argument("--demo", action="store_true", help="Use synthetic demo data (for testing)")
    args = parser.parse_args()

    # 1. Discover
    leads = discover_leads(args.city, args.state, args.type, args.count, demo=args.demo)
    if not leads:
        print("No leads found.")
        return

    # 2. Enrich
    if args.enrich:
        leads = enrich_leads(leads)

    # 3. Score
    if args.score:
        leads = score_leads(leads, use_ai=args.use_ai)

    # 4. Save
    if args.save_db and HAS_DB:
        init_db()
        saved = 0
        for lead in leads:
            if save_lead_to_db(lead):
                saved += 1
        print(f"[DB] Saved {saved}/{len(leads)} leads to CRM")

    if args.save_json:
        save_leads_to_json(leads, args.save_json)
    elif not args.save_db:
        default_path = os.path.join(
            PROJECT_ROOT, "clients", "leads",
            f"aventis_leads_{args.city.lower().replace(' ', '_')}_{date.today()}.json"
        )
        save_leads_to_json(leads, default_path)

    # 5. Print summary
    print_summary(leads)


if __name__ == "__main__":
    main()
