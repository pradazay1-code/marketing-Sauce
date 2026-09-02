"""Firecrawl v2 client — deep web research for lead discovery and auditing.

Two endpoints carry the whole feature:

  POST /v2/scrape   one URL -> markdown + html + metadata + links
  POST /v2/search   a query -> ranked results, optionally scraped inline

Everything degrades gracefully. With no FIRECRAWL_API_KEY set, calls return a
structured "not configured" result rather than raising, so the CRM stays usable
and the UI can say why the feature is dark.

Docs: https://docs.firecrawl.dev
"""

import os
import re
import time
import requests

BASE = "https://api.firecrawl.dev/v2"
DEFAULT_TIMEOUT = 45


def api_key():
    return os.getenv("FIRECRAWL_API_KEY", "").strip()


def is_configured():
    return bool(api_key())


class FirecrawlError(Exception):
    pass


def _post(path, payload, timeout=DEFAULT_TIMEOUT):
    key = api_key()
    if not key:
        raise FirecrawlError("FIRECRAWL_API_KEY is not set")
    r = requests.post(
        f"{BASE}{path}",
        headers={"Authorization": f"Bearer {key}",
                 "Content-Type": "application/json"},
        json=payload,
        timeout=timeout,
    )
    if r.status_code == 401:
        raise FirecrawlError("Firecrawl rejected the API key (401)")
    if r.status_code == 402:
        raise FirecrawlError("Firecrawl credits exhausted (402)")
    if r.status_code == 429:
        raise FirecrawlError("Firecrawl rate limit hit (429) — slow down")
    if r.status_code >= 400:
        raise FirecrawlError(f"Firecrawl HTTP {r.status_code}: {r.text[:200]}")
    return r.json()


def scrape(url, formats=None, only_main=True, timeout=DEFAULT_TIMEOUT):
    """Scrape one URL.

    Returns {ok, url, markdown, html, links, metadata, error}. `ok` is False
    with a populated `error` rather than raising, because a dead prospect site
    is an ordinary outcome here -- and often the finding itself.
    """
    if not url:
        return {"ok": False, "error": "no url", "url": url}
    if "://" not in url:
        url = f"https://{url}"

    formats = formats or ["markdown", "html", "links"]
    try:
        body = _post("/scrape", {
            "url": url,
            "formats": formats,
            "onlyMainContent": only_main,
        }, timeout=timeout)
    except FirecrawlError as e:
        return {"ok": False, "error": str(e), "url": url}
    except requests.RequestException as e:
        return {"ok": False, "error": f"network: {str(e)[:150]}", "url": url}

    data = body.get("data") or {}
    return {
        "ok": bool(body.get("success", True)),
        "url": url,
        "markdown": data.get("markdown") or "",
        "html": data.get("rawHtml") or data.get("html") or "",
        "links": data.get("links") or [],
        "metadata": data.get("metadata") or {},
        "error": "",
    }


def search(query, limit=10, scrape_results=False, timeout=60):
    """Web search, optionally scraping each result inline.

    `scrape_results=True` costs materially more credits -- one scrape per
    result -- so discovery runs leave it off and audit only the sites that
    survive filtering.
    """
    payload = {"query": query, "limit": limit}
    if scrape_results:
        payload["scrapeOptions"] = {"formats": ["markdown"]}
    try:
        body = _post("/search", payload, timeout=timeout)
    except (FirecrawlError, requests.RequestException) as e:
        return {"ok": False, "error": str(e)[:200], "results": []}

    raw = body.get("data")
    if isinstance(raw, dict):
        raw = raw.get("web") or raw.get("results") or []
    results = [
        {
            "title": r.get("title") or "",
            "url": r.get("url") or "",
            "description": r.get("description") or r.get("snippet") or "",
            "markdown": r.get("markdown") or "",
        }
        for r in (raw or []) if r.get("url")
    ]
    return {"ok": True, "error": "", "results": results}


# ---------------------------------------------------------------------------
# Contact extraction
# ---------------------------------------------------------------------------

_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]{2,}")
_PHONE_RE = re.compile(r"(?:\+?1[-.\s]?)?\(?([2-9]\d{2})\)?[-.\s]?([2-9]\d{2})[-.\s]?(\d{4})")

# Addresses that appear on nearly every site and belong to nobody useful.
_JUNK_EMAIL = re.compile(
    r"(sentry|wixpress|example\.|@2x|\.png|\.jpe?g|\.gif|\.webp|\.svg"
    r"|godaddy|squarespace|wordpress|yourdomain|domain\.com)", re.I)


def extract_contacts(page):
    """Pull emails and phone numbers out of a scraped page.

    Prefers role addresses (info@, contact@, owner@) since those reach a human
    at a small business, and drops the tracking and asset noise that otherwise
    dominates a naive regex sweep.
    """
    if not page or not page.get("ok"):
        return {"emails": [], "phones": []}

    blob = f"{page.get('markdown','')}\n{page.get('html','')}"

    emails, seen = [], set()
    for m in _EMAIL_RE.findall(blob):
        e = m.lower().strip(".")
        if e in seen or _JUNK_EMAIL.search(e) or len(e) > 80:
            continue
        seen.add(e)
        emails.append(e)

    priority = ("info@", "contact@", "hello@", "office@", "owner@", "sales@",
                "admin@", "service@")
    emails.sort(key=lambda e: (0 if e.startswith(priority) else 1, len(e)))

    phones, pseen = [], set()
    for area, exch, last in _PHONE_RE.findall(blob):
        p = f"+1{area}{exch}{last}"
        if p not in pseen:
            pseen.add(p)
            phones.append(p)

    return {"emails": emails[:5], "phones": phones[:5]}


def find_official_site(business_name, city, state, timeout=45):
    """Search for a business's own website.

    Skips directory aggregators -- a Yelp page is not the business's site, and
    treating it as one would score them as 'has a website' when they do not.
    """
    q = f'"{business_name}" {city} {state} official website'
    res = search(q, limit=5, timeout=timeout)
    if not res["ok"]:
        return {"ok": False, "error": res["error"], "url": ""}

    directories = (
        "yelp.com", "facebook.com", "instagram.com", "linkedin.com",
        "yellowpages.com", "bbb.org", "mapquest.com", "angi.com",
        "thumbtack.com", "houzz.com", "nextdoor.com", "tripadvisor.com",
        "indeed.com", "zillow.com", "realtor.com", "manta.com", "chamberof",
    )
    for r in res["results"]:
        host = (r["url"].split("/")[2] if "://" in r["url"] else r["url"]).lower()
        if not any(d in host for d in directories):
            return {"ok": True, "url": r["url"], "title": r["title"], "error": ""}

    return {"ok": True, "url": "", "title": "",
            "error": "only directory listings found"}
