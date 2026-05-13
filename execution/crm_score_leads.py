#!/usr/bin/env python3
"""
crm_score_leads.py
Deterministic lead scoring engine. Mirrors the scoring logic in crm/index.html
so the same priority ranking is applied whether leads come in via the dashboard
or the Python pipeline.

Score (0-100):
  base 40
  + 25 if no website
  + 18 if outdated website
  + 14 if social-only
  + 8  if valid phone (>=10 digits)
  + 8  if email present
  + 5  if owner name known (not 'there')
  + 6  if high-LTV business type
  + 6  if "new/opening/expanding/ready/launching" in notes
  + 4  if "referral/recommended" in notes
Priority: HIGH >=75, MEDIUM >=55, else LOW.

Usage:
  python execution/crm_score_leads.py clients/leads/raw_leads.json
  python execution/crm_score_leads.py --in raw.json --out scored.json
"""
import argparse
import json
import re
import sys
from pathlib import Path

HIGH_VALUE_TYPES = {
    "restaurant", "pizzeria", "hardscaping", "tattoo", "mexican restaurant",
    "sailing charter", "cafe", "bakery", "auto detailing", "yoga studio",
    "barbershop", "salon", "spa", "gym", "landscaping",
}

NEW_SIGNAL = re.compile(r"\b(new|opened|opening|expanding|ready|launching|grand opening)\b", re.I)
REF_SIGNAL = re.compile(r"\b(referral|recommended|already (a|our) client)\b", re.I)


def score_lead(lead: dict) -> dict:
    s = 40

    website = (lead.get("website_status") or "").lower()
    online = (lead.get("online_presence") or "").lower()
    if "no website" in website or online == "none":
        s += 25
    elif "outdated" in website:
        s += 18
    elif "social" in website or "social" in online:
        s += 14

    phone = lead.get("phone") or ""
    if phone and phone != "N/A" and len(re.sub(r"\D", "", phone)) >= 10:
        s += 8

    email = lead.get("email") or ""
    if email and email != "N/A" and "@" in email:
        s += 8

    owner = (lead.get("owner") or lead.get("owner_name") or "").strip().lower()
    if owner and owner not in {"there", "n/a", ""}:
        s += 5

    btype = (lead.get("type") or "").lower()
    if any(t in btype for t in HIGH_VALUE_TYPES):
        s += 6

    notes = lead.get("notes") or ""
    if NEW_SIGNAL.search(notes):
        s += 6
    if REF_SIGNAL.search(notes):
        s += 4

    s = max(0, min(100, s))
    lead["score"] = s
    lead["priority"] = "HIGH" if s >= 75 else ("MEDIUM" if s >= 55 else "LOW")
    return lead


def main():
    p = argparse.ArgumentParser()
    p.add_argument("input", nargs="?", default="clients/leads/raw_leads.json")
    p.add_argument("--out", default=None, help="Output path (default: overwrite input)")
    args = p.parse_args()

    src = Path(args.input)
    if not src.exists():
        print(f"ERROR: {src} not found", file=sys.stderr)
        sys.exit(1)

    leads = json.loads(src.read_text())
    if not isinstance(leads, list):
        leads = leads.get("leads", [])

    for l in leads:
        score_lead(l)

    leads.sort(key=lambda x: -x.get("score", 0))

    out = Path(args.out) if args.out else src
    out.write_text(json.dumps(leads, indent=2))

    high = sum(1 for l in leads if l["priority"] == "HIGH")
    med = sum(1 for l in leads if l["priority"] == "MEDIUM")
    low = sum(1 for l in leads if l["priority"] == "LOW")
    print(f"Scored {len(leads)} leads → {out}")
    print(f"  HIGH:   {high}")
    print(f"  MEDIUM: {med}")
    print(f"  LOW:    {low}")
    if leads:
        print(f"  Top:    {leads[0].get('business_name') or leads[0].get('name')} (score {leads[0]['score']})")


if __name__ == "__main__":
    main()
