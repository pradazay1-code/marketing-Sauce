#!/usr/bin/env python3
"""
Generate outreach email drafts for all leads in raw_leads.json.

Usage:
  python .claude/skills/cold-outreach/scripts/generate_outreach.py \
    --leads clients/leads/raw_leads.json \
    --site-url "https://pradazay1-code.github.io/marketing-Sauce"
"""

import argparse
import json
import os
import sys

# Add project root to path so we can import email_outreach
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
from execution.email_outreach import generate_email


def main():
    parser = argparse.ArgumentParser(description="One Vision Marketing — Outreach Draft Generator")
    parser.add_argument("--leads", required=True, help="Path to raw_leads.json or outreach_drafts.json")
    parser.add_argument("--site-url", default="https://pradazay1-code.github.io/marketing-Sauce",
                        help="Base URL for deployed websites")
    parser.add_argument("--output", default="clients/leads/outreach_drafts.json",
                        help="Output path for drafts")
    args = parser.parse_args()

    with open(args.leads, "r") as f:
        leads = json.load(f)

    drafts = []
    for i, lead in enumerate(leads, 1):
        name = lead.get("business_name", lead.get("name", "Business"))
        owner = lead.get("owner_name", lead.get("owner", "there"))
        city = lead.get("city", "your area")
        state = lead.get("state", "MA")
        btype = lead.get("type", lead.get("business_type", "Business"))

        subject, body = generate_email(
            "cold-outreach",
            business_name=name,
            owner_name=owner if owner != "N/A" else "there",
            city=city,
            state=state,
        )

        # Build slug for website path
        slug = name.lower().strip()
        for ch in ["'", "'", "'"]:
            slug = slug.replace(ch, "")
        import re
        slug = re.sub(r"[^a-z0-9]+", "-", slug).strip("-")

        draft = {
            "id": i,
            "business_name": name,
            "owner_name": owner,
            "city": city,
            "state": state,
            "type": btype,
            "subject": subject,
            "body": body,
            "status": "pending_approval",
            "email": lead.get("email", ""),
            "website_built": os.path.exists(f"clients/leads/websites/{slug}/index.html"),
            "website_path": f"clients/leads/websites/{slug}/index.html",
            "website_url": f"{args.site_url}/clients/leads/websites/{slug}/",
        }
        drafts.append(draft)
        print(f"[{i}/{len(leads)}] Draft ready: {name}")

    # Save drafts
    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    with open(args.output, "w") as f:
        json.dump(drafts, f, indent=2)

    print(f"\nSaved {len(drafts)} drafts to {args.output}")
    print("Run 'mcp__gmail__send_message' for each approved draft to send.")


if __name__ == "__main__":
    main()
