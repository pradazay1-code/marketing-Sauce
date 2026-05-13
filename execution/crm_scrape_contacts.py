#!/usr/bin/env python3
"""
crm_scrape_contacts.py
Enrich leads with phone and email by scraping public sources.

Strategy (no paid APIs required):
  1. If the lead has a known social URL or directory listing, fetch it.
  2. Else, run a DuckDuckGo HTML search for "{business_name} {city} {state} contact"
     and walk the top result pages.
  3. Regex out the first phone number (US format) and the first email that
     does NOT look like a no-reply / image-tracking address.
  4. Skip leads that already have both phone + email.

Designed to be safe: 1 request/second, 12s timeout, no JS execution.

Usage:
  python execution/crm_scrape_contacts.py clients/leads/raw_leads.json
  python execution/crm_scrape_contacts.py --limit 5 --in raw.json --out enriched.json
"""
import argparse
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from html import unescape
from pathlib import Path

UA = "Mozilla/5.0 (compatible; AventisCRM-LeadBot/1.0; +contact:hello@aventis.example)"
TIMEOUT = 12

PHONE_RE = re.compile(
    r"\(?\b([2-9]\d{2})\)?[\s.\-]?([2-9]\d{2})[\s.\-]?(\d{4})\b"
)
EMAIL_RE = re.compile(
    r"\b([A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,})\b"
)
BAD_EMAIL_TOKENS = ("noreply", "no-reply", "donotreply", "wixpress", "sentry", "example.com")


def http_get(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        raw = r.read()
        ctype = r.headers.get("Content-Type", "")
        # crude charset detection
        charset = "utf-8"
        if "charset=" in ctype:
            charset = ctype.split("charset=")[-1].split(";")[0].strip() or "utf-8"
        return raw.decode(charset, errors="replace")


def ddg_search(query: str) -> list[str]:
    """Return up to 5 result URLs from the DuckDuckGo HTML endpoint."""
    url = "https://duckduckgo.com/html/?q=" + urllib.parse.quote_plus(query)
    try:
        html = http_get(url)
    except Exception as e:
        print(f"  ! search failed: {e}", file=sys.stderr)
        return []
    # DDG result links look like: /l/?uddg=<encoded-url>
    raw_links = re.findall(r'<a[^>]+class="result__a"[^>]+href="([^"]+)"', html)
    urls = []
    for href in raw_links:
        if href.startswith("/"):
            href = "https://duckduckgo.com" + href
        m = re.search(r"uddg=([^&]+)", href)
        if m:
            try:
                urls.append(urllib.parse.unquote(m.group(1)))
            except Exception:
                continue
        elif href.startswith("http"):
            urls.append(href)
        if len(urls) >= 5:
            break
    return urls


def extract_phone(text: str) -> str | None:
    for m in PHONE_RE.finditer(text):
        a, b, c = m.groups()
        return f"({a}) {b}-{c}"
    return None


def extract_email(text: str) -> str | None:
    for m in EMAIL_RE.finditer(text):
        e = m.group(1).lower()
        if any(tok in e for tok in BAD_EMAIL_TOKENS):
            continue
        # skip image/asset filenames that contain @
        if e.endswith((".png", ".jpg", ".jpeg", ".gif", ".svg")):
            continue
        return e
    return None


def enrich(lead: dict) -> dict:
    name = lead.get("business_name") or lead.get("name")
    city = lead.get("city", "")
    state = lead.get("state", "")

    has_phone = bool(lead.get("phone")) and lead["phone"] != "N/A"
    has_email = bool(lead.get("email")) and lead["email"] != "N/A"
    if has_phone and has_email:
        print(f"  ✓ {name}: already complete, skipping")
        return lead

    query = f'"{name}" {city} {state} contact phone email'
    print(f"  → searching: {query}")
    urls = ddg_search(query)
    time.sleep(1.2)

    phone = email = None
    for u in urls:
        # Skip social aggregators that block scrapers
        if any(d in u for d in ("facebook.com/login", "instagram.com/accounts")):
            continue
        try:
            html = http_get(u)
        except Exception as e:
            print(f"  ! fetch {u}: {e}", file=sys.stderr)
            continue
        text = unescape(re.sub(r"<[^>]+>", " ", html))
        if not phone:
            phone = extract_phone(text)
        if not email:
            email = extract_email(text)
        if phone and email:
            break
        time.sleep(1.0)

    changed = False
    if not has_phone and phone:
        lead["phone"] = phone
        changed = True
    if not has_email and email:
        lead["email"] = email
        changed = True

    if changed:
        print(f"  ✓ {name}: phone={lead.get('phone','—')}  email={lead.get('email','—')}")
    else:
        print(f"  ✗ {name}: nothing found")
    return lead


def main():
    p = argparse.ArgumentParser()
    p.add_argument("input", nargs="?", default="clients/leads/raw_leads.json")
    p.add_argument("--out", default=None)
    p.add_argument("--limit", type=int, default=0, help="Max leads to process (0 = all)")
    args = p.parse_args()

    src = Path(args.input)
    if not src.exists():
        print(f"ERROR: {src} not found", file=sys.stderr)
        sys.exit(1)

    leads = json.loads(src.read_text())
    if not isinstance(leads, list):
        leads = leads.get("leads", [])

    targets = leads if not args.limit else leads[: args.limit]
    print(f"Enriching {len(targets)} leads...")
    for i, lead in enumerate(targets, 1):
        print(f"[{i}/{len(targets)}] {lead.get('business_name') or lead.get('name')}")
        try:
            enrich(lead)
        except Exception as e:
            print(f"  ! error: {e}", file=sys.stderr)
        time.sleep(1.0)

    out = Path(args.out) if args.out else src
    out.write_text(json.dumps(leads, indent=2))
    print(f"\nWrote {len(leads)} leads → {out}")


if __name__ == "__main__":
    main()
