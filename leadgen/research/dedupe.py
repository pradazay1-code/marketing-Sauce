"""Duplicate detection for leads.

The original CRM deduped on exact phone match only, which misses the three ways
the same business actually arrives twice:

  1. Different phone formatting, or a second line for the same business
  2. The same business found by two sources under slightly different names
     ("Joe's Barbershop" vs "Joes Barber Shop LLC")
  3. The same website discovered under two hostnames (www / non-www / http)

Three independent keys are generated per lead. A match on **any** of them is a
duplicate. False negatives cost you a repeat cold-call to someone who already
told you no, so this errs toward catching more.
"""

import re

# Suffixes and filler that vary between sources for the same business.
_NOISE = re.compile(
    r"\b(llc|l\.l\.c|inc|incorporated|corp|corporation|co|company|ltd|limited"
    r"|pllc|pc|lp|llp|the|and|of|services?|service|solutions?|group|enterprises?"
    r"|professional|quality)\b", re.I)

_PUNCT = re.compile(r"[^a-z0-9\s]")
_WS = re.compile(r"\s+")


def phone_key(phone):
    """Last 10 digits, so +1/1/formatting differences collapse."""
    if not phone:
        return ""
    d = re.sub(r"\D", "", str(phone))
    if len(d) == 11 and d.startswith("1"):
        d = d[1:]
    return d if len(d) == 10 else ""


def domain_key(url):
    """Registrable host, lowercased, www and scheme stripped."""
    if not url:
        return ""
    u = str(url).strip().lower()
    u = re.sub(r"^https?://", "", u)
    u = u.split("/")[0].split("?")[0].split("#")[0]
    u = re.sub(r"^www\.", "", u)
    return u if "." in u else ""


def name_key(business_name, city="", state=""):
    """Normalized name plus locality.

    Locality is included because "Elite Landscaping" in Brockton and the same
    name in Providence are usually different businesses, and merging them would
    silently lose a real lead.
    """
    if not business_name:
        return ""
    n = str(business_name).lower()
    n = _PUNCT.sub(" ", n)          # "joe's" -> "joe s"
    n = _NOISE.sub(" ", n)          # drop llc / inc / the / services
    # Collapse to bare alphanumerics. Word boundaries are exactly what differs
    # between sources -- "Joe's Barbershop" and "Joes Barber Shop LLC" are the
    # same business, and only match once the spaces are gone.
    n = re.sub(r"[^a-z0-9]", "", n)
    if not n:
        return ""
    loc = re.sub(r"[^a-z0-9]", "", f"{city or ''}{state or ''}".lower())
    return f"{n}|{loc}"


def keys_for(lead):
    """All dedupe keys for one lead, empty ones dropped."""
    return {
        "phone": phone_key(lead.get("phone")),
        "domain": domain_key(lead.get("website_url")),
        "name": name_key(lead.get("business_name"), lead.get("city"),
                         lead.get("state")),
    }


class DedupeIndex:
    """In-memory index for checking a batch against existing leads.

    Build once per import run rather than querying per row -- a 500-row import
    otherwise becomes 1,500 round trips.
    """

    def __init__(self, existing_leads=None):
        self.phones = set()
        self.domains = set()
        self.names = set()
        for lead in existing_leads or []:
            self.add(lead)

    def add(self, lead):
        k = keys_for(lead)
        if k["phone"]:
            self.phones.add(k["phone"])
        if k["domain"]:
            self.domains.add(k["domain"])
        if k["name"]:
            self.names.add(k["name"])

    def check(self, lead):
        """Return the reason this lead is a duplicate, or None if it is new."""
        k = keys_for(lead)
        if k["phone"] and k["phone"] in self.phones:
            return f"phone already in CRM ({k['phone']})"
        if k["domain"] and k["domain"] in self.domains:
            return f"website already in CRM ({k['domain']})"
        if k["name"] and k["name"] in self.names:
            return f"same business name in same city ({k['name'].split('|')[0]})"
        return None

    def is_duplicate(self, lead):
        return self.check(lead) is not None


def dedupe_batch(leads, existing_leads=None):
    """Split a batch into new leads and rejected duplicates.

    Checks against both the existing CRM and earlier rows in the same batch, so
    a list containing the same business twice only yields it once.

    Returns (unique, duplicates) where each duplicate is (lead, reason).
    """
    index = DedupeIndex(existing_leads)
    unique, dupes = [], []
    for lead in leads:
        reason = index.check(lead)
        if reason:
            dupes.append((lead, reason))
            continue
        unique.append(lead)
        index.add(lead)
    return unique, dupes
