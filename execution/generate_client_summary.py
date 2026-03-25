#!/usr/bin/env python3
"""
Generate a client summary document for tracking and email.
Usage: python generate_client_summary.py --client "client-name" --business "Business Type" --location "City, ST" --url "https://..."
"""
import argparse
import os
from datetime import datetime


def generate_summary(client_name: str, business_type: str, location: str,
                     github_url: str, services: list[str] | None = None) -> str:
    """Generate a formatted client summary in Markdown."""
    date = datetime.now().strftime("%B %d, %Y")
    display_name = client_name.replace("-", " ").title()

    services_list = services or ["Custom Website Design", "Mobile-Responsive Development", "SEO Optimization", "GitHub Pages Deployment"]
    services_md = "\n".join(f"- {s}" for s in services_list)

    summary = f"""# Client Summary: {display_name}

## Overview
| Field | Details |
|-------|---------|
| **Client** | {display_name} |
| **Business** | {business_type} |
| **Location** | {location} |
| **Date Delivered** | {date} |
| **Status** | Delivered |

## Live Website
- **GitHub Pages**: {github_url}
- **Standalone HTML**: `clients/{client_name}/index-standalone.html`
- **Wix-Ready HTML**: `clients/{client_name}/index-wix.html`

## Services Delivered
{services_md}

## Files
- `index.html` — Development version (relative image paths)
- `index-standalone.html` — Self-contained version (base64 embedded images)
- `index-wix.html` — Wix-compatible version (no html/head/body wrapper)
- `images/` — Original image assets
- `CLIENT_SUMMARY.md` — This file

## Notes
- All HTML is fully self-contained with inline CSS/JS
- Images are base64-encoded in standalone and Wix versions
- Site is mobile-responsive (tested at 320px, 768px, 1200px breakpoints)
- Wix version uses sticky positioning instead of fixed for navbar compatibility

---
*Generated on {date} by Marketing Sauce*
"""
    return summary


def update_tracker(client_name: str, business_type: str, github_url: str, tracker_path: str):
    """Append client entry to the master tracker."""
    date = datetime.now().strftime("%Y-%m-%d")
    display_name = client_name.replace("-", " ").title()

    entry = f"| {display_name} | {business_type} | [Live Site]({github_url}) | {date} | Delivered |\n"

    if not os.path.exists(tracker_path):
        header = """# Client Tracker

All client projects delivered by Marketing Sauce.

| Client | Business | Website | Date | Status |
|--------|----------|---------|------|--------|
"""
        with open(tracker_path, "w") as f:
            f.write(header + entry)
    else:
        with open(tracker_path, "a") as f:
            f.write(entry)


def main():
    parser = argparse.ArgumentParser(description="Generate client summary document")
    parser.add_argument("--client", required=True, help="Client folder name (e.g., north-atlantic-tattoo)")
    parser.add_argument("--business", required=True, help="Business type (e.g., Custom Tattoo Studio)")
    parser.add_argument("--location", required=True, help="Location (e.g., New Bedford, MA)")
    parser.add_argument("--url", required=True, help="GitHub Pages URL")
    parser.add_argument("--services", nargs="*", help="List of services delivered")
    args = parser.parse_args()

    # Paths
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    client_dir = os.path.join(base_dir, "clients", args.client)
    tracker_path = os.path.join(base_dir, "clients", "CLIENT_TRACKER.md")
    summary_path = os.path.join(client_dir, "CLIENT_SUMMARY.md")

    # Generate summary
    summary = generate_summary(args.client, args.business, args.location, args.url, args.services)

    os.makedirs(client_dir, exist_ok=True)
    with open(summary_path, "w") as f:
        f.write(summary)
    print(f"Summary saved to: {summary_path}")

    # Update master tracker
    update_tracker(args.client, args.business, args.url, tracker_path)
    print(f"Tracker updated: {tracker_path}")


if __name__ == "__main__":
    main()
