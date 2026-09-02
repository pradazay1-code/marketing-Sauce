"""State licensing boards — newly licensed professionals.

The highest-urgency segment in the taxonomy. A real estate agent licensed last
month has a commission budget, no brand, no website, and no marketing support
from their brokerage. Nobody works this list systematically because the data is
public but awkward to get at.

CREDIT STRATEGY
---------------
Free HTTP first. These are mostly classic ASP/HTML pages, so `requests` reads
them for nothing. Firecrawl is a *fallback* for JS-rendered boards only, is
budget-checked before every call, and every result is cached so the same page is
never paid for twice.

A roster pull is cheap either way -- a search returns many licensees per page.
The expensive part is enriching each one, which is deliberately a separate,
opt-in step. Newly licensed agents usually have no website at all, so the audit
has nothing to scrape and enrichment is often pointless.

ENDPOINT CONFIGURATION
----------------------
State licensing portals change and several sit behind Salesforce or Accela front
ends. Rather than hard-code URLs that rot, each board is a template that can be
overridden with the LICENSE_BOARDS env var (JSON). `probe()` reports exactly what
came back from a live request so a broken board can be diagnosed and corrected
from the deployed app without a redeploy.
"""

import json
import os
import re
from datetime import datetime, timedelta

import requests

from .base import Candidate, Source, register

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
TIMEOUT = 30

# Default boards. Override wholesale with LICENSE_BOARDS as JSON.
#
# `url` may contain {profession} and {page}. `method` is get or post; post
# bodies come from `data`. Templates are conservative: they aim at the classic
# public search endpoints rather than the JS portals, because those are the ones
# that can be read for free.
DEFAULT_BOARDS = {
    "MA": {
        "label": "Massachusetts DOL — Check a License",
        "url": "https://licensing.reg.state.ma.us/public/dpl_licsearch/dpl_search_result.asp",
        "method": "get",
        "params": {"profession": "RE", "licensetype": "RS", "page": "{page}"},
        "portal": "https://www.mass.gov/info-details/division-of-occupational-licensure-check-a-license",
        "note": "New licences appear within 24-48 hours of issuance.",
    },
    "RI": {
        "label": "Rhode Island DBR — Licensee Search",
        "url": "https://dbr.ri.gov/divisions/commlicensing/realestate.php",
        "method": "get",
        "params": {},
        "portal": "https://dbr.ri.gov/divisions/commlicensing/realestate.php",
        "note": "RI publishes periodic licensee lists rather than a live search.",
    },
    "CT": {
        "label": "Connecticut eLicense",
        "url": "https://www.elicense.ct.gov/Lookup/LicenseLookup.aspx",
        "method": "get",
        "params": {},
        "portal": "https://www.elicense.ct.gov/",
        "note": "ASP.NET postback form; usually needs the Firecrawl fallback.",
    },
}


def boards():
    raw = os.getenv("LICENSE_BOARDS", "").strip()
    if not raw:
        return dict(DEFAULT_BOARDS)
    try:
        override = json.loads(raw)
        merged = dict(DEFAULT_BOARDS)
        for k, v in override.items():
            merged[k.upper()] = {**merged.get(k.upper(), {}), **v}
        return merged
    except (ValueError, TypeError) as e:
        print(f"[licenses] LICENSE_BOARDS is not valid JSON, using defaults: {e}")
        return dict(DEFAULT_BOARDS)


def _build_url(board, page=1):
    url = board["url"].replace("{page}", str(page))
    params = {k: str(v).replace("{page}", str(page))
              for k, v in (board.get("params") or {}).items()}
    return url, params


def fetch_free(url, params=None):
    """Plain HTTP. Costs nothing. Returns (ok, html, note)."""
    try:
        r = requests.get(url, params=params or {},
                         headers={"User-Agent": UA,
                                  "Accept": "text/html,application/xhtml+xml"},
                         timeout=TIMEOUT)
    except requests.RequestException as e:
        return False, "", f"network: {str(e)[:140]}"

    if r.status_code >= 400:
        return False, "", f"HTTP {r.status_code}"
    html = r.text or ""
    if len(html) < 500:
        return False, html, f"response too short ({len(html)} bytes)"
    # A page whose body is mostly a script tag is JS-rendered; plain HTTP
    # cannot read it and Firecrawl is the only way through.
    if re.search(r"<div[^>]+id=[\"']root[\"']", html) and len(
            re.sub(r"<script.*?</script>", "", html, flags=re.S | re.I)) < 2000:
        return False, html, "JS-rendered shell — needs Firecrawl"
    return True, html, ""


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

_DATE_RE = re.compile(
    r"\b(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}-\d{2}-\d{2})\b")
_LIC_RE = re.compile(r"\b(\d{6,9})\b")


def parse_rows(html, state):
    """Pull licensee rows out of a results table.

    Written defensively: these boards render as HTML tables with varying
    column orders, so columns are identified by content shape (a date looks
    like a date, a licence number looks like a number) rather than position.
    Anything unrecognisable is skipped rather than guessed at.
    """
    if not html:
        return []

    try:
        from bs4 import BeautifulSoup
    except ImportError:
        return []

    soup = BeautifulSoup(html, "html.parser")
    out = []

    for table in soup.find_all("table"):
        rows = table.find_all("tr")
        if len(rows) < 2:
            continue
        for tr in rows[1:]:
            cells = [c.get_text(" ", strip=True)
                     for c in tr.find_all(["td", "th"])]
            cells = [c for c in cells if c]
            if len(cells) < 2:
                continue

            name = _pick_name(cells)
            if not name:
                continue

            joined = " | ".join(cells)
            dates = _DATE_RE.findall(joined)
            lic = ""
            for c in cells:
                m = _LIC_RE.fullmatch(c.strip())
                if m:
                    lic = m.group(1)
                    break

            city = _pick_city(cells, name)

            out.append({
                "name": _clean_name(name),
                "license_number": lic,
                "issue_date": _norm_date(dates[0]) if dates else "",
                "city": city,
                "state": state,
                "raw_cells": cells[:8],
            })
    return out


# Licence-type and status vocabulary. Without this the city heuristic happily
# returns "Salesperson", because it is also a plain alphabetic word.
_NOT_A_CITY = {
    "salesperson", "sales person", "broker", "associate broker", "agent",
    "realtor", "real estate", "individual", "corporation", "partnership",
    "sole proprietor", "active", "inactive", "expired", "current", "valid",
    "suspended", "revoked", "surrendered", "pending", "lapsed", "renewed",
    "license", "licence", "licensee", "type", "status", "name", "city",
    "town", "none", "n/a", "yes", "no", "primary", "secondary", "residential",
    "commercial", "affiliated", "unaffiliated",
}


def _pick_name(cells):
    """Best licensee-name candidate from a row of unlabelled cells.

    Scored rather than first-match, because column order varies between boards
    and a first-match rule happily returns "Fall River" when the city column
    comes before the name. The comma in "RIVERA, LUZ A" is the strongest signal
    these registries give, since they almost all render LAST, FIRST.
    """
    best, best_score = "", 0
    for c in cells:
        v = c.strip()
        if any(ch.isdigit() for ch in v) or not (4 < len(v) < 70):
            continue
        low = v.lower()
        if low in _NOT_A_CITY or any(
                w in low for w in ("license", "status", "salesper", "broker")):
            continue
        words = v.replace(",", " ").split()
        if len(words) < 2:
            continue
        score = 1
        if "," in v:
            score += 3                       # LAST, FIRST -- a person
        if v.upper() == v:
            score += 2                       # registries shout names
        if 2 <= len(words) <= 4:
            score += 1
        if score > best_score:
            best, best_score = v, score
    return best


def _pick_city(cells, name):
    """Best city candidate from a row of unlabelled cells.

    Cities are alphabetic, are not the licensee's name, and are not licence-type
    or status words. Scanned right-to-left because boards almost always place
    location after name and licence type.
    """
    for c in reversed(cells):
        v = c.strip()
        if not re.fullmatch(r"[A-Za-z .'-]{3,28}", v):
            continue
        low = v.lower()
        if low in _NOT_A_CITY:
            continue
        if any(w in low for w in ("license", "broker", "salesper", "status")):
            continue
        if low in name.lower() or v.lower() in ("mr", "ms", "mrs"):
            continue
        return v
    return ""


def _clean_name(raw):
    """'DOE, JANE M' -> 'Jane M Doe'."""
    n = re.sub(r"\s+", " ", raw).strip(" ,")
    if "," in n:
        last, _, first = n.partition(",")
        n = f"{first.strip()} {last.strip()}"
    if n.isupper() or n.islower():
        n = " ".join(w.capitalize() for w in n.split())
    return n[:80]


def _norm_date(d):
    for fmt in ("%m/%d/%Y", "%m-%d-%Y", "%Y-%m-%d", "%m/%d/%y"):
        try:
            return datetime.strptime(d, fmt).date().isoformat()
        except ValueError:
            continue
    return ""


def filter_recent(rows, days=90):
    """Keep only licences issued inside the window.

    Rows with no parseable date are kept -- a board that does not publish issue
    dates should not silently return nothing.
    """
    if not days:
        return rows
    cutoff = (datetime.now() - timedelta(days=days)).date().isoformat()
    return [r for r in rows if not r.get("issue_date")
            or r["issue_date"] >= cutoff]


# ---------------------------------------------------------------------------
# Public entry points
# ---------------------------------------------------------------------------

def probe(state="MA", use_credits=False):
    """Diagnose a board without committing to a run.

    Reports what a live request actually returned, so a changed endpoint can be
    identified and corrected via LICENSE_BOARDS from the deployed app.
    """
    from research import budget

    b = boards().get(state.upper())
    if not b:
        return {"ok": False, "error": f"No board configured for {state}"}

    url, params = _build_url(b, 1)
    ok, html, note = fetch_free(url, params)
    result = {
        "state": state.upper(),
        "label": b.get("label", ""),
        "url": url,
        "params": params,
        "portal": b.get("portal", ""),
        "note": b.get("note", ""),
        "free_fetch_ok": ok,
        "free_fetch_note": note,
        "bytes": len(html or ""),
        "credits_spent": 0,
    }

    if ok:
        rows = parse_rows(html, state.upper())
        result["rows_parsed"] = len(rows)
        result["sample"] = rows[:5]
        result["ok"] = True
        result["verdict"] = (
            f"Free HTTP works — parsed {len(rows)} rows at zero credit cost."
            if rows else
            "Page loaded free, but no licensee table was recognised. "
            "The endpoint may need different params — set LICENSE_BOARDS.")
        return result

    if not use_credits:
        result["ok"] = False
        result["verdict"] = (
            f"Free fetch failed ({note}). Re-run the probe with 'use credits' "
            "to try Firecrawl — that costs 1 credit.")
        return result

    page = budget.guarded_scrape(url, "license_probe")
    result["credits_spent"] = page.get("credits_spent", 0)
    result["from_cache"] = page.get("from_cache", False)
    if not page.get("ok"):
        result["ok"] = False
        result["verdict"] = f"Firecrawl also failed: {page.get('error','')[:160]}"
        return result

    rows = parse_rows(page.get("html") or "", state.upper())
    result["rows_parsed"] = len(rows)
    result["sample"] = rows[:5]
    result["ok"] = bool(rows)
    result["verdict"] = (
        f"Firecrawl works — parsed {len(rows)} rows for "
        f"{result['credits_spent']} credit(s)."
        if rows else
        "Firecrawl fetched the page but no licensee table was recognised.")
    return result


def fetch_licensees(state="MA", pages=1, days=90, allow_credits=False,
                    max_credits=2):
    """Pull recent licensees. Free first, Firecrawl only if permitted.

    Returns rows plus an accounting of what it cost.
    """
    from research import budget

    b = boards().get(state.upper())
    if not b:
        return {"ok": False, "error": f"No board configured for {state}",
                "rows": [], "credits_spent": 0}

    all_rows, spent, notes = [], 0, []

    for page in range(1, max(1, min(pages, 5)) + 1):
        url, params = _build_url(b, page)
        ok, html, note = fetch_free(url, params)

        if not ok:
            if not allow_credits:
                notes.append(f"page {page}: free fetch failed ({note}); "
                             "credits not permitted")
                continue
            if spent >= max_credits:
                notes.append(f"page {page}: stopped, credit cap {max_credits} reached")
                break
            afford, msg = budget.can_afford(1)
            if not afford:
                notes.append(f"page {page}: {msg}")
                break
            got = budget.guarded_scrape(url, f"license_{state.lower()}")
            spent += got.get("credits_spent", 0)
            if not got.get("ok"):
                notes.append(f"page {page}: firecrawl failed ({got.get('error','')[:90]})")
                continue
            html = got.get("html") or ""
        else:
            notes.append(f"page {page}: fetched free")

        rows = parse_rows(html, state.upper())
        if not rows:
            notes.append(f"page {page}: no rows recognised")
            break
        all_rows.extend(rows)

    recent_rows = filter_recent(all_rows, days)
    return {
        "ok": True,
        "error": "",
        "state": state.upper(),
        "board": b.get("label", ""),
        "pages_tried": pages,
        "rows_found": len(all_rows),
        "rows_recent": len(recent_rows),
        "days": days,
        "rows": recent_rows,
        "credits_spent": spent,
        "notes": notes,
    }


class StateLicenses(Source):
    """Registered so licensees flow through the same consensus pipeline.

    Trust is high because this is a primary government record, not an
    aggregator's guess about who exists.
    """

    name = "licenses"
    trust = 0.95
    env_key = ""          # free HTTP path needs no credential

    def _search(self, term, city, state, limit):
        res = fetch_licensees(state=state, pages=1, days=90,
                              allow_credits=False)
        if not res.get("ok"):
            return []
        out = []
        for r in res["rows"][:limit]:
            out.append(Candidate(
                business_name=r["name"],
                city=r.get("city") or city,
                state=r.get("state") or state,
                category="Real Estate Agent (newly licensed)",
                source_id=r.get("license_number", ""),
                raw={"issue_date": r.get("issue_date", "")},
            ))
        return out


register(StateLicenses())
