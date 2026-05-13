#!/usr/bin/env python3
"""
crm_find_leads.py
Find local MA/RI/CT businesses that don't have a website, normalize them
into the CRM JSON schema, score them, and merge into raw_leads.json.

This script chains the three deterministic pieces:
  1. Search DuckDuckGo for "{type} {city} {state}" + "no website"-style queries
  2. Parse business names/addresses from result snippets
  3. Run crm_scrape_contacts.enrich() to pull phone+email
  4. Run crm_score_leads.score_lead() to assign priority

It is intentionally conservative: the LLM-driven find_leads_web.py covers
deeper discovery. This script is the deterministic gap-filler.

Usage:
  python execution/crm_find_leads.py --state MA --type Barbershop --count 10
  python execution/crm_find_leads.py --state RI --city Providence --type Bakery
"""
import argparse
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

# Reuse helpers from sibling scripts
sys.path.insert(0, str(Path(__file__).parent))
from crm_score_leads import score_lead  # noqa: E402
from crm_scrape_contacts import ddg_search, http_get, enrich  # noqa: E402

DEFAULT_OUT = Path("clients/leads/raw_leads.json")

CITY_HINTS = {
    "MA": ["Worcester", "Boston", "Springfield", "Lowell", "Westborough",
           "Framingham", "Quincy", "Newton", "Salem", "New Bedford"],
    "RI": ["Providence", "Warwick", "Cranston", "Newport", "Pawtucket"],
    "CT": ["Hartford", "New Haven", "Bridgeport", "Stamford", "Waterbury"],
}


def discover(business_type: str, city: str, state: str, count: int) -> list[dict]:
    """Pull candidate businesses from DDG; very heuristic."""
    query = f'"{business_type}" "{city}" "{state}" -site:yelp.com -site:facebook.com'
    print(f"→ {query}")
    urls = ddg_search(query)
    if not urls:
        # Soften the query
        urls = ddg_search(f"{business_type} {city} {state}")

    found = []
    seen_names = set()
    for u in urls[:8]:
        try:
            html = http_get(u)
        except Exception as e:
            print(f"  ! {u}: {e}", file=sys.stderr)
            continue
        # Look for things that resemble business names: <title>, <h1>, <h2>
        candidates = re.findall(r"<(?:title|h1|h2)[^>]*>(.*?)</(?:title|h1|h2)>", html, re.I | re.S)
        for c in candidates[:6]:
            c = re.sub(r"<[^>]+>", "", c).strip()
            c = re.sub(r"\s+", " ", c)
            # Trim site-style suffixes
            c = re.split(r"\s[\-|—]\s", c)[0].strip()
            if 4 < len(c) < 80 and c.lower() not in seen_names:
                seen_names.add(c.lower())
                found.append({
                    "business_name": c,
                    "type": business_type,
                    "city": city,
                    "state": state,
                    "address": "",
                    "phone": "",
                    "email": "",
                    "owner_name": "",
                    "online_presence": "Unknown",
                    "website_status": "No Website",
                    "notes": f"Discovered via search for {business_type} in {city}, {state}",
                    "source": "DuckDuckGo Search",
                })
                if len(found) >= count:
                    break
        if len(found) >= count:
            break
        time.sleep(1.0)
    return found


def merge(existing: list[dict], new: list[dict]) -> tuple[list[dict], int]:
    """Insert new leads, deduping by (name.lower(), city.lower())."""
    seen = {(l.get("business_name", "").lower(), l.get("city", "").lower()) for l in existing}
    added = 0
    for n in new:
        k = (n["business_name"].lower(), n["city"].lower())
        if k in seen:
            continue
        existing.insert(0, n)
        seen.add(k)
        added += 1
    return existing, added


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--type", required=True, help="Business type (e.g. Barbershop, Bakery)")
    p.add_argument("--state", default="MA", choices=["MA", "RI", "CT"])
    p.add_argument("--city", default=None, help="Specific city (else searches multiple)")
    p.add_argument("--count", type=int, default=5, help="Target lead count")
    p.add_argument("--out", default=str(DEFAULT_OUT))
    p.add_argument("--no-enrich", action="store_true", help="Skip phone/email scraping")
    args = p.parse_args()

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    existing = json.loads(out.read_text()) if out.exists() else []
    if not isinstance(existing, list):
        existing = existing.get("leads", [])

    cities = [args.city] if args.city else CITY_HINTS[args.state]
    discovered: list[dict] = []
    per_city = max(1, args.count // len(cities))

    for c in cities:
        if len(discovered) >= args.count:
            break
        print(f"\n— Searching {args.type} in {c}, {args.state}")
        discovered.extend(discover(args.type, c, args.state, per_city))
        time.sleep(1.5)

    print(f"\nDiscovered {len(discovered)} candidates")

    if not args.no_enrich:
        for d in discovered:
            try:
                enrich(d)
            except Exception as e:
                print(f"  ! enrich error: {e}", file=sys.stderr)
            time.sleep(1.0)

    for d in discovered:
        score_lead(d)

    merged, added = merge(existing, discovered)
    merged.sort(key=lambda x: -x.get("score", 0))
    out.write_text(json.dumps(merged, indent=2))

    print(f"\n✓ Added {added} new leads → {out}")
    print(f"  Total in file: {len(merged)}")
    if discovered:
        top = max(discovered, key=lambda d: d.get("score", 0))
        print(f"  Top discovered: {top['business_name']} (score {top.get('score', 0)})")


if __name__ == "__main__":
    main()
