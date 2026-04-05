#!/usr/bin/env python3
"""
Generate personalized cold outreach email drafts from leads.

Usage:
    python .claude/skills/cold-outreach/scripts/generate_outreach.py \
        --leads clients/leads/raw_leads.json \
        --output clients/leads/outreach_drafts.json

Drafts are saved to JSON. Actual sending is done via Gmail MCP after user approval.
"""

import argparse
import json
import os
import re
import sys
from datetime import date


def slugify(name):
    slug = name.lower().strip()
    slug = re.sub(r"[''']s\b", "s", slug)
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    return slug.strip("-")


def generate_draft(lead, site_base_url=""):
    """Generate a personalized cold outreach email for a lead."""
    name = lead["business_name"]
    biz_type = lead.get("type", "business")
    city = lead.get("city", "")
    state = lead.get("state", "MA")
    owner = lead.get("owner_name", "")
    notes = lead.get("notes", "")

    greeting = f"Hi {owner}" if owner else "Hi there"

    # Build mockup link if we have a site URL base
    slug = slugify(name)
    mockup_line = ""
    if site_base_url:
        mockup_url = f"{site_base_url.rstrip('/')}/sites/{slug}/"
        mockup_line = f"\nI actually went ahead and put together a quick mockup for {name} — no strings attached:\n{mockup_url}\n"

    subject = f"Free Website Mockup for {name}"
    if len(subject) > 50:
        subject = f"Website for {name}"

    body = f"""{greeting},

I came across {name} and love what you're building in {city}. I noticed you don't currently have a website — I'd love to help change that.

I run Marketing Sauce, a local digital marketing agency. We build clean, mobile-friendly websites for small businesses in the {state} area.
{mockup_line}
I'd be happy to put together a free mockup for you — no strings attached. If you like it, we can talk pricing. If not, no worries at all.

Would you be open to a quick 5-minute call this week?

Best,
Marketing Sauce
"""

    return {
        "lead_name": name,
        "lead_type": biz_type,
        "lead_city": city,
        "subject": subject,
        "body": body.strip(),
        "status": "draft",
        "generated_date": str(date.today()),
    }


def main():
    parser = argparse.ArgumentParser(description="Generate outreach email drafts")
    parser.add_argument("--leads", required=True, help="Path to raw_leads.json")
    parser.add_argument("--output", default="clients/leads/outreach_drafts.json", help="Output path")
    parser.add_argument("--site-url", default="", help="Base URL for mockup sites (e.g. https://user.github.io/repo)")
    parser.add_argument("--priority", default="all", choices=["HIGH", "MEDIUM", "all"], help="Filter by priority")
    args = parser.parse_args()

    with open(args.leads) as f:
        leads = json.load(f)

    if args.priority != "all":
        leads = [l for l in leads if l.get("priority", "").upper() == args.priority]

    print(f"Generating drafts for {len(leads)} leads...")
    drafts = []
    for lead in leads:
        draft = generate_draft(lead, site_base_url=args.site_url)
        drafts.append(draft)
        print(f"  Draft: {draft['lead_name']} ({draft['lead_city']})")

    os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
    with open(args.output, "w") as f:
        json.dump(drafts, f, indent=2)

    print(f"\nSaved {len(drafts)} drafts to {args.output}")
    print("Review drafts and send via Gmail MCP with user approval.")


if __name__ == "__main__":
    main()
