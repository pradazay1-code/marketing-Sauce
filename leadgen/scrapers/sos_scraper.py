"""
Secretary of State new business filing scrapers for MA, RI, CT.
Pulls newly registered businesses (LLCs, DBAs, Corps) and checks for web presence.
"""

import requests
import time
import re
import socket
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from urllib.parse import quote_plus

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
}

EXCLUDED_KEYWORDS = [
    "holding", "holdings", "investment", "investments", "capital", "ventures",
    "management group", "consulting group", "advisors", "advisory", "fund",
    "trust", "trustees", "realty trust", "nominee", "fiduciary",
    "mcdonald", "subway", "dunkin", "starbucks", "walmart", "target",
    "amazon", "google", "microsoft", "apple inc", "cvs", "walgreens",
    "7-eleven", "burger king", "wendy", "chipotle", "domino",
    "shell", "exxon", "bp ", "chevron",
]

LOCAL_BUSINESS_KEYWORDS = [
    "restaurant", "cafe", "bakery", "salon", "barber", "spa", "gym", "fitness",
    "auto", "repair", "mechanic", "plumbing", "plumber", "electric", "electrician",
    "landscaping", "lawn", "cleaning", "maid", "janitorial", "tattoo", "piercing",
    "photography", "photo", "studio", "boutique", "shop", "store", "market",
    "grill", "pizza", "taco", "sushi", "kitchen", "food", "catering", "truck",
    "construction", "contractor", "roofing", "painting", "flooring", "tile",
    "pet", "grooming", "daycare", "childcare", "tutoring", "training",
    "dental", "chiropractic", "therapy", "massage", "wellness", "health",
    "nail", "beauty", "hair", "lash", "brow", "wax",
    "florist", "flower", "event", "planning", "dj",
    "moving", "hauling", "junk", "disposal",
    "real estate", "realty", "property", "homes",
    "law", "attorney", "legal", "lawyer",
    "bar ", "pub ", "tavern", "brewery", "distillery",
    "yoga", "pilates", "crossfit", "boxing",
    "hvac", "heating", "cooling", "insulation",
]


def is_local_business(name):
    name_lower = name.lower()
    for keyword in EXCLUDED_KEYWORDS:
        if keyword in name_lower:
            return False
    for keyword in LOCAL_BUSINESS_KEYWORDS:
        if keyword in name_lower:
            return True
    return False


def categorize_business(name):
    name_lower = name.lower()
    categories = {
        "Restaurant/Food": ["restaurant", "cafe", "bakery", "grill", "pizza", "taco", "sushi", "kitchen", "food", "catering", "truck", "bar & grill", "diner", "bistro"],
        "Salon/Beauty": ["salon", "beauty", "hair", "nail", "lash", "brow", "wax", "spa", "aesthetic"],
        "Barbershop": ["barber"],
        "Gym/Fitness": ["gym", "fitness", "training", "crossfit", "yoga", "pilates", "boxing"],
        "Auto Services": ["auto", "repair", "mechanic", "body shop", "tire", "detailing"],
        "Construction/Contractor": ["construction", "contractor", "roofing", "painting", "flooring", "tile", "remodel", "renovation", "build"],
        "Landscaping": ["landscaping", "lawn", "tree", "garden"],
        "Cleaning Services": ["cleaning", "maid", "janitorial", "pressure wash"],
        "Tattoo/Piercing": ["tattoo", "piercing", "ink"],
        "Photography": ["photography", "photo", "videograph"],
        "Retail/Boutique": ["boutique", "shop", "store", "market", "retail"],
        "Pet Services": ["pet", "grooming", "veterinar", "kennel", "dog", "cat"],
        "Healthcare/Wellness": ["dental", "chiropractic", "therapy", "massage", "wellness", "health", "medical", "clinic"],
        "Real Estate": ["real estate", "realty", "property", "homes", "broker"],
        "Lawyer/Attorney": ["law", "attorney", "legal", "lawyer", "esq"],
        "Childcare/Education": ["daycare", "childcare", "tutoring", "academy", "school", "learning"],
        "Events/Entertainment": ["event", "planning", "dj", "entertainment", "party", "wedding"],
        "Home Services": ["plumbing", "plumber", "electric", "electrician", "hvac", "handyman", "moving", "hauling", "heating", "cooling"],
        "Bar/Brewery": ["bar ", "pub ", "tavern", "brewery", "distillery"],
    }
    for category, keywords in categories.items():
        for kw in keywords:
            if kw in name_lower:
                return category
    return "Other"


def check_website_exists(business_name, city="", state=""):
    clean_name = re.sub(r'[^a-zA-Z0-9\s]', '', business_name).strip()
    slug = clean_name.lower().replace(" ", "")

    for suffix in [".com", ".net", ".biz"]:
        domain = slug + suffix
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(2)
            s.connect((domain, 80))
            s.close()
            return True, f"http://{domain}"
        except (socket.gaierror, socket.timeout, OSError, ConnectionRefusedError):
            continue

    return False, ""


def score_marketing_presence(has_website, has_social, business_age_days=0):
    """0 = no marketing at all (best lead), 10 = strong marketing (skip)"""
    score = 0
    if has_website:
        score += 4
    if has_social:
        score += 3
    if business_age_days > 365:
        score += 2
    elif business_age_days > 180:
        score += 1
    return min(score, 10)


def calculate_priority(marketing_score, has_website, phone):
    if not has_website and phone and marketing_score <= 2:
        return "high"
    elif marketing_score <= 4:
        return "medium"
    return "low"


def scrape_ma_new_filings(days_back=7, max_results=100):
    """Scrape Massachusetts Secretary of State for new business filings."""
    leads = []

    end_date = datetime.now()
    start_date = end_date - timedelta(days=days_back)

    try:
        session = requests.Session()
        session.headers.update(HEADERS)

        search_url = "https://corp.sec.state.ma.us/CorpWeb/CorpSearch/CorpSearch.aspx"
        resp = session.get(search_url, timeout=15)

        if resp.status_code != 200:
            return leads, f"MA SOS returned status {resp.status_code}"

        soup = BeautifulSoup(resp.text, "html.parser")

        viewstate = soup.find("input", {"name": "__VIEWSTATE"})
        if not viewstate:
            return leads, "Could not parse MA SOS page (no viewstate)"

        form_data = {
            "__VIEWSTATE": viewstate.get("value", ""),
            "__VIEWSTATEGENERATOR": soup.find("input", {"name": "__VIEWSTATEGENERATOR"}).get("value", "") if soup.find("input", {"name": "__VIEWSTATEGENERATOR"}) else "",
            "__EVENTVALIDATION": soup.find("input", {"name": "__EVENTVALIDATION"}).get("value", "") if soup.find("input", {"name": "__EVENTVALIDATION"}) else "",
            "ctl00$MainContent$txtEntityName": "",
            "ctl00$MainContent$txtEntityNumber": "",
            "ctl00$MainContent$ddlEntityType": "ALL",
            "ctl00$MainContent$txtOrganizationDateFrom": start_date.strftime("%m/%d/%Y"),
            "ctl00$MainContent$txtOrganizationDateTo": end_date.strftime("%m/%d/%Y"),
            "ctl00$MainContent$btnSearch": "Search",
        }

        resp = session.post(search_url, data=form_data, timeout=30)
        if resp.status_code == 200:
            result_soup = BeautifulSoup(resp.text, "html.parser")
            table = result_soup.find("table", {"id": "MainContent_SearchResults"})
            if table:
                rows = table.find_all("tr")[1:]
                for row in rows[:max_results]:
                    cells = row.find_all("td")
                    if len(cells) >= 3:
                        name = cells[0].get_text(strip=True)
                        entity_type = cells[1].get_text(strip=True) if len(cells) > 1 else ""
                        filing_date = cells[2].get_text(strip=True) if len(cells) > 2 else ""

                        if not is_local_business(name):
                            continue

                        has_site, site_url = check_website_exists(name, state="MA")
                        category = categorize_business(name)
                        m_score = score_marketing_presence(has_site, False)

                        leads.append({
                            "business_name": name,
                            "category": category,
                            "business_type": entity_type,
                            "city": "",
                            "state": "MA",
                            "has_website": int(has_site),
                            "website_url": site_url,
                            "marketing_score": m_score,
                            "priority": calculate_priority(m_score, has_site, ""),
                            "filing_date": filing_date,
                            "source": "MA Secretary of State",
                            "notes": f"New filing: {entity_type}. Filed {filing_date}.",
                        })
                        time.sleep(0.5)

    except Exception as e:
        return leads, str(e)

    return leads, ""


def scrape_ri_new_filings(days_back=7, max_results=100):
    """Scrape Rhode Island Secretary of State for new business filings."""
    leads = []
    try:
        session = requests.Session()
        session.headers.update(HEADERS)
        resp = session.get("https://business.sos.ri.gov/CorpWeb/CorpSearch/CorpSearch.aspx", timeout=15)

        if resp.status_code != 200:
            return leads, f"RI SOS returned status {resp.status_code}"

        soup = BeautifulSoup(resp.text, "html.parser")
        viewstate = soup.find("input", {"name": "__VIEWSTATE"})
        if not viewstate:
            return leads, "Could not parse RI SOS page"

        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)

        form_data = {
            "__VIEWSTATE": viewstate.get("value", ""),
            "ctl00$MainContent$txtOrganizationDateFrom": start_date.strftime("%m/%d/%Y"),
            "ctl00$MainContent$txtOrganizationDateTo": end_date.strftime("%m/%d/%Y"),
            "ctl00$MainContent$btnSearch": "Search",
        }

        resp = session.post("https://business.sos.ri.gov/CorpWeb/CorpSearch/CorpSearch.aspx", data=form_data, timeout=30)
        if resp.status_code == 200:
            result_soup = BeautifulSoup(resp.text, "html.parser")
            table = result_soup.find("table", {"class": "SearchResults"})
            if table:
                rows = table.find_all("tr")[1:]
                for row in rows[:max_results]:
                    cells = row.find_all("td")
                    if len(cells) >= 2:
                        name = cells[0].get_text(strip=True)
                        filing_date = cells[-1].get_text(strip=True) if len(cells) > 2 else ""

                        if not is_local_business(name):
                            continue

                        has_site, site_url = check_website_exists(name, state="RI")
                        category = categorize_business(name)
                        m_score = score_marketing_presence(has_site, False)

                        leads.append({
                            "business_name": name,
                            "category": category,
                            "city": "",
                            "state": "RI",
                            "has_website": int(has_site),
                            "website_url": site_url,
                            "marketing_score": m_score,
                            "priority": calculate_priority(m_score, has_site, ""),
                            "filing_date": filing_date,
                            "source": "RI Secretary of State",
                            "notes": f"New RI filing. Filed {filing_date}.",
                        })
                        time.sleep(0.5)

    except Exception as e:
        return leads, str(e)

    return leads, ""


def scrape_ct_new_filings(days_back=7, max_results=100):
    """Scrape Connecticut Secretary of State for new business filings."""
    leads = []
    try:
        session = requests.Session()
        session.headers.update(HEADERS)
        resp = session.get("https://service.ct.gov/business/s/onlinebusinesssearch", timeout=15)

        if resp.status_code != 200:
            return leads, f"CT SOS returned status {resp.status_code}"

        return leads, "CT SOS uses Salesforce/Lightning — requires browser automation. Use Google Places API instead."

    except Exception as e:
        return leads, str(e)


if __name__ == "__main__":
    print("Testing MA SOS scraper...")
    ma_leads, ma_error = scrape_ma_new_filings(days_back=7, max_results=10)
    print(f"  MA: {len(ma_leads)} leads found. Error: {ma_error or 'None'}")

    print("\nTesting RI SOS scraper...")
    ri_leads, ri_error = scrape_ri_new_filings(days_back=7, max_results=10)
    print(f"  RI: {len(ri_leads)} leads found. Error: {ri_error or 'None'}")

    print("\nTesting CT SOS scraper...")
    ct_leads, ct_error = scrape_ct_new_filings(days_back=7, max_results=10)
    print(f"  CT: {len(ct_leads)} leads found. Error: {ct_error or 'None'}")
