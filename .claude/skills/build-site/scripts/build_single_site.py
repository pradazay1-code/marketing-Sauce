#!/usr/bin/env python3
"""
Build single or batch HTML websites for leads.

Usage:
  Single: python .claude/skills/build-site/scripts/build_single_site.py --name "Joe's" --type "Barbershop" --city "Boston" --state "MA"
  Batch:  python .claude/skills/build-site/scripts/build_single_site.py --batch clients/leads/raw_leads.json
"""

import argparse
import json
import os
import re
import hashlib


# Color palettes by business type
PALETTES = {
    "restaurant":  {"color1": "#1a1a2e", "color2": "#e94560", "color3": "#fff3e0"},
    "barbershop":  {"color1": "#1a1a2e", "color2": "#e94560", "color3": "#f5f5f5"},
    "bakery":      {"color1": "#4e342e", "color2": "#ff8f00", "color3": "#efebe9"},
    "retail":      {"color1": "#4a148c", "color2": "#ff6f00", "color3": "#fce4ec"},
    "salon":       {"color1": "#880e4f", "color2": "#f48fb1", "color3": "#fce4ec"},
    "contractor":  {"color1": "#263238", "color2": "#ff6f00", "color3": "#eceff1"},
    "bar":         {"color1": "#263238", "color2": "#c9a96e", "color3": "#efebe9"},
    "seafood":     {"color1": "#01579b", "color2": "#e65100", "color3": "#e0f7fa"},
    "bookstore":   {"color1": "#1b5e20", "color2": "#4e342e", "color3": "#f1f8e9"},
    "default":     {"color1": "#2c3e50", "color2": "#e74c3c", "color3": "#f8f9fa"},
}


def get_palette(business_type):
    """Pick color palette based on business type keywords."""
    t = business_type.lower()
    for key, palette in PALETTES.items():
        if key in t:
            return palette
    # Deterministic fallback based on hash
    palettes = list(PALETTES.values())
    idx = int(hashlib.md5(t.encode()).hexdigest(), 16) % len(palettes)
    return palettes[idx]


def slugify(name):
    """Convert business name to URL-friendly slug."""
    slug = name.lower().strip()
    slug = re.sub(r"[''']", "", slug)
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    return slug.strip("-")


def generate_services(business_type):
    """Generate generic services based on business type."""
    t = business_type.lower()
    if "barber" in t:
        return ["Classic Haircuts", "Skin Fades", "Beard Trims", "Kids Cuts", "Hot Towel Shaves", "Line-Ups"]
    elif "restaurant" in t or "food" in t or "kitchen" in t or "grill" in t:
        return ["Dine-In", "Takeout & Delivery", "Catering", "Private Events", "Daily Specials", "Family Platters"]
    elif "bakery" in t or "coffee" in t:
        return ["Fresh Breads", "Pastries", "Espresso & Coffee", "Cakes & Special Orders", "Breakfast", "Seasonal Menu"]
    elif "salon" in t or "beauty" in t:
        return ["Haircuts & Styling", "Color & Highlights", "Blowouts", "Bridal Services", "Treatments", "Waxing"]
    elif "auto" in t or "mechanic" in t:
        return ["Oil Changes", "Brake Service", "Engine Diagnostics", "Tire Service", "AC Repair", "Inspections"]
    elif "vintage" in t or "clothing" in t or "apparel" in t:
        return ["Curated Collections", "Vintage Finds", "Accessories", "Seasonal Drops", "Buy & Trade", "Gift Cards"]
    elif "jewelry" in t:
        return ["Handcrafted Pieces", "Custom Orders", "Rings & Bracelets", "Earrings", "Gift Sets", "Bridal"]
    elif "book" in t:
        return ["Fiction & Non-Fiction", "Children's Books", "Local Authors", "Book Clubs", "Special Orders", "Gifts"]
    elif "seafood" in t or "fish" in t:
        return ["Lobster Rolls", "Fried Clams", "Fish & Chips", "Raw Bar", "Chowder", "Daily Catch"]
    elif "pizza" in t:
        return ["Classic Pies", "Specialty Pizza", "Slices", "Calzones", "Salads", "Desserts"]
    else:
        return ["Our Services", "Consultations", "Custom Solutions", "Quality Products", "Customer Support", "Special Requests"]


TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{name} | {city}, {state}</title>
<meta name="description" content="{name} — {business_type} in {city}, {state}. Visit us today!">
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:'Segoe UI',system-ui,-apple-system,sans-serif;color:#333;line-height:1.6}}
nav{{background:{color1};padding:15px 30px;display:flex;justify-content:space-between;align-items:center;position:sticky;top:0;z-index:100;box-shadow:0 2px 10px rgba(0,0,0,0.2)}}
.logo{{font-size:1.5rem;font-weight:800;color:#fff;letter-spacing:1px}}
.logo span{{color:{color2}}}
nav ul{{list-style:none;display:flex;gap:25px}}
nav a{{color:#fff;text-decoration:none;font-weight:500;font-size:0.95rem;transition:color 0.3s}}
nav a:hover{{color:{color2}}}
.hero{{background:linear-gradient(135deg,{color1} 0%,{color2} 100%);color:#fff;padding:100px 30px;text-align:center}}
.hero h1{{font-size:3rem;margin-bottom:15px;letter-spacing:2px}}
.hero p{{font-size:1.3rem;opacity:0.9;max-width:600px;margin:0 auto 30px}}
.btn{{display:inline-block;padding:14px 35px;background:{color2};color:#fff;text-decoration:none;border-radius:50px;font-weight:700;font-size:1rem;transition:transform 0.3s,box-shadow 0.3s}}
.btn:hover{{transform:translateY(-2px);box-shadow:0 5px 20px rgba(0,0,0,0.3)}}
section{{padding:70px 30px;max-width:1100px;margin:0 auto}}
.section-title{{text-align:center;font-size:2rem;margin-bottom:10px;color:{color1}}}
.section-sub{{text-align:center;color:#666;margin-bottom:40px;font-size:1.05rem}}
.about-text{{max-width:750px;margin:0 auto;text-align:center;font-size:1.1rem;color:#555}}
.services-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:25px}}
.service-card{{background:{color3};border-radius:12px;padding:30px;text-align:center;border-left:4px solid {color2};transition:transform 0.3s,box-shadow 0.3s}}
.service-card:hover{{transform:translateY(-5px);box-shadow:0 10px 25px rgba(0,0,0,0.1)}}
.service-card h3{{color:{color1};margin-bottom:8px;font-size:1.15rem}}
.hours-box{{background:{color1};color:#fff;border-radius:12px;padding:40px;text-align:center;max-width:600px;margin:0 auto}}
.hours-box h2{{margin-bottom:15px;font-size:1.8rem}}
.hours-box p{{font-size:1.15rem;opacity:0.9}}
.hours-box .address{{margin-top:15px;font-size:1rem;opacity:0.75}}
.cta{{background:linear-gradient(135deg,{color2} 0%,{color1} 100%);color:#fff;padding:60px 30px;text-align:center}}
.cta h2{{font-size:2rem;margin-bottom:15px}}
.cta p{{font-size:1.15rem;opacity:0.9;margin-bottom:25px}}
.btn-light{{background:#fff;color:{color1};padding:14px 35px;border-radius:50px;text-decoration:none;font-weight:700;transition:transform 0.3s}}
.btn-light:hover{{transform:translateY(-2px)}}
footer{{background:{color1};color:#fff;text-align:center;padding:25px;font-size:0.9rem;opacity:0.8}}
@media(max-width:768px){{
  .hero h1{{font-size:2rem}}
  .hero p{{font-size:1rem}}
  nav ul{{display:none}}
  section{{padding:50px 20px}}
}}
</style>
</head>
<body>
<nav>
  <div class="logo">{logo_first}<span>{logo_second}</span></div>
  <ul>
    <li><a href="#about">About</a></li>
    <li><a href="#services">Services</a></li>
    <li><a href="#hours">Hours</a></li>
    <li><a href="#contact">Contact</a></li>
  </ul>
</nav>
<div class="hero">
  <h1>{name}</h1>
  <p>{tagline}</p>
  <a href="#contact" class="btn">Get In Touch</a>
</div>
<section id="about">
  <h2 class="section-title">About Us</h2>
  <p class="section-sub">{business_type} in {city}, {state}</p>
  <p class="about-text">{about}</p>
</section>
<section id="services">
  <h2 class="section-title">What We Offer</h2>
  <p class="section-sub">Quality products and services you can count on</p>
  <div class="services-grid">
{services_html}
  </div>
</section>
<section id="hours">
  <div class="hours-box">
    <h2>Hours & Location</h2>
    <p>{hours}</p>
    <p class="address">{city}, {state}</p>
  </div>
</section>
<div class="cta" id="contact">
  <h2>Ready to Visit?</h2>
  <p>Stop by {name} today. We'd love to see you!</p>
  <a href="https://maps.google.com/?q={name_encoded}+{city_encoded}+{state}" class="btn-light" target="_blank">Get Directions</a>
</div>
<footer>
  <p>&copy; 2026 {name}. All rights reserved. | Website by One Vision Marketing</p>
</footer>
</body>
</html>"""


def build_site(name, business_type, city, state, output_dir="clients/leads/websites"):
    """Build a single website and save to disk."""
    slug = slugify(name)
    palette = get_palette(business_type)
    services = generate_services(business_type)

    # Logo split
    parts = name.split()
    if len(parts) >= 2:
        logo_first = " ".join(parts[:-1]) + " "
        logo_second = parts[-1]
    else:
        logo_first = name
        logo_second = ""

    # Services HTML
    services_html = ""
    for s in services:
        services_html += f'    <div class="service-card"><h3>{s}</h3></div>\n'

    # Tagline
    tagline = f"Your local {business_type.lower()} in {city}."

    # About
    about = (f"{name} is a {business_type.lower()} proudly serving the {city}, {state} community. "
             f"We're dedicated to providing quality products and exceptional service to every customer who walks through our doors.")

    html = TEMPLATE.format(
        name=name,
        business_type=business_type,
        city=city,
        state=state,
        tagline=tagline,
        about=about,
        color1=palette["color1"],
        color2=palette["color2"],
        color3=palette["color3"],
        hours="Call for hours",
        logo_first=logo_first,
        logo_second=logo_second,
        services_html=services_html,
        name_encoded=name.replace(" ", "+"),
        city_encoded=city.replace(" ", "+"),
    )

    folder = os.path.join(output_dir, slug)
    os.makedirs(folder, exist_ok=True)
    filepath = os.path.join(folder, "index.html")
    with open(filepath, "w") as f:
        f.write(html)
    print(f"Built: {filepath}")
    return filepath


def main():
    parser = argparse.ArgumentParser(description="One Vision Marketing — Website Builder")
    parser.add_argument("--name", help="Business name")
    parser.add_argument("--type", dest="business_type", default="Business", help="Business type")
    parser.add_argument("--city", default="Boston", help="City")
    parser.add_argument("--state", default="MA", help="State")
    parser.add_argument("--batch", help="Path to raw_leads.json for batch build")
    parser.add_argument("--output", default="clients/leads/websites", help="Output directory")
    args = parser.parse_args()

    if args.batch:
        with open(args.batch, "r") as f:
            leads = json.load(f)
        print(f"Building {len(leads)} websites...\n")
        for lead in leads:
            build_site(
                name=lead.get("business_name", lead.get("name", "Business")),
                business_type=lead.get("type", lead.get("business_type", "Business")),
                city=lead.get("city", "Boston"),
                state=lead.get("state", "MA"),
                output_dir=args.output,
            )
        print(f"\nDone! {len(leads)} websites built.")
    elif args.name:
        build_site(args.name, args.business_type, args.city, args.state, args.output)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
