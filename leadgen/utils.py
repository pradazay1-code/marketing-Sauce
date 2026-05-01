"""
LeadPilot — Utility functions.
Phone normalization, email validation, lead scoring, enrichment.
"""

import re
import socket
import requests
from urllib.parse import urlparse

REQUEST_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
}


def normalize_phone(phone):
    """Convert any phone format to (XXX) XXX-XXXX. Returns empty string if invalid."""
    if not phone:
        return ""
    digits = re.sub(r"\D", "", str(phone))
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    if len(digits) != 10:
        return ""
    return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"


def phone_digits(phone):
    """Extract last 10 digits from a phone number for dedup comparison."""
    if not phone:
        return ""
    digits = re.sub(r"\D", "", str(phone))
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    return digits[-10:] if len(digits) >= 10 else ""


def is_valid_phone(phone):
    """Check if phone has 10 digits."""
    return len(phone_digits(phone)) == 10


EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")


def is_valid_email(email):
    """Validate email format."""
    if not email:
        return False
    return bool(EMAIL_REGEX.match(email.strip()))


def has_mx_record(domain):
    """Check if domain has DNS A record (proxy for email-capable)."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(3)
        try:
            socket.getaddrinfo(domain, None)
            return True
        finally:
            s.close()
    except (socket.gaierror, socket.timeout, OSError):
        return False


def check_website_live(business_name, custom_domain=None):
    """
    Website detection: tries HTTP HEAD on common domain variations.
    Returns (has_website: bool, working_url: str, status_code: int).
    """
    clean_name = re.sub(r"[^a-zA-Z0-9\s]", "", business_name).strip()
    slug = clean_name.lower().replace(" ", "")

    candidates = []
    if custom_domain:
        candidates.append(custom_domain)
    candidates.extend([
        f"https://{slug}.com",
        f"https://www.{slug}.com",
        f"https://{slug}.net",
        f"https://{slug}.biz",
    ])

    for url in candidates:
        try:
            resp = requests.head(url, headers=REQUEST_HEADERS, timeout=4, allow_redirects=True)
            if 200 <= resp.status_code < 400:
                return True, resp.url, resp.status_code
        except requests.RequestException:
            try:
                resp = requests.get(url, headers=REQUEST_HEADERS, timeout=4, allow_redirects=True, stream=True)
                resp.close()
                if 200 <= resp.status_code < 400:
                    return True, resp.url, resp.status_code
            except requests.RequestException:
                continue

    return False, "", 0


HIGH_VALUE_CATEGORIES = {
    "Restaurant/Food", "Salon/Beauty", "Barbershop", "Gym/Fitness",
    "Real Estate", "Lawyer/Attorney", "Auto Services", "Healthcare/Wellness",
    "Construction/Contractor", "Home Services", "Landscaping",
}


def calculate_lead_score(lead):
    """Smart lead scoring 0-100. Higher = better prospect for marketing outreach."""
    score = 50

    if not lead.get("has_website"):
        score += 25
    if lead.get("phone"):
        score += 10
    if lead.get("email"):
        score += 5
    if not lead.get("has_social_media"):
        score += 10
    if lead.get("address"):
        score += 5
    if lead.get("category") in HIGH_VALUE_CATEGORIES:
        score += 10

    if lead.get("has_website") and lead.get("website_url"):
        url = (lead["website_url"] or "").lower()
        if any(b in url for b in ["wix.com", "weebly", "godaddysites", "facebook.com", "yelp.com"]):
            score += 15

    return max(0, min(100, score))


def enrich_lead(lead):
    """Auto-fill priority and score on a lead dict."""
    if lead.get("phone"):
        lead["phone"] = normalize_phone(lead["phone"])

    lead["lead_score"] = calculate_lead_score(lead)

    if not lead.get("priority"):
        if lead["lead_score"] >= 80:
            lead["priority"] = "high"
        elif lead["lead_score"] >= 60:
            lead["priority"] = "medium"
        else:
            lead["priority"] = "low"

    return lead


def merge_duplicates(leads_list):
    """Detect and merge near-duplicate leads in a list (pre-DB dedup)."""
    by_phone = {}
    by_name_city = {}
    deduped = []

    for lead in leads_list:
        pk = phone_digits(lead.get("phone", ""))
        name_city = (lead.get("business_name", "").lower().strip(),
                     lead.get("city", "").lower().strip())

        if pk and pk in by_phone:
            existing = by_phone[pk]
            for k, v in lead.items():
                if not existing.get(k) and v:
                    existing[k] = v
            continue

        if name_city[0] and name_city in by_name_city:
            existing = by_name_city[name_city]
            for k, v in lead.items():
                if not existing.get(k) and v:
                    existing[k] = v
            continue

        if pk:
            by_phone[pk] = lead
        if name_city[0]:
            by_name_city[name_city] = lead
        deduped.append(lead)

    return deduped
