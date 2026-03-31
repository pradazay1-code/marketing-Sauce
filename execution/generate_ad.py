#!/usr/bin/env python3
"""
Ad Copy Generator for Marketing Sauce
Generates ad copy for Google, Facebook, and Instagram.

Usage:
    python execution/generate_ad.py --client "Joe's Barbershop" --service "Haircuts" --location "Boston, MA" --platform all
"""

import argparse
import os
from datetime import date


def generate_google_ad(client, service, location, cta):
    """Generate Google Ads copy."""
    return {
        "platform": "Google Ads",
        "headline_1": f"{service} in {location.split(',')[0]}"[:30],
        "headline_2": f"{client} - Book Today"[:30],
        "headline_3": f"Local & Trusted"[:30],
        "description_1": f"Professional {service.lower()} from {client}. Serving {location}. {cta}!"[:90],
        "description_2": f"Locally owned. Quality you can trust. Visit us in {location}."[:90],
    }


def generate_facebook_ad(client, service, location, cta):
    """Generate Facebook ad copy."""
    return {
        "platform": "Facebook",
        "primary_text": f"Looking for quality {service.lower()} in {location}? {client} has you covered. Locally owned, community trusted. {cta} today!",
        "headline": f"{service} — {client}"[:40],
        "description": f"Professional {service.lower()} in {location}. Book your appointment today.",
        "cta_button": "Learn More",
    }


def generate_instagram_ad(client, service, location, cta):
    """Generate Instagram ad copy."""
    city = location.split(",")[0].strip()
    city_tag = city.replace(" ", "")
    service_tag = service.replace(" ", "")
    client_tag = client.replace(" ", "").replace("'", "")
    caption = (
        f"Quality {service.lower()} right here in {city}.\n\n"
        f"{client} — locally owned, community driven.\n\n"
        f"{cta}\nLink in bio\n\n"
        f"#{city_tag} #{service_tag} #LocalBusiness #SupportLocal #SmallBusiness #{client_tag}"
    )
    return {
        "platform": "Instagram",
        "caption": caption,
    }


def format_output(ads):
    """Format ads for display/saving."""
    output = f"# Ad Campaign\n**Generated:** {date.today()}\n\n"
    for ad in ads:
        platform = ad.pop("platform")
        output += f"## {platform}\n"
        for key, value in ad.items():
            label = key.replace("_", " ").title()
            output += f"**{label}:** {value}\n"
        output += "\n"
    return output


def main():
    parser = argparse.ArgumentParser(description="Ad Copy Generator")
    parser.add_argument("--client", required=True, help="Client/business name")
    parser.add_argument("--service", required=True, help="Service to advertise")
    parser.add_argument("--location", required=True, help="Location (City, State)")
    parser.add_argument("--cta", default="Call now for a free quote", help="Call to action")
    parser.add_argument("--platform", default="all", choices=["google", "facebook", "instagram", "all"])
    parser.add_argument("--output", "-o", help="Output file path")
    args = parser.parse_args()

    ads = []
    if args.platform in ("google", "all"):
        ads.append(generate_google_ad(args.client, args.service, args.location, args.cta))
    if args.platform in ("facebook", "all"):
        ads.append(generate_facebook_ad(args.client, args.service, args.location, args.cta))
    if args.platform in ("instagram", "all"):
        ads.append(generate_instagram_ad(args.client, args.service, args.location, args.cta))

    output = format_output(ads)

    if args.output:
        os.makedirs(os.path.dirname(args.output), exist_ok=True)
        with open(args.output, "w") as f:
            f.write(output)
        print(f"Ad copy saved to {args.output}")
    else:
        print(output)


if __name__ == "__main__":
    main()
