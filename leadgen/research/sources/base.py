"""Shared contract for every lead source.

Each source knows one thing: given an industry search term plus a location,
return normalized `Candidate` records. Sources never write to the database and
never decide whether a lead is good -- that is the consensus engine's job.

Adding a source means writing a `search()` and registering it. Nothing else in
the pipeline changes.

TRUST weights reflect data quality, not usefulness. They are used to break ties
when sources disagree on a field, and to weight the corroboration score -- two
Google Places hits mean more than two blog mentions.
"""

import os
import re
from dataclasses import dataclass, field, asdict


@dataclass
class Candidate:
    """One business as reported by one source. Not yet a lead."""
    business_name: str = ""
    phone: str = ""
    website: str = ""
    address: str = ""
    city: str = ""
    state: str = ""
    zip_code: str = ""
    latitude: float = None
    longitude: float = None
    category: str = ""
    review_count: int = None
    review_rating: float = None
    source: str = ""
    source_id: str = ""
    raw: dict = field(default_factory=dict)

    def to_dict(self):
        d = asdict(self)
        d.pop("raw", None)
        return d

    def is_usable(self):
        """A name plus at least one way to reach or identify them."""
        return bool(self.business_name.strip()) and bool(
            self.phone or self.website or self.address)


def norm_phone(raw):
    """Last 10 NANP digits as +1XXXXXXXXXX, or empty."""
    if not raw:
        return ""
    d = re.sub(r"\D", "", str(raw))
    if len(d) == 11 and d.startswith("1"):
        d = d[1:]
    if len(d) != 10 or d[0] in "01" or d[3] in "01":
        return ""
    return f"+1{d}"


def norm_website(raw):
    """Scheme-and-www-stripped host with path preserved, or empty.

    Directory listings are rejected outright -- a Yelp URL is not a business's
    website, and letting one through makes the audit score them as having a web
    presence they do not have.
    """
    if not raw:
        return ""
    u = str(raw).strip()
    if not u or u.lower() in ("null", "none"):
        return ""
    if "://" not in u:
        u = "https://" + u
    host = u.split("://", 1)[1].split("/")[0].lower().replace("www.", "")
    if not host or "." not in host:
        return ""
    if any(d in host for d in DIRECTORY_HOSTS):
        return ""
    return u


DIRECTORY_HOSTS = (
    "yelp.com", "yellowpages.com", "bbb.org", "angi.com", "angieslist.com",
    "thumbtack.com", "houzz.com", "facebook.com", "instagram.com",
    "linkedin.com", "twitter.com", "x.com", "mapquest.com", "tripadvisor.com",
    "indeed.com", "nextdoor.com", "manta.com", "wikipedia.org", "youtube.com",
    "reddit.com", "foursquare.com", "google.com", "bing.com", "apple.com",
    "zillow.com", "realtor.com", "trulia.com", "redfin.com", "homeadvisor.com",
    "chamberofcommerce.com", "birdeye.com", "porch.com", "expertise.com",
)


def looks_like_directory(name):
    """Reject listicle titles that describe many businesses, not one.

    Web search returns a lot of "Top 10 Landscapers in Brockton" pages, and
    importing them creates leads that are not businesses at all.
    """
    if not name:
        return True
    n = name.lower()
    if re.match(r"^\s*(top|best|the)\s+\d+", n):
        return True
    return any(p in n for p in (
        "top 10", "top 5", "best of", "near me", "directory", "listings",
        "yellow pages", "reviews of", " vs ", "compare ", "guide to",
    ))


class Source:
    """Base class. Subclasses set `name`/`trust` and implement `_search`."""

    name = "base"
    trust = 0.5
    env_key = ""          # env var holding the credential, "" if none needed

    def is_configured(self):
        return True if not self.env_key else bool(os.getenv(self.env_key, "").strip())

    def status(self):
        return {"name": self.name, "configured": self.is_configured(),
                "env": self.env_key, "trust": self.trust}

    def search(self, term, city, state, limit=20):
        """Normalized, filtered candidates. Never raises."""
        if not self.is_configured():
            return []
        try:
            out = self._search(term, city, state, limit) or []
        except Exception as e:                    # noqa: BLE001
            print(f"[{self.name}] search failed: {str(e)[:160]}")
            return []
        clean = []
        for c in out:
            c.source = self.name
            c.phone = norm_phone(c.phone)
            c.website = norm_website(c.website)
            c.business_name = (c.business_name or "").strip()[:140]
            if not c.is_usable() or looks_like_directory(c.business_name):
                continue
            if not c.city:
                c.city = city
            if not c.state:
                c.state = state
            clean.append(c)
        return clean

    def _search(self, term, city, state, limit):
        raise NotImplementedError


_REGISTRY = {}


def register(source):
    _REGISTRY[source.name] = source
    return source


def get_sources(only=None, configured_only=True):
    """Registered sources, optionally filtered to a named subset."""
    out = []
    for name, src in _REGISTRY.items():
        if only and name not in only:
            continue
        if configured_only and not src.is_configured():
            continue
        out.append(src)
    return sorted(out, key=lambda s: -s.trust)


def all_status():
    return [s.status() for s in sorted(_REGISTRY.values(), key=lambda s: -s.trust)]
