#!/usr/bin/env python3
"""
Build a single self-contained HTML website for a business lead.
All CSS/JS inline. Mobile responsive. SEO optimized.

Usage:
    python .claude/skills/build-site/scripts/build_single_site.py \
        --name "Joe's Barbershop" --type "Barbershop" --city "Boston" --state "MA"

    python .claude/skills/build-site/scripts/build_single_site.py \
        --batch clients/leads/raw_leads.json
"""

import argparse
import json
import os
import re
import sys

# Color schemes by business type
COLOR_SCHEMES = {
    "Barbershop":       {"primary": "#1a1a2e", "accent": "#e94560", "light": "#f5f5f5"},
    "Restaurant":       {"primary": "#2d3436", "accent": "#e17055", "light": "#ffeaa7"},
    "Mexican Restaurant": {"primary": "#2d3436", "accent": "#d63031", "light": "#ffeaa7"},
    "Indian Restaurant": {"primary": "#2c3e50", "accent": "#f39c12", "light": "#fdf2e9"},
    "Seafood Restaurant": {"primary": "#0c2461", "accent": "#0984e3", "light": "#dfe6e9"},
    "Bakery & Coffee":  {"primary": "#4a2c2a", "accent": "#d4a574", "light": "#fdf2e9"},
    "Vintage Clothing Shop": {"primary": "#2d132c", "accent": "#c56cf0", "light": "#f8e8f8"},
    "Jewelry Boutique": {"primary": "#2c2c54", "accent": "#d4af37", "light": "#f9f3e3"},
    "Cocktail Bar & Restaurant": {"primary": "#1a1a2e", "accent": "#c56cf0", "light": "#f0e6f6"},
    "Apparel & Accessories": {"primary": "#006266", "accent": "#00b894", "light": "#e0f7f0"},
    "Comfort Food Restaurant": {"primary": "#4a2c2a", "accent": "#fdcb6e", "light": "#fef9ef"},
    "Pizza Restaurant": {"primary": "#c0392b", "accent": "#f39c12", "light": "#fef9ef"},
    "Independent Bookstore": {"primary": "#2c3e50", "accent": "#27ae60", "light": "#eafaf1"},
    "default":          {"primary": "#2d3436", "accent": "#0984e3", "light": "#dfe6e9"},
}

def slugify(name):
    """Convert business name to URL-friendly slug."""
    slug = name.lower().strip()
    slug = re.sub(r"[''']s\b", "s", slug)
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = slug.strip("-")
    return slug

def get_colors(biz_type):
    """Get color scheme for business type."""
    return COLOR_SCHEMES.get(biz_type, COLOR_SCHEMES["default"])

def build_html(name, biz_type, city, state, address="", phone="", description="", services=None):
    """Generate complete self-contained HTML website."""
    colors = get_colors(biz_type)
    p = colors["primary"]
    a = colors["accent"]
    lt = colors["light"]

    if not description:
        description = f"Welcome to {name}, your local {biz_type.lower()} in {city}, {state}."

    if not services:
        services = _default_services(biz_type)

    services_html = ""
    for svc in services:
        services_html += f"""
            <div class="service-card">
                <h3>{svc['name']}</h3>
                <p>{svc['desc']}</p>
            </div>"""

    contact_info = ""
    if address:
        contact_info += f"<p><strong>Address:</strong> {address}, {city}, {state}</p>"
    else:
        contact_info += f"<p><strong>Location:</strong> {city}, {state}</p>"
    if phone and phone != "N/A":
        contact_info += f'<p><strong>Phone:</strong> <a href="tel:{phone}">{phone}</a></p>'

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="description" content="{name} - {biz_type} in {city}, {state}. {description[:120]}">
    <title>{name} | {biz_type} in {city}, {state}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; color: #333; line-height: 1.6; }}

        /* Navigation */
        nav {{ background: {p}; padding: 1rem 2rem; position: fixed; width: 100%; top: 0; z-index: 1000; display: flex; justify-content: space-between; align-items: center; }}
        .logo {{ color: white; font-size: 1.4rem; font-weight: 700; text-decoration: none; }}
        .logo span {{ color: {a}; }}
        .nav-links {{ list-style: none; display: flex; gap: 1.5rem; }}
        .nav-links a {{ color: #ccc; text-decoration: none; font-size: 0.95rem; transition: color 0.3s; }}
        .nav-links a:hover {{ color: {a}; }}
        .hamburger {{ display: none; flex-direction: column; cursor: pointer; gap: 5px; }}
        .hamburger span {{ width: 25px; height: 3px; background: white; border-radius: 3px; transition: 0.3s; }}

        /* Hero */
        .hero {{ background: linear-gradient(135deg, {p} 0%, {a} 100%); color: white; padding: 8rem 2rem 5rem; text-align: center; min-height: 80vh; display: flex; flex-direction: column; justify-content: center; }}
        .hero h1 {{ font-size: 3rem; margin-bottom: 1rem; }}
        .hero p {{ font-size: 1.2rem; max-width: 600px; margin: 0 auto 2rem; opacity: 0.9; }}
        .btn {{ display: inline-block; padding: 0.9rem 2.2rem; background: {a}; color: white; text-decoration: none; border-radius: 5px; font-weight: 600; font-size: 1rem; transition: transform 0.3s, box-shadow 0.3s; border: none; cursor: pointer; }}
        .btn:hover {{ transform: translateY(-2px); box-shadow: 0 4px 15px rgba(0,0,0,0.3); }}

        /* Sections */
        section {{ padding: 5rem 2rem; }}
        .section-title {{ text-align: center; font-size: 2rem; margin-bottom: 1rem; color: {p}; }}
        .section-subtitle {{ text-align: center; color: #666; max-width: 600px; margin: 0 auto 3rem; }}

        /* About */
        .about {{ background: {lt}; }}
        .about-content {{ max-width: 800px; margin: 0 auto; text-align: center; font-size: 1.1rem; }}

        /* Services */
        .services-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 2rem; max-width: 1000px; margin: 0 auto; }}
        .service-card {{ background: white; padding: 2rem; border-radius: 10px; box-shadow: 0 2px 15px rgba(0,0,0,0.08); text-align: center; transition: transform 0.3s; }}
        .service-card:hover {{ transform: translateY(-5px); }}
        .service-card h3 {{ color: {a}; margin-bottom: 0.8rem; font-size: 1.2rem; }}
        .service-card p {{ color: #666; font-size: 0.95rem; }}

        /* Contact */
        .contact {{ background: {lt}; }}
        .contact-info {{ max-width: 600px; margin: 0 auto; text-align: center; }}
        .contact-info p {{ margin: 0.5rem 0; font-size: 1.05rem; }}
        .contact-info a {{ color: {a}; }}

        /* CTA */
        .cta {{ background: linear-gradient(135deg, {p}, {a}); color: white; text-align: center; }}
        .cta h2 {{ font-size: 2rem; margin-bottom: 1rem; }}
        .cta p {{ margin-bottom: 2rem; opacity: 0.9; }}
        .cta .btn {{ background: white; color: {p}; }}

        /* Footer */
        footer {{ background: {p}; color: #aaa; text-align: center; padding: 2rem; font-size: 0.9rem; }}
        footer a {{ color: {a}; text-decoration: none; }}

        /* Mobile */
        @media (max-width: 768px) {{
            .hamburger {{ display: flex; }}
            .nav-links {{ display: none; position: absolute; top: 100%; left: 0; width: 100%; background: {p}; flex-direction: column; padding: 1rem 2rem; gap: 1rem; }}
            .nav-links.active {{ display: flex; }}
            .hero h1 {{ font-size: 2rem; }}
            .hero {{ padding: 6rem 1.5rem 3rem; min-height: 60vh; }}
            section {{ padding: 3rem 1.5rem; }}
        }}
    </style>
</head>
<body>
    <nav>
        <a href="#" class="logo">{name.split()[0]}<span>{''.join(name.split()[1:2])}</span></a>
        <div class="hamburger" onclick="document.querySelector('.nav-links').classList.toggle('active')">
            <span></span><span></span><span></span>
        </div>
        <ul class="nav-links">
            <li><a href="#about">About</a></li>
            <li><a href="#services">Services</a></li>
            <li><a href="#contact">Contact</a></li>
        </ul>
    </nav>

    <section class="hero">
        <h1>{name}</h1>
        <p>{description}</p>
        <a href="#contact" class="btn">Get In Touch</a>
    </section>

    <section class="about" id="about">
        <h2 class="section-title">About Us</h2>
        <div class="about-content">
            <p>{description} We're proud to serve the {city}, {state} community with quality {biz_type.lower()} services.</p>
        </div>
    </section>

    <section id="services">
        <h2 class="section-title">What We Offer</h2>
        <p class="section-subtitle">Quality services tailored to our community.</p>
        <div class="services-grid">{services_html}
        </div>
    </section>

    <section class="contact" id="contact">
        <h2 class="section-title">Visit Us</h2>
        <div class="contact-info">
            {contact_info}
            <p style="margin-top:1.5rem;color:#666;">Stop by and see us today!</p>
        </div>
    </section>

    <section class="cta">
        <h2>Ready to Visit {name}?</h2>
        <p>We'd love to see you. Come check us out!</p>
        <a href="#contact" class="btn">Contact Us</a>
    </section>

    <footer>
        <p>&copy; 2026 {name}. All rights reserved.</p>
        <p style="margin-top:0.5rem;">Website by <a href="#">Marketing Sauce</a></p>
    </footer>
</body>
</html>"""
    return html


def _default_services(biz_type):
    """Return default services based on business type."""
    defaults = {
        "Barbershop": [
            {"name": "Haircuts", "desc": "Classic and modern cuts for all styles."},
            {"name": "Beard Trims", "desc": "Sharp beard shaping and grooming."},
            {"name": "Hot Towel Shave", "desc": "Relaxing traditional straight razor shave."},
        ],
        "Restaurant": [
            {"name": "Dine In", "desc": "Enjoy our full menu in a comfortable setting."},
            {"name": "Takeout", "desc": "Fresh food ready to go when you are."},
            {"name": "Catering", "desc": "Let us cater your next event."},
        ],
        "Mexican Restaurant": [
            {"name": "Authentic Cuisine", "desc": "Traditional Mexican recipes made fresh daily."},
            {"name": "Craft Cocktails", "desc": "Margaritas, mezcal, and more."},
            {"name": "Catering", "desc": "Bring the fiesta to your next event."},
        ],
        "Bakery & Coffee": [
            {"name": "Artisan Breads", "desc": "Freshly baked breads made from scratch."},
            {"name": "Pastries", "desc": "Croissants, muffins, and sweet treats."},
            {"name": "Espresso Bar", "desc": "Premium coffee and espresso drinks."},
        ],
        "Independent Bookstore": [
            {"name": "New Releases", "desc": "Latest titles across all genres."},
            {"name": "Local Authors", "desc": "Curated selection from local writers."},
            {"name": "Events", "desc": "Book signings, readings, and community events."},
        ],
    }
    return defaults.get(biz_type, [
        {"name": "Quality Products", "desc": "Carefully selected items for our customers."},
        {"name": "Expert Service", "desc": "Friendly, knowledgeable staff ready to help."},
        {"name": "Local Community", "desc": "Proudly serving our local neighborhood."},
    ])


def build_from_lead(lead):
    """Build site from a lead dict (from raw_leads.json)."""
    name = lead["business_name"]
    slug = slugify(name)
    output_dir = f"clients/leads/websites/{slug}"
    os.makedirs(output_dir, exist_ok=True)

    html = build_html(
        name=name,
        biz_type=lead.get("type", "Business"),
        city=lead.get("city", ""),
        state=lead.get("state", "MA"),
        address=lead.get("address", ""),
        phone=lead.get("phone", ""),
        description=lead.get("notes", ""),
    )

    output_path = os.path.join(output_dir, "index.html")
    with open(output_path, "w") as f:
        f.write(html)
    print(f"  Built: {output_path}")
    return output_path


def main():
    parser = argparse.ArgumentParser(description="Build single-page HTML websites")
    parser.add_argument("--name", help="Business name")
    parser.add_argument("--type", default="Business", help="Business type")
    parser.add_argument("--city", default="", help="City")
    parser.add_argument("--state", default="MA", help="State")
    parser.add_argument("--address", default="", help="Street address")
    parser.add_argument("--phone", default="", help="Phone number")
    parser.add_argument("--desc", default="", help="Business description")
    parser.add_argument("--output", default="", help="Output file path")
    parser.add_argument("--batch", help="Path to raw_leads.json for batch generation")
    args = parser.parse_args()

    if args.batch:
        with open(args.batch) as f:
            leads = json.load(f)
        print(f"Building {len(leads)} websites...")
        paths = []
        for lead in leads:
            path = build_from_lead(lead)
            paths.append(path)
        print(f"\nDone! Built {len(paths)} websites.")
        return

    if not args.name:
        print("ERROR: --name is required (or use --batch)")
        sys.exit(1)

    slug = slugify(args.name)
    output = args.output or f"clients/leads/websites/{slug}/index.html"
    os.makedirs(os.path.dirname(output), exist_ok=True)

    html = build_html(
        name=args.name,
        biz_type=args.type,
        city=args.city,
        state=args.state,
        address=args.address,
        phone=args.phone,
        description=args.desc,
    )

    with open(output, "w") as f:
        f.write(html)
    print(f"Built: {output}")


if __name__ == "__main__":
    main()
