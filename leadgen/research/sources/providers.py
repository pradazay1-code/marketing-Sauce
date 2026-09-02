"""Concrete lead sources.

Every provider here is optional. Configure one and the system works; configure
five and the consensus engine can corroborate across them, which is what makes
the output trustworthy rather than merely plentiful.

  Google Places  GOOGLE_PLACES_API_KEY   places.googleapis.com/v1 (New)
  Yelp Fusion    YELP_API_KEY            api.yelp.com/v3
  Foursquare     FOURSQUARE_API_KEY      places-api.foursquare.com
  Serper         SERPER_API_KEY          google.serper.dev/maps
  Firecrawl      FIRECRAWL_API_KEY       api.firecrawl.dev/v2/search
  OpenStreetMap  (none)                  Overpass / Nominatim, always free

Cost note, checked Sept 2026: Google Places Text Search bills at the Pro SKU
(~$32/1k, 5k free per month); Yelp Fusion ended its free tier and starts around
$7.99/1k; Foursquare deprecated v3 on 15 May 2026, so this targets the new
Places API. Serper and Firecrawl are credit-based. OSM is free and unlimited but
sparse on phone numbers.
"""

import os
import re
import requests

from .base import Candidate, Source, register

TIMEOUT = 25


# ---------------------------------------------------------------------------
# Google Places API (New) -- highest quality structured local data
# ---------------------------------------------------------------------------

class GooglePlaces(Source):
    name = "google_places"
    trust = 1.0
    env_key = "GOOGLE_PLACES_API_KEY"

    FIELDS = ",".join([
        "places.displayName", "places.formattedAddress",
        "places.nationalPhoneNumber", "places.websiteUri",
        "places.location", "places.rating", "places.userRatingCount",
        "places.primaryTypeDisplayName", "places.id",
    ])

    def _search(self, term, city, state, limit):
        r = requests.post(
            "https://places.googleapis.com/v1/places:searchText",
            headers={
                "Content-Type": "application/json",
                "X-Goog-Api-Key": os.getenv(self.env_key, "").strip(),
                "X-Goog-FieldMask": self.FIELDS,
            },
            json={"textQuery": f"{term} in {city}, {state}",
                  "maxResultCount": min(limit, 20)},
            timeout=TIMEOUT,
        )
        if r.status_code == 403:
            raise RuntimeError("Places API not enabled, or key restricted")
        r.raise_for_status()

        out = []
        for p in (r.json() or {}).get("places", []):
            loc = p.get("location") or {}
            addr = p.get("formattedAddress") or ""
            out.append(Candidate(
                business_name=(p.get("displayName") or {}).get("text", ""),
                phone=p.get("nationalPhoneNumber", ""),
                website=p.get("websiteUri", ""),
                address=addr,
                city=_city_from_address(addr) or city,
                state=state,
                zip_code=_zip_from_address(addr),
                latitude=loc.get("latitude"),
                longitude=loc.get("longitude"),
                category=(p.get("primaryTypeDisplayName") or {}).get("text", ""),
                review_count=p.get("userRatingCount"),
                review_rating=p.get("rating"),
                source_id=p.get("id", ""),
                raw=p,
            ))
        return out


# ---------------------------------------------------------------------------
# Yelp Fusion -- strong on reviews, which drive two audit signals
# ---------------------------------------------------------------------------

class Yelp(Source):
    name = "yelp"
    trust = 0.9
    env_key = "YELP_API_KEY"

    def _search(self, term, city, state, limit):
        r = requests.get(
            "https://api.yelp.com/v3/businesses/search",
            headers={"Authorization": f"Bearer {os.getenv(self.env_key,'').strip()}"},
            params={"term": term, "location": f"{city}, {state}",
                    "limit": min(limit, 50)},
            timeout=TIMEOUT,
        )
        if r.status_code == 429:
            raise RuntimeError("Yelp rate limit / quota exhausted")
        r.raise_for_status()

        out = []
        for b in (r.json() or {}).get("businesses", []):
            loc = b.get("location") or {}
            coord = b.get("coordinates") or {}
            cats = ", ".join(c.get("title", "")
                             for c in (b.get("categories") or []))
            out.append(Candidate(
                business_name=b.get("name", ""),
                phone=b.get("phone") or b.get("display_phone", ""),
                # Yelp returns its own listing URL, never the business's site.
                website="",
                address=" ".join(loc.get("display_address") or []),
                city=loc.get("city") or city,
                state=loc.get("state") or state,
                zip_code=loc.get("zip_code", ""),
                latitude=coord.get("latitude"),
                longitude=coord.get("longitude"),
                category=cats,
                review_count=b.get("review_count"),
                review_rating=b.get("rating"),
                source_id=b.get("id", ""),
                raw=b,
            ))
        return out


# ---------------------------------------------------------------------------
# Foursquare Places (new API -- v3 was retired 15 May 2026)
# ---------------------------------------------------------------------------

class Foursquare(Source):
    name = "foursquare"
    trust = 0.8
    env_key = "FOURSQUARE_API_KEY"
    API_VERSION = "2025-06-17"

    def _search(self, term, city, state, limit):
        r = requests.get(
            "https://places-api.foursquare.com/places/search",
            headers={
                "Authorization": f"Bearer {os.getenv(self.env_key,'').strip()}",
                "X-Places-Api-Version": self.API_VERSION,
                "accept": "application/json",
            },
            params={"query": term, "near": f"{city}, {state}",
                    "limit": min(limit, 50)},
            timeout=TIMEOUT,
        )
        r.raise_for_status()

        out = []
        for p in (r.json() or {}).get("results", []):
            loc = p.get("location") or {}
            geo = (p.get("geocodes") or {}).get("main") or {}
            cats = ", ".join(c.get("name", "") for c in (p.get("categories") or []))
            out.append(Candidate(
                business_name=p.get("name", ""),
                phone=p.get("tel", ""),
                website=p.get("website", ""),
                address=loc.get("formatted_address")
                        or loc.get("address", ""),
                city=loc.get("locality") or city,
                state=loc.get("region") or state,
                zip_code=loc.get("postcode", ""),
                latitude=geo.get("latitude"),
                longitude=geo.get("longitude"),
                category=cats,
                source_id=str(p.get("fsq_place_id") or p.get("fsq_id") or ""),
                raw=p,
            ))
        return out


# ---------------------------------------------------------------------------
# Serper -- Google Maps results without a Google Cloud project
# ---------------------------------------------------------------------------

class Serper(Source):
    name = "serper"
    trust = 0.85
    env_key = "SERPER_API_KEY"

    def _search(self, term, city, state, limit):
        r = requests.post(
            "https://google.serper.dev/maps",
            headers={"X-API-KEY": os.getenv(self.env_key, "").strip(),
                     "Content-Type": "application/json"},
            json={"q": f"{term} {city} {state}", "num": min(limit, 20)},
            timeout=TIMEOUT,
        )
        r.raise_for_status()

        out = []
        for p in (r.json() or {}).get("places", []):
            out.append(Candidate(
                business_name=p.get("title", ""),
                phone=p.get("phoneNumber", ""),
                website=p.get("website", ""),
                address=p.get("address", ""),
                city=_city_from_address(p.get("address", "")) or city,
                state=state,
                zip_code=_zip_from_address(p.get("address", "")),
                latitude=p.get("latitude"),
                longitude=p.get("longitude"),
                category=p.get("type", ""),
                review_count=p.get("ratingCount"),
                review_rating=p.get("rating"),
                source_id=str(p.get("cid") or p.get("placeId") or ""),
                raw=p,
            ))
        return out


# ---------------------------------------------------------------------------
# Firecrawl web search -- catches businesses the places APIs have never indexed
# ---------------------------------------------------------------------------

class FirecrawlWeb(Source):
    name = "firecrawl"
    trust = 0.6
    env_key = "FIRECRAWL_API_KEY"

    def _search(self, term, city, state, limit):
        from research import firecrawl_client as fc

        res = fc.search(f"{term} in {city}, {state}", limit=min(limit, 20))
        if not res.get("ok"):
            raise RuntimeError(res.get("error", "search failed"))

        out = []
        for r in res["results"]:
            out.append(Candidate(
                business_name=_clean_title(r.get("title", "")),
                website=r.get("url", ""),
                city=city, state=state,
                category=term,
                raw={"description": (r.get("description") or "")[:400]},
            ))
        return out


# ---------------------------------------------------------------------------
# OpenStreetMap -- free, unlimited, and the only source with no key at all
# ---------------------------------------------------------------------------

class OpenStreetMap(Source):
    name = "osm"
    trust = 0.7
    env_key = ""

    CITY_COORDS = {}          # resolved lazily via Nominatim

    def _search(self, term, city, state, limit):
        # Nominatim's free-text search doubles as a POI lookup and needs no key.
        r = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": f"{term} {city} {state}", "format": "json",
                    "limit": min(limit, 25), "addressdetails": 1,
                    "extratags": 1, "countrycodes": "us"},
            headers={"User-Agent": "AventisAI-CRM/1.0 (lead research)"},
            timeout=TIMEOUT,
        )
        r.raise_for_status()

        out = []
        for p in r.json() or []:
            addr = p.get("address") or {}
            tags = p.get("extratags") or {}
            name = p.get("name") or (p.get("display_name") or "").split(",")[0]
            out.append(Candidate(
                business_name=name,
                phone=tags.get("phone") or tags.get("contact:phone", ""),
                website=tags.get("website") or tags.get("contact:website", ""),
                address=(p.get("display_name") or "").split(",")[0],
                city=addr.get("city") or addr.get("town")
                     or addr.get("village") or city,
                state=addr.get("state") or state,
                zip_code=addr.get("postcode", ""),
                latitude=_f(p.get("lat")),
                longitude=_f(p.get("lon")),
                category=p.get("type", ""),
                source_id=str(p.get("osm_id", "")),
                raw={},
            ))
        return out


# ---------------------------------------------------------------------------

def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _zip_from_address(addr):
    m = re.search(r"\b(\d{5})(?:-\d{4})?\b", addr or "")
    return m.group(1) if m else ""


def _city_from_address(addr):
    """Second-to-last comma segment, before 'ST 01234'."""
    if not addr:
        return ""
    parts = [p.strip() for p in addr.split(",") if p.strip()]
    for p in reversed(parts):
        if re.match(r"^[A-Z]{2}\s+\d{5}", p):
            idx = parts.index(p)
            return parts[idx - 1] if idx > 0 else ""
    return parts[-2] if len(parts) >= 2 else ""


def _clean_title(title):
    if not title:
        return ""
    name = title.split("|")[0].split(" - ")[0].split("–")[0].strip()
    for suf in ("Home", "Homepage", "Official Site", "Welcome"):
        if name.endswith(suf) and len(name) > len(suf) + 3:
            name = name[: -len(suf)].strip(" -|")
    return name[:140]


register(GooglePlaces())
register(Serper())
register(Yelp())
register(Foursquare())
register(OpenStreetMap())
register(FirecrawlWeb())
