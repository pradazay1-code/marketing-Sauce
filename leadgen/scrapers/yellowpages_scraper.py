"""
Yellow Pages scraper — 100% FREE.

Scrapes yellowpages.com for businesses by category and city.
Returns: name, phone, address, website status, years in business.

Yellow Pages explicitly lists whether a business has a website,
making it ideal for finding leads without web presence.
"""

import re
import time
import requests
from urllib.parse import quote_plus
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

CATEGORIES = [
    ("restaurants", "Restaurant/Food"),
    ("barbers", "Barbershop"),
    ("hair-salons", "Salon/Beauty"),
    ("nail-salons", "Salon/Beauty"),
    ("beauty-salons", "Salon/Beauty"),
    ("auto-repair", "Auto Services"),
    ("contractors", "Construction/Contractor"),
    ("landscaping", "Landscaping"),
    ("cleaning-service", "Cleaning Services"),
    ("tattoo-piercing", "Tattoo/Piercing"),
    ("photographers", "Photography"),
    ("fitness-instruction", "Gym/Fitness"),
    ("personal-trainers", "Gym/Fitness"),
    ("bakeries", "Restaurant/Food"),
    ("caterers", "Restaurant/Food"),
    ("pet-grooming", "Pet Services"),
    ("florists", "Events/Entertainment"),
    ("event-planning-services", "Events/Entertainment"),
    ("attorneys", "Lawyer/Attorney"),
    ("real-estate-agents", "Real Estate"),
    ("plumbers", "Home Services"),
    ("electricians", "Home Services"),
    ("hvac-contractors", "Home Services"),
]

CITIES = {
    "MA": ["Boston", "Worcester", "Springfield", "Brockton", "New-Bedford",
           "Lowell", "Fall-River", "Taunton", "Plymouth", "Framingham",
           "Cambridge", "Quincy", "Newton", "Somerville", "Haverhill"],
    "RI": ["Providence", "Warwick", "Cranston", "Pawtucket", "East-Providence",
           "Newport", "Woonsocket", "Coventry"],
    "CT": ["Hartford", "New-Haven", "Bridgeport", "Stamford", "Waterbury",
           "Norwalk", "Danbury", "New-Britain", "Meriden", "West-Hartford"],
}


def parse_yp_listing(card):
    """Extract lead data from a single YP search result card."""
    name_el = card.find("a", class_="business-name")
    if not name_el:
        return None
    name = name_el.get_text(strip=True)
    if not name or "ad" in name_el.get("class", []):
        return None

    phone_el = card.find(class_="phones")
    phone = phone_el.get_text(strip=True) if phone_el else ""

    addr_el = card.find(class_="street-address")
    address = addr_el.get_text(strip=True) if addr_el else ""

    locality_el = card.find(class_="locality")
    city_state_zip = locality_el.get_text(strip=True) if locality_el else ""

    website_el = card.find("a", class_="track-visit-website")
    website = website_el.get("href", "") if website_el else ""
    has_website = 1 if website else 0

    email_el = card.find("a", class_="track-email") or card.find("a", href=re.compile(r"mailto:"))
    email = ""
    if email_el:
        href = email_el.get("href", "")
        if href.startswith("mailto:"):
            email = href[7:].split("?")[0].strip()

    years_el = card.find(class_="years-in-business")
    years = years_el.get_text(strip=True) if years_el else ""

    categories_el = card.find(class_="categories")
    cats = categories_el.get_text(strip=True) if categories_el else ""

    return {
        "name": name,
        "phone": phone,
        "email": email,
        "address": address,
        "city_state_zip": city_state_zip,
        "website": website,
        "has_website": has_website,
        "years_in_business": years,
        "categories": cats,
    }


def parse_city_state_zip(text, fallback_state=""):
    """Parse 'City, ST 12345' format."""
    match = re.match(r"(.+?),\s*([A-Z]{2})\s*(\d{5})?", text)
    if match:
        return match.group(1).strip(), match.group(2), (match.group(3) or "").strip()
    return text, fallback_state, ""


def search_yellowpages(category_slug, city, state, page=1, max_pages=2):
    """Search YP for category in city, return list of business dicts."""
    leads = []
    last_error = None

    for p in range(1, max_pages + 1):
        url = f"https://www.yellowpages.com/{quote_plus(city.replace(' ', '-'))}-{state.lower()}/{category_slug}"
        if p > 1:
            url += f"?page={p}"

        try:
            resp = requests.get(url, headers=HEADERS, timeout=20)
            if resp.status_code == 404:
                break
            if resp.status_code != 200:
                last_error = f"HTTP {resp.status_code}"
                break

            soup = BeautifulSoup(resp.text, "html.parser")
            cards = soup.find_all("div", class_="result")

            if not cards:
                cards = soup.find_all("div", class_="info")

            page_leads = 0
            for card in cards:
                lead = parse_yp_listing(card)
                if lead and lead["phone"]:
                    leads.append(lead)
                    page_leads += 1

            if page_leads == 0:
                break

            time.sleep(2)
        except requests.RequestException as e:
            last_error = str(e)
            break

    return leads, last_error


def _phone_digits(phone):
    """Strip phone formatting, keep digits only for dedup."""
    return re.sub(r"\D", "", phone or "")


def calculate_priority(has_website, phone, years):
    """High priority for established businesses without websites."""
    if not has_website and phone:
        return "high"
    if has_website:
        return "low"
    return "medium"


def scrape_yellowpages(state="MA", categories=None, cities=None, max_per_combo=15, only_no_website=False):
    """
    Main YP scraper. Returns leads from YP for given state.
    """
    if categories is None:
        categories = CATEGORIES[:8]
    if cities is None:
        cities = CITIES.get(state, CITIES["MA"])[:5]

    all_leads = []
    seen_phones = set()
    seen_names = set()
    errors = []

    for city in cities:
        for slug, our_category in categories:
            results, error = search_yellowpages(slug, city, state, max_pages=2)
            if error:
                errors.append(f"{city}/{slug}: {error}")
                continue

            count = 0
            for r in results:
                if count >= max_per_combo:
                    break

                if only_no_website and r["has_website"]:
                    continue

                phone_normalized = _phone_digits(r["phone"])
                name_key = r["name"].lower().strip()

                if phone_normalized and phone_normalized in seen_phones:
                    continue
                if name_key in seen_names:
                    continue

                if phone_normalized:
                    seen_phones.add(phone_normalized)
                seen_names.add(name_key)

                parsed_city, parsed_state, zip_code = parse_city_state_zip(
                    r["city_state_zip"], state
                )

                marketing_score = 4 if r["has_website"] else 0
                priority = calculate_priority(r["has_website"], r["phone"], r["years_in_business"])

                lead = {
                    "business_name": r["name"],
                    "category": our_category,
                    "phone": r["phone"],
                    "email": r.get("email", ""),
                    "address": r["address"],
                    "city": parsed_city or city.replace("-", " "),
                    "state": parsed_state or state,
                    "zip_code": zip_code,
                    "has_website": r["has_website"],
                    "website_url": r["website"],
                    "marketing_score": marketing_score,
                    "priority": priority,
                    "business_type": r["categories"],
                    "source": "Yellow Pages",
                    "notes": f"YP listing. {r['years_in_business']}".strip(),
                }
                all_leads.append(lead)
                count += 1

            time.sleep(1.5)

    return all_leads, "; ".join(errors[:5]) if errors else ""


if __name__ == "__main__":
    print("Testing Yellow Pages scraper (FREE)...")
    leads, error = scrape_yellowpages(
        "MA",
        categories=[("barbers", "Barbershop")],
        cities=["Boston"],
        max_per_combo=5,
        only_no_website=True,
    )
    print(f"\nFound {len(leads)} barbershops without websites in Boston, MA")
    if error:
        print(f"Errors: {error}")
    for lead in leads[:5]:
        print(f"  - {lead['business_name']} | {lead['phone']} | {lead['address']}")
