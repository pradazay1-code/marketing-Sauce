#!/usr/bin/env python3
"""
One Vision Marketing — Premium Website Builder v2.0

Generates modern, professional websites with:
- High-quality stock photos from Unsplash
- Scroll animations & parallax effects
- Business-specific layouts & content
- Mobile-first responsive design
- Google Maps integration
- Testimonials section
- Image gallery
- Contact forms

Usage:
  Single: python build_single_site.py --name "Joe's" --type "Barbershop" --city "Boston" --state "MA"
  Batch:  python build_single_site.py --batch clients/leads/raw_leads.json
  With extras: --address "123 Main St" --phone "(508) 555-1234" --owner "Joe"
"""

import argparse
import json
import os
import re
import hashlib
import html as html_module


# ── Business-specific configurations ──────────────────────────────────────────

BUSINESS_CONFIG = {
    "barbershop": {
        "palette": {"primary": "#1a1a2e", "accent": "#d4a574", "light": "#f5f0eb", "dark": "#0d0d1a", "text": "#2c2c2c"},
        "photos": {
            "hero": "https://images.unsplash.com/photo-1585747860019-8e3e5d43e889?w=1600&h=900&fit=crop",
            "about": "https://images.unsplash.com/photo-1503951914875-452162b0f3f1?w=800&h=600&fit=crop",
            "gallery": [
                "https://images.unsplash.com/photo-1621605815971-fbc98d665033?w=600&h=400&fit=crop",
                "https://images.unsplash.com/photo-1599351431202-1e0f0137899a?w=600&h=400&fit=crop",
                "https://images.unsplash.com/photo-1622286342621-4bd786c2447c?w=600&h=400&fit=crop",
                "https://images.unsplash.com/photo-1493256338651-d82f7acb2b38?w=600&h=400&fit=crop",
            ],
        },
        "icon": "&#9986;",
        "services": [
            ("Classic Haircuts", "Precision cuts tailored to your style and face shape"),
            ("Skin Fades", "Clean, seamless fades from skin to any length"),
            ("Beard Trims & Shaping", "Expert beard grooming and hot towel treatments"),
            ("Kids Cuts", "Patient, fun haircuts for the little ones"),
            ("Hot Towel Shaves", "Traditional straight razor shaves with hot lather"),
            ("Line-Ups & Edge-Ups", "Crisp, clean hairlines every time"),
        ],
        "tagline": "Where Style Meets Tradition",
        "about_extra": "Step into a space where classic barbering meets modern style. Every cut is crafted with precision and care.",
    },
    "restaurant": {
        "palette": {"primary": "#1a1a2e", "accent": "#e94560", "light": "#fff8f0", "dark": "#12121f", "text": "#2c2c2c"},
        "photos": {
            "hero": "https://images.unsplash.com/photo-1517248135467-4c7edcad34c4?w=1600&h=900&fit=crop",
            "about": "https://images.unsplash.com/photo-1414235077428-338989a2e8c0?w=800&h=600&fit=crop",
            "gallery": [
                "https://images.unsplash.com/photo-1504674900247-0877df9cc836?w=600&h=400&fit=crop",
                "https://images.unsplash.com/photo-1540189549336-e6e99c3679fe?w=600&h=400&fit=crop",
                "https://images.unsplash.com/photo-1565299624946-b28f40a0ae38?w=600&h=400&fit=crop",
                "https://images.unsplash.com/photo-1482049016688-2d3e1b311543?w=600&h=400&fit=crop",
            ],
        },
        "icon": "&#127860;",
        "services": [
            ("Dine-In Experience", "Enjoy our dishes in a warm, welcoming atmosphere"),
            ("Takeout & Delivery", "Your favorites, fresh and fast to your door"),
            ("Catering Services", "Let us cater your next event or celebration"),
            ("Private Events", "Host your special occasion in our private dining space"),
            ("Daily Specials", "Fresh seasonal dishes crafted by our chef daily"),
            ("Family Platters", "Generous portions perfect for sharing with loved ones"),
        ],
        "tagline": "A Culinary Experience Like No Other",
        "about_extra": "From our kitchen to your table, every dish tells a story of passion, fresh ingredients, and authentic flavors.",
    },
    "mexican": {
        "palette": {"primary": "#2d1b0e", "accent": "#e8512b", "light": "#fff5ee", "dark": "#1a0f06", "text": "#2c2c2c"},
        "photos": {
            "hero": "https://images.unsplash.com/photo-1613514785940-daed07799d9b?w=1600&h=900&fit=crop",
            "about": "https://images.unsplash.com/photo-1551504734-5ee1c4a1479b?w=800&h=600&fit=crop",
            "gallery": [
                "https://images.unsplash.com/photo-1565299585323-38d6b0865b47?w=600&h=400&fit=crop",
                "https://images.unsplash.com/photo-1599974579688-8dbdd335c77f?w=600&h=400&fit=crop",
                "https://images.unsplash.com/photo-1624300629298-e9de39c13be5?w=600&h=400&fit=crop",
                "https://images.unsplash.com/photo-1582234372722-50d7ccc30ebd?w=600&h=400&fit=crop",
            ],
        },
        "icon": "&#127798;",
        "services": [
            ("Authentic Tacos", "Handmade tortillas with traditional fillings"),
            ("Burritos & Bowls", "Loaded with fresh ingredients and bold flavors"),
            ("Margaritas & Cocktails", "House-made drinks with premium spirits"),
            ("Family Platters", "Share the flavor with generous combo plates"),
            ("Catering", "Bring the fiesta to your next event"),
            ("Daily Specials", "Chef's rotating selections of regional favorites"),
        ],
        "tagline": "Authentic Flavors, Made Fresh Daily",
        "about_extra": "We bring the vibrant flavors of Mexico to your table with recipes passed down through generations.",
    },
    "indian": {
        "palette": {"primary": "#1a0a2e", "accent": "#ff6b35", "light": "#fff8f0", "dark": "#0f0519", "text": "#2c2c2c"},
        "photos": {
            "hero": "https://images.unsplash.com/photo-1585937421612-70a008356fbe?w=1600&h=900&fit=crop",
            "about": "https://images.unsplash.com/photo-1596797038530-2c107229654b?w=800&h=600&fit=crop",
            "gallery": [
                "https://images.unsplash.com/photo-1565557623262-b51c2513a641?w=600&h=400&fit=crop",
                "https://images.unsplash.com/photo-1631452180519-c014fe946bc7?w=600&h=400&fit=crop",
                "https://images.unsplash.com/photo-1588166524941-3bf61a9c41db?w=600&h=400&fit=crop",
                "https://images.unsplash.com/photo-1606491956689-2ea866880049?w=600&h=400&fit=crop",
            ],
        },
        "icon": "&#127836;",
        "services": [
            ("Curries & Biryanis", "Rich, aromatic dishes slow-cooked to perfection"),
            ("Tandoori Specialties", "Clay oven-roasted meats and breads"),
            ("Vegetarian Feast", "Extensive plant-based options bursting with flavor"),
            ("Street Food", "Authentic Indian street snacks and chaats"),
            ("Catering & Events", "Bring the taste of India to your celebration"),
            ("Lunch Specials", "Affordable lunch combos served daily"),
        ],
        "tagline": "Authentic Indian Cuisine, Crafted With Love",
        "about_extra": "Every dish is a celebration of spices, tradition, and the rich culinary heritage of India.",
    },
    "seafood": {
        "palette": {"primary": "#0a3d62", "accent": "#e58e26", "light": "#f0f8ff", "dark": "#061f33", "text": "#2c2c2c"},
        "photos": {
            "hero": "https://images.unsplash.com/photo-1559339352-11d035aa65de?w=1600&h=900&fit=crop",
            "about": "https://images.unsplash.com/photo-1534604973900-c43ab4c2e0ab?w=800&h=600&fit=crop",
            "gallery": [
                "https://images.unsplash.com/photo-1615141982883-c7ad0e69fd62?w=600&h=400&fit=crop",
                "https://images.unsplash.com/photo-1559737558-2f5a35f4523b?w=600&h=400&fit=crop",
                "https://images.unsplash.com/photo-1551218808-94e220e084d2?w=600&h=400&fit=crop",
                "https://images.unsplash.com/photo-1579631542720-3a87824fff86?w=600&h=400&fit=crop",
            ],
        },
        "icon": "&#127843;",
        "services": [
            ("Lobster Rolls", "Fresh-caught lobster in a toasted buttered roll"),
            ("Fried Clams & Scallops", "Golden-fried, crispy, and perfectly seasoned"),
            ("Fish & Chips", "Classic beer-battered with hand-cut fries"),
            ("Raw Bar & Oysters", "Fresh shucked oysters and chilled shellfish"),
            ("New England Chowder", "Creamy, hearty, made from scratch daily"),
            ("Daily Catch", "Today's freshest selection from local waters"),
        ],
        "tagline": "Fresh From the Sea to Your Plate",
        "about_extra": "We source the freshest catch from local fishermen and serve it with pride, just steps from the shore.",
    },
    "bakery": {
        "palette": {"primary": "#3e2723", "accent": "#ff8f00", "light": "#fdf6ee", "dark": "#1a0f0a", "text": "#2c2c2c"},
        "photos": {
            "hero": "https://images.unsplash.com/photo-1509440159596-0249088772ff?w=1600&h=900&fit=crop",
            "about": "https://images.unsplash.com/photo-1556471013-0001958d2f12?w=800&h=600&fit=crop",
            "gallery": [
                "https://images.unsplash.com/photo-1549931319-a545753d62ce?w=600&h=400&fit=crop",
                "https://images.unsplash.com/photo-1486427944544-d2c246c4df8d?w=600&h=400&fit=crop",
                "https://images.unsplash.com/photo-1517433670267-08bbd4be890f?w=600&h=400&fit=crop",
                "https://images.unsplash.com/photo-1558961363-fa8fdf82db35?w=600&h=400&fit=crop",
            ],
        },
        "icon": "&#127838;",
        "services": [
            ("Artisan Breads", "Hand-crafted loaves baked fresh every morning"),
            ("Pastries & Croissants", "Flaky, buttery, and irresistible"),
            ("Espresso & Coffee", "Premium roasts brewed to perfection"),
            ("Custom Cakes", "Beautiful cakes for any celebration"),
            ("Breakfast & Brunch", "Start your day with something special"),
            ("Seasonal Specials", "Rotating menu of seasonal treats"),
        ],
        "tagline": "Handcrafted With Love, Baked Fresh Daily",
        "about_extra": "Every loaf, every pastry, every cup of coffee is made with care, quality ingredients, and a passion for baking.",
    },
    "vintage": {
        "palette": {"primary": "#2c1810", "accent": "#c97b3d", "light": "#faf5ef", "dark": "#1a0e08", "text": "#2c2c2c"},
        "photos": {
            "hero": "https://images.unsplash.com/photo-1441984904996-e0b6ba687e04?w=1600&h=900&fit=crop",
            "about": "https://images.unsplash.com/photo-1558618666-fcd25c85f82e?w=800&h=600&fit=crop",
            "gallery": [
                "https://images.unsplash.com/photo-1567401893414-76b7b1e5a7a5?w=600&h=400&fit=crop",
                "https://images.unsplash.com/photo-1489987707025-afc232f7ea0f?w=600&h=400&fit=crop",
                "https://images.unsplash.com/photo-1551488831-00ddcb6c6bd3?w=600&h=400&fit=crop",
                "https://images.unsplash.com/photo-1525507119028-ed4c629a60a3?w=600&h=400&fit=crop",
            ],
        },
        "icon": "&#128090;",
        "services": [
            ("Curated Collections", "Handpicked vintage pieces from every era"),
            ("Designer Finds", "Rare designer items at unbeatable prices"),
            ("Accessories", "Vintage bags, jewelry, hats, and more"),
            ("Seasonal Drops", "New inventory arriving weekly"),
            ("Buy & Trade", "Sell or trade your vintage pieces with us"),
            ("Personal Styling", "Let us help you find your perfect look"),
        ],
        "tagline": "Timeless Style, One-of-a-Kind Finds",
        "about_extra": "Every piece in our shop has a story. We curate the best vintage finds so you can express your unique style.",
    },
    "jewelry": {
        "palette": {"primary": "#1a1a2e", "accent": "#c9a96e", "light": "#faf8f3", "dark": "#0d0d17", "text": "#2c2c2c"},
        "photos": {
            "hero": "https://images.unsplash.com/photo-1515562141589-67f0d569b6fc?w=1600&h=900&fit=crop",
            "about": "https://images.unsplash.com/photo-1611591437281-460bfbe1220a?w=800&h=600&fit=crop",
            "gallery": [
                "https://images.unsplash.com/photo-1573408301185-9146fe634ad0?w=600&h=400&fit=crop",
                "https://images.unsplash.com/photo-1599643478518-a784e5dc4c8f?w=600&h=400&fit=crop",
                "https://images.unsplash.com/photo-1602751584552-8ba73aad10e1?w=600&h=400&fit=crop",
                "https://images.unsplash.com/photo-1535632066927-ab7c9ab60908?w=600&h=400&fit=crop",
            ],
        },
        "icon": "&#128142;",
        "services": [
            ("Handcrafted Rings", "Unique rings made with care and precision"),
            ("Custom Orders", "Design your dream piece from scratch"),
            ("Necklaces & Pendants", "Statement pieces for every occasion"),
            ("Earrings & Bracelets", "Elegant accessories to complete your look"),
            ("Bridal Collections", "Engagement rings and wedding bands"),
            ("Gift Sets", "Curated gift boxes for that special someone"),
        ],
        "tagline": "Handcrafted Elegance, Designed for You",
        "about_extra": "Each piece is crafted with meticulous attention to detail, blending artistry with timeless design.",
    },
    "bookstore": {
        "palette": {"primary": "#1b3a2d", "accent": "#c97b3d", "light": "#f5f1eb", "dark": "#0d1f16", "text": "#2c2c2c"},
        "photos": {
            "hero": "https://images.unsplash.com/photo-1507842217343-583bb7270b66?w=1600&h=900&fit=crop",
            "about": "https://images.unsplash.com/photo-1521587760476-6c12a4b040da?w=800&h=600&fit=crop",
            "gallery": [
                "https://images.unsplash.com/photo-1526243741027-444d633d7365?w=600&h=400&fit=crop",
                "https://images.unsplash.com/photo-1524578271613-d550eacf6090?w=600&h=400&fit=crop",
                "https://images.unsplash.com/photo-1481627834876-b7833e8f5570?w=600&h=400&fit=crop",
                "https://images.unsplash.com/photo-1495446815901-a7297e633e8d?w=600&h=400&fit=crop",
            ],
        },
        "icon": "&#128218;",
        "services": [
            ("Fiction & Non-Fiction", "Wide selection across every genre"),
            ("Children's Corner", "Inspiring young readers of all ages"),
            ("Local Authors", "Proudly featuring local literary talent"),
            ("Book Clubs", "Join our monthly reading community"),
            ("Special Orders", "Can't find it? We'll get it for you"),
            ("Events & Signings", "Author readings and community events"),
        ],
        "tagline": "Your Next Great Read Awaits",
        "about_extra": "More than a bookstore — we're a community gathering place where stories come alive and readers find their next adventure.",
    },
    "default": {
        "palette": {"primary": "#1e293b", "accent": "#3b82f6", "light": "#f8fafc", "dark": "#0f172a", "text": "#2c2c2c"},
        "photos": {
            "hero": "https://images.unsplash.com/photo-1497366216548-37526070297c?w=1600&h=900&fit=crop",
            "about": "https://images.unsplash.com/photo-1556761175-5973dc0f32e7?w=800&h=600&fit=crop",
            "gallery": [
                "https://images.unsplash.com/photo-1522071820081-009f0129c71c?w=600&h=400&fit=crop",
                "https://images.unsplash.com/photo-1556761175-b413da4baf72?w=600&h=400&fit=crop",
                "https://images.unsplash.com/photo-1497215728101-856f4ea42174?w=600&h=400&fit=crop",
                "https://images.unsplash.com/photo-1573164713988-8665fc963095?w=600&h=400&fit=crop",
            ],
        },
        "icon": "&#9733;",
        "services": [
            ("Our Services", "Professional solutions tailored to your needs"),
            ("Consultations", "Free consultations to discuss your goals"),
            ("Custom Solutions", "Personalized approaches for every client"),
            ("Quality Products", "Premium products you can trust"),
            ("Customer Support", "We're here for you every step of the way"),
            ("Special Requests", "Have something specific in mind? Let's talk"),
        ],
        "tagline": "Quality You Can Trust",
        "about_extra": "We're dedicated to providing exceptional products and services to our community.",
    },
}



# ── Helper functions ──────────────────────────────────────────────────────────

def get_config(business_type):
    """Get business config based on type keywords."""
    t = business_type.lower()
    for key in ["barbershop", "barber"]:
        if key in t: return BUSINESS_CONFIG["barbershop"]
    if "mexican" in t or "cantina" in t or "taco" in t:
        return BUSINESS_CONFIG["mexican"]
    if "indian" in t or "curry" in t:
        return BUSINESS_CONFIG["indian"]
    if "seafood" in t or "fish" in t or "lobster" in t:
        return BUSINESS_CONFIG["seafood"]
    if "bakery" in t or "bread" in t or "coffee" in t or "pastry" in t:
        return BUSINESS_CONFIG["bakery"]
    if "vintage" in t or "thrift" in t or "clothing" in t:
        return BUSINESS_CONFIG["vintage"]
    if "jewel" in t:
        return BUSINESS_CONFIG["jewelry"]
    if "book" in t or "library" in t:
        return BUSINESS_CONFIG["bookstore"]
    if "restaurant" in t or "food" in t or "kitchen" in t or "grill" in t or "diner" in t or "cafe" in t:
        return BUSINESS_CONFIG["restaurant"]
    return BUSINESS_CONFIG["default"]


def slugify(name):
    slug = name.lower().strip()
    slug = re.sub(r"[''']", "", slug)
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    return slug.strip("-")


def esc(text):
    return html_module.escape(str(text))


# ── Testimonials generator ────────────────────────────────────────────────────

def generate_testimonials(name, business_type):
    t = business_type.lower()
    if "barber" in t:
        return [
            ("Best barbershop in town! Always leave looking sharp.", "Marcus T.", "5"),
            ("Jose and the team are amazing. Won't go anywhere else.", "David R.", "5"),
            ("Great atmosphere, even better cuts. Highly recommend!", "Chris M.", "5"),
        ]
    elif "seafood" in t:
        return [
            ("Freshest seafood on the Cape! The lobster rolls are incredible.", "Sarah K.", "5"),
            ("Our family's go-to spot every summer. Never disappoints!", "Mike & Lisa P.", "5"),
            ("Amazing chowder and the friendliest staff around.", "Jennifer L.", "5"),
        ]
    elif "bakery" in t or "bread" in t or "coffee" in t:
        return [
            ("The croissants are perfection. Best bakery I've ever been to!", "Emma W.", "5"),
            ("My morning coffee ritual starts here. Can't recommend enough.", "Robert H.", "5"),
            ("Their sourdough bread is out of this world. A true artisan.", "Patricia D.", "5"),
        ]
    elif "book" in t:
        return [
            ("A real neighborhood gem. Love the curated selections!", "Amanda K.", "5"),
            ("Best independent bookstore in Western Mass!", "Thomas R.", "5"),
            ("The staff recommendations are always spot-on. Love this place.", "Rachel S.", "5"),
        ]
    elif "vintage" in t or "clothing" in t:
        return [
            ("Found the most amazing vintage jacket here! Always great finds.", "Olivia J.", "5"),
            ("Unique pieces you won't find anywhere else. Love this shop!", "Mia C.", "5"),
            ("The curation is incredible. Every visit I find something special.", "Taylor N.", "5"),
        ]
    elif "jewel" in t:
        return [
            ("Got my engagement ring here. Absolutely beautiful craftsmanship!", "Daniel F.", "5"),
            ("Unique, handmade pieces that get compliments everywhere.", "Sophie L.", "5"),
            ("The custom design process was so easy and the result was stunning.", "Alex M.", "5"),
        ]
    else:
        return [
            (f"Love {name}! Great service and quality every time.", "Jessica M.", "5"),
            ("Absolutely the best experience. Will definitely be back!", "Ryan T.", "5"),
            ("Highly recommend to anyone looking for quality and value.", "Maria G.", "5"),
        ]



# ── HTML Template ─────────────────────────────────────────────────────────────

def build_html(name, business_type, city, state, address="", phone="", owner="", notes=""):
    config = get_config(business_type)
    p = config["palette"]
    photos = config["photos"]
    services = config["services"]
    testimonials = generate_testimonials(name, business_type)

    # Escape all user inputs
    name_e = esc(name)
    city_e = esc(city)
    state_e = esc(state)
    btype_e = esc(business_type)
    address_e = esc(address) if address else f"{city_e}, {state_e}"
    phone_e = esc(phone) if phone else ""
    owner_e = esc(owner) if owner else ""

    # Logo split
    parts = name.split()
    if len(parts) >= 2:
        logo1 = esc(" ".join(parts[:-1])) + " "
        logo2 = esc(parts[-1])
    else:
        logo1 = name_e
        logo2 = ""

    tagline = config["tagline"]
    about_extra = config["about_extra"]
    icon = config["icon"]

    # Services HTML
    svc_icons = ["&#9733;", "&#9733;", "&#9733;", "&#9733;", "&#9733;", "&#9733;"]
    services_html = ""
    for i, (svc_name, svc_desc) in enumerate(services):
        services_html += f'''    <div class="svc-card" style="animation-delay: {i*0.1}s">
      <div class="svc-icon">{svc_icons[i % len(svc_icons)]}</div>
      <h3>{esc(svc_name)}</h3>
      <p>{esc(svc_desc)}</p>
    </div>
'''

    # Gallery HTML
    gallery_html = ""
    for i, img_url in enumerate(photos["gallery"]):
        gallery_html += f'    <div class="gallery-item"><img src="{img_url}" alt="{name_e} photo {i+1}" loading="lazy"></div>\n'

    # Testimonials HTML
    testimonials_html = ""
    for text, author, stars in testimonials:
        star_html = "&#9733;" * int(stars)
        testimonials_html += f'''    <div class="testimonial">
      <div class="stars">{star_html}</div>
      <p>"{esc(text)}"</p>
      <span class="author">— {esc(author)}</span>
    </div>
'''

    # Contact info
    contact_info = ""
    if address:
        contact_info += f'<div class="contact-item"><span class="ci-icon">&#128205;</span><span>{address_e}</span></div>'
    if phone:
        contact_info += f'<div class="contact-item"><span class="ci-icon">&#128222;</span><a href="tel:{phone_e}">{phone_e}</a></div>'
    contact_info += f'<div class="contact-item"><span class="ci-icon">&#128205;</span><span>{city_e}, {state_e}</span></div>'

    maps_query = f"{name}+{address}+{city}+{state}".replace(" ", "+") if address else f"{name}+{city}+{state}".replace(" ", "+")

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{name_e} | {btype_e} in {city_e}, {state_e}</title>
<meta name="description" content="{name_e} — {btype_e} in {city_e}, {state_e}. {tagline}. Visit us today!">
<meta property="og:title" content="{name_e} | {city_e}, {state_e}">
<meta property="og:description" content="{tagline}">
<meta property="og:image" content="{photos["hero"]}">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&family=Playfair+Display:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
:root{{--primary:{p["primary"]};--accent:{p["accent"]};--light:{p["light"]};--dark:{p["dark"]};--text:{p["text"]}}}
html{{scroll-behavior:smooth}}
body{{font-family:'Inter',system-ui,sans-serif;color:var(--text);line-height:1.6;overflow-x:hidden}}

/* ── Nav ── */
.nav{{position:fixed;top:0;width:100%;z-index:1000;padding:18px 40px;display:flex;justify-content:space-between;align-items:center;transition:all 0.4s ease}}
.nav.scrolled{{background:var(--primary);box-shadow:0 4px 30px rgba(0,0,0,0.15);padding:12px 40px}}
.logo{{font-family:'Playfair Display',serif;font-size:1.6rem;font-weight:700;color:#fff;letter-spacing:1px;text-decoration:none}}
.logo span{{color:var(--accent)}}
.nav-links{{list-style:none;display:flex;gap:30px}}
.nav-links a{{color:rgba(255,255,255,0.85);text-decoration:none;font-weight:500;font-size:0.9rem;letter-spacing:0.5px;text-transform:uppercase;transition:color 0.3s}}
.nav-links a:hover{{color:var(--accent)}}
.menu-toggle{{display:none;flex-direction:column;gap:5px;cursor:pointer;z-index:1001}}
.menu-toggle span{{width:25px;height:2px;background:#fff;transition:0.3s}}

/* ── Hero ── */
.hero{{position:relative;height:100vh;min-height:600px;display:flex;align-items:center;justify-content:center;text-align:center;color:#fff;overflow:hidden}}
.hero-bg{{position:absolute;inset:0;background:url('{photos["hero"]}') center/cover no-repeat;transform:scale(1.05)}}
.hero-overlay{{position:absolute;inset:0;background:linear-gradient(180deg,rgba(0,0,0,0.4) 0%,rgba(0,0,0,0.6) 50%,var(--primary) 100%)}}
.hero-content{{position:relative;z-index:2;max-width:800px;padding:0 30px}}
.hero-badge{{display:inline-block;padding:8px 24px;border:1px solid rgba(255,255,255,0.3);border-radius:50px;font-size:0.8rem;letter-spacing:3px;text-transform:uppercase;margin-bottom:25px;backdrop-filter:blur(5px)}}
.hero h1{{font-family:'Playfair Display',serif;font-size:4rem;font-weight:700;line-height:1.1;margin-bottom:20px;text-shadow:0 2px 40px rgba(0,0,0,0.3)}}
.hero p{{font-size:1.25rem;opacity:0.9;margin-bottom:35px;max-width:550px;margin-left:auto;margin-right:auto}}
.btn{{display:inline-block;padding:16px 40px;border-radius:50px;font-weight:600;font-size:0.95rem;text-decoration:none;letter-spacing:1px;text-transform:uppercase;transition:all 0.4s ease;cursor:pointer}}
.btn-primary{{background:var(--accent);color:#fff;box-shadow:0 4px 20px rgba(0,0,0,0.2)}}
.btn-primary:hover{{transform:translateY(-3px);box-shadow:0 8px 30px rgba(0,0,0,0.3)}}
.btn-outline{{border:2px solid #fff;color:#fff;margin-left:15px}}
.btn-outline:hover{{background:#fff;color:var(--primary)}}

/* ── Sections ── */
section{{padding:100px 40px}}
.container{{max-width:1200px;margin:0 auto}}
.section-label{{color:var(--accent);font-weight:600;font-size:0.85rem;letter-spacing:3px;text-transform:uppercase;margin-bottom:12px}}
.section-title{{font-family:'Playfair Display',serif;font-size:2.8rem;color:var(--primary);margin-bottom:15px;line-height:1.2}}
.section-sub{{color:#666;font-size:1.1rem;max-width:600px}}

/* ── About ── */
.about-grid{{display:grid;grid-template-columns:1fr 1fr;gap:60px;align-items:center;margin-top:50px}}
.about-img{{border-radius:16px;overflow:hidden;box-shadow:0 20px 60px rgba(0,0,0,0.12);position:relative}}
.about-img img{{width:100%;height:400px;object-fit:cover;display:block}}
.about-img-badge{{position:absolute;bottom:-20px;right:30px;background:var(--accent);color:#fff;padding:20px 30px;border-radius:12px;font-family:'Playfair Display',serif;font-size:1.4rem;font-weight:700;box-shadow:0 10px 30px rgba(0,0,0,0.15)}}
.about-text{{font-size:1.05rem;color:#555;line-height:1.8}}
.about-text p{{margin-bottom:20px}}
.about-stats{{display:flex;gap:40px;margin-top:30px}}
.stat{{text-align:center}}
.stat-num{{font-family:'Playfair Display',serif;font-size:2.2rem;font-weight:700;color:var(--accent)}}
.stat-label{{font-size:0.8rem;text-transform:uppercase;letter-spacing:1px;color:#888;margin-top:5px}}

/* ── Services ── */
.services{{background:var(--light)}}
.svc-grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:30px;margin-top:50px}}
.svc-card{{background:#fff;border-radius:16px;padding:35px 30px;text-align:center;transition:all 0.4s ease;border:1px solid rgba(0,0,0,0.05);position:relative;overflow:hidden}}
.svc-card::before{{content:'';position:absolute;top:0;left:0;right:0;height:3px;background:var(--accent);transform:scaleX(0);transition:transform 0.4s ease}}
.svc-card:hover{{transform:translateY(-8px);box-shadow:0 20px 40px rgba(0,0,0,0.08)}}
.svc-card:hover::before{{transform:scaleX(1)}}
.svc-icon{{font-size:2rem;margin-bottom:15px;color:var(--accent)}}
.svc-card h3{{font-size:1.1rem;color:var(--primary);margin-bottom:10px;font-weight:600}}
.svc-card p{{font-size:0.9rem;color:#666;line-height:1.6}}

/* ── Gallery ── */
.gallery-grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:15px;margin-top:50px}}
.gallery-item{{border-radius:12px;overflow:hidden;aspect-ratio:3/2;cursor:pointer;position:relative}}
.gallery-item img{{width:100%;height:100%;object-fit:cover;transition:transform 0.5s ease}}
.gallery-item:hover img{{transform:scale(1.08)}}
.gallery-item::after{{content:'';position:absolute;inset:0;background:linear-gradient(to top,rgba(0,0,0,0.3),transparent);opacity:0;transition:opacity 0.3s}}
.gallery-item:hover::after{{opacity:1}}

/* ── Testimonials ── */
.testimonials{{background:var(--primary);color:#fff;text-align:center}}
.testimonials .section-label{{color:var(--accent)}}
.testimonials .section-title{{color:#fff}}
.test-grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:30px;margin-top:50px}}
.testimonial{{background:rgba(255,255,255,0.08);backdrop-filter:blur(10px);border-radius:16px;padding:35px;border:1px solid rgba(255,255,255,0.1);transition:transform 0.3s}}
.testimonial:hover{{transform:translateY(-5px)}}
.stars{{color:var(--accent);font-size:1.2rem;margin-bottom:15px;letter-spacing:3px}}
.testimonial p{{font-size:1rem;line-height:1.7;opacity:0.9;font-style:italic;margin-bottom:15px}}
.author{{font-weight:600;font-size:0.9rem;opacity:0.7}}

/* ── Contact ── */
.contact-section{{background:var(--light)}}
.contact-grid{{display:grid;grid-template-columns:1fr 1fr;gap:50px;margin-top:50px;align-items:start}}
.contact-info{{display:flex;flex-direction:column;gap:20px}}
.contact-item{{display:flex;align-items:center;gap:15px;padding:18px 24px;background:#fff;border-radius:12px;box-shadow:0 2px 10px rgba(0,0,0,0.05)}}
.contact-item a{{color:var(--accent);text-decoration:none;font-weight:500}}
.ci-icon{{font-size:1.3rem}}
.map-container{{border-radius:16px;overflow:hidden;box-shadow:0 10px 30px rgba(0,0,0,0.1);height:350px}}
.map-container iframe{{width:100%;height:100%;border:0}}

/* ── CTA Banner ── */
.cta-banner{{background:linear-gradient(135deg,var(--accent),var(--primary));color:#fff;text-align:center;padding:80px 40px}}
.cta-banner h2{{font-family:'Playfair Display',serif;font-size:2.5rem;margin-bottom:15px}}
.cta-banner p{{font-size:1.15rem;opacity:0.9;margin-bottom:30px;max-width:500px;margin-left:auto;margin-right:auto}}

/* ── Footer ── */
footer{{background:var(--dark);color:rgba(255,255,255,0.6);padding:40px;text-align:center}}
footer p{{font-size:0.85rem}}
footer a{{color:var(--accent);text-decoration:none}}
footer .footer-brand{{font-family:'Playfair Display',serif;font-size:1.3rem;color:#fff;margin-bottom:10px}}

/* ── Animations ── */
.reveal{{opacity:0;transform:translateY(30px);transition:all 0.8s ease}}
.reveal.visible{{opacity:1;transform:translateY(0)}}

/* ── Mobile ── */
@media(max-width:968px){{
  .hero h1{{font-size:2.8rem}}
  .about-grid{{grid-template-columns:1fr;gap:40px}}
  .svc-grid{{grid-template-columns:repeat(2,1fr)}}
  .gallery-grid{{grid-template-columns:repeat(2,1fr)}}
  .test-grid{{grid-template-columns:1fr}}
  .contact-grid{{grid-template-columns:1fr}}
  section{{padding:70px 25px}}
}}
@media(max-width:768px){{
  .nav-links{{position:fixed;top:0;right:-100%;width:70%;height:100vh;background:var(--primary);flex-direction:column;justify-content:center;align-items:center;gap:35px;transition:right 0.4s ease;box-shadow:-5px 0 30px rgba(0,0,0,0.3)}}
  .nav-links.active{{right:0}}
  .menu-toggle{{display:flex}}
  .hero h1{{font-size:2.2rem}}
  .hero p{{font-size:1rem}}
  .svc-grid{{grid-template-columns:1fr}}
  .section-title{{font-size:2rem}}
  .about-img-badge{{display:none}}
  .btn-outline{{display:none}}
}}
</style>
</head>
<body>

<!-- Navigation -->
<nav class="nav">
  <a href="#" class="logo">{logo1}<span>{logo2}</span></a>
  <ul class="nav-links">
    <li><a href="#about">About</a></li>
    <li><a href="#services">Services</a></li>
    <li><a href="#gallery">Gallery</a></li>
    <li><a href="#reviews">Reviews</a></li>
    <li><a href="#contact">Contact</a></li>
  </ul>
  <div class="menu-toggle" onclick="document.querySelector('.nav-links').classList.toggle('active')">
    <span></span><span></span><span></span>
  </div>
</nav>

<!-- Hero -->
<section class="hero">
  <div class="hero-bg"></div>
  <div class="hero-overlay"></div>
  <div class="hero-content">
    <div class="hero-badge">{icon} {btype_e} &bull; {city_e}, {state_e}</div>
    <h1>{name_e}</h1>
    <p>{tagline}</p>
    <a href="#contact" class="btn btn-primary">Visit Us Today</a>
    <a href="#about" class="btn btn-outline">Learn More</a>
  </div>
</section>

<!-- About -->
<section id="about">
  <div class="container">
    <div class="about-grid">
      <div class="about-img reveal">
        <img src="{photos["about"]}" alt="About {name_e}">
        <div class="about-img-badge">Est. 2024</div>
      </div>
      <div class="reveal">
        <span class="section-label">Our Story</span>
        <h2 class="section-title">Welcome to {name_e}</h2>
        <div class="about-text">
          <p>{name_e} is a proud {btype_e.lower()} serving the {city_e}, {state_e} community. {about_extra}</p>
          <p>We believe in quality, community, and creating an experience that keeps you coming back. Whether you're a first-time visitor or a longtime regular, you're always welcome here.</p>
        </div>
        <div class="about-stats">
          <div class="stat"><div class="stat-num">100%</div><div class="stat-label">Locally Owned</div></div>
          <div class="stat"><div class="stat-num">5&#9733;</div><div class="stat-label">Top Rated</div></div>
          <div class="stat"><div class="stat-num">{city_e}</div><div class="stat-label">Community</div></div>
        </div>
      </div>
    </div>
  </div>
</section>

<!-- Services -->
<section id="services" class="services">
  <div class="container">
    <div style="text-align:center" class="reveal">
      <span class="section-label">What We Offer</span>
      <h2 class="section-title">Our Services</h2>
      <p class="section-sub" style="margin:0 auto 10px">Quality products and services you can count on</p>
    </div>
    <div class="svc-grid">
{services_html}
    </div>
  </div>
</section>

<!-- Gallery -->
<section id="gallery">
  <div class="container">
    <div style="text-align:center" class="reveal">
      <span class="section-label">See For Yourself</span>
      <h2 class="section-title">Gallery</h2>
    </div>
    <div class="gallery-grid">
{gallery_html}
    </div>
  </div>
</section>

<!-- Testimonials -->
<section id="reviews" class="testimonials">
  <div class="container">
    <div class="reveal">
      <span class="section-label">What People Say</span>
      <h2 class="section-title">Customer Reviews</h2>
    </div>
    <div class="test-grid">
{testimonials_html}
    </div>
  </div>
</section>

<!-- Contact -->
<section id="contact" class="contact-section">
  <div class="container">
    <div style="text-align:center" class="reveal">
      <span class="section-label">Get In Touch</span>
      <h2 class="section-title">Find Us</h2>
    </div>
    <div class="contact-grid">
      <div class="contact-info reveal">
        {contact_info}
        <a href="https://maps.google.com/?q={maps_query}" class="btn btn-primary" target="_blank" style="text-align:center;margin-top:10px">Get Directions</a>
      </div>
      <div class="map-container reveal">
        <iframe src="https://www.google.com/maps?q={maps_query}&output=embed" allowfullscreen loading="lazy"></iframe>
      </div>
    </div>
  </div>
</section>

<!-- CTA -->
<div class="cta-banner">
  <h2>Ready to Experience {name_e}?</h2>
  <p>Stop by today — we'd love to welcome you!</p>
  <a href="https://maps.google.com/?q={maps_query}" class="btn btn-primary" target="_blank">Get Directions</a>
</div>

<!-- Footer -->
<footer>
  <div class="footer-brand">{name_e}</div>
  <p>{address_e} &bull; {city_e}, {state_e}</p>
  <p style="margin-top:15px">&copy; 2026 {name_e}. All rights reserved. | Website by <a href="https://pradazay1-code.github.io/marketing-Sauce/" target="_blank">One Vision Marketing</a></p>
</footer>

<script>
// Scroll nav effect
window.addEventListener('scroll',()=>{{document.querySelector('.nav').classList.toggle('scrolled',window.scrollY>50)}});

// Reveal on scroll
const observer=new IntersectionObserver((entries)=>{{entries.forEach(e=>{{if(e.isIntersecting){{e.target.classList.add('visible');observer.unobserve(e.target);}}}});}},{{threshold:0.15}});
document.querySelectorAll('.reveal').forEach(el=>observer.observe(el));

// Close mobile menu on link click
document.querySelectorAll('.nav-links a').forEach(a=>a.addEventListener('click',()=>document.querySelector('.nav-links').classList.remove('active')));
</script>
</body>
</html>'''



# ── Build & Save ──────────────────────────────────────────────────────────────

def build_site(name, business_type, city, state, output_dir="clients/leads/websites",
               address="", phone="", owner="", notes=""):
    """Build a single website and save to disk."""
    slug = slugify(name)
    html = build_html(name, business_type, city, state, address, phone, owner, notes)

    folder = os.path.join(output_dir, slug)
    os.makedirs(folder, exist_ok=True)
    filepath = os.path.join(folder, "index.html")
    with open(filepath, "w") as f:
        f.write(html)
    print(f"  Built: {filepath}")
    return filepath


def main():
    parser = argparse.ArgumentParser(description="One Vision Marketing — Premium Website Builder v2.0")
    parser.add_argument("--name", help="Business name")
    parser.add_argument("--type", dest="business_type", default="Business", help="Business type")
    parser.add_argument("--city", default="Boston", help="City")
    parser.add_argument("--state", default="MA", help="State")
    parser.add_argument("--address", default="", help="Street address")
    parser.add_argument("--phone", default="", help="Phone number")
    parser.add_argument("--owner", default="", help="Owner name")
    parser.add_argument("--batch", help="Path to raw_leads.json for batch build")
    parser.add_argument("--output", default="clients/leads/websites", help="Output directory")
    args = parser.parse_args()

    if args.batch:
        with open(args.batch, "r") as f:
            leads = json.load(f)
        print(f"\n  One Vision Marketing — Website Builder v2.0")
        print(f"  Building {len(leads)} premium websites...\n")
        for i, lead in enumerate(leads, 1):
            name = lead.get("business_name", lead.get("name", "Business"))
            print(f"  [{i}/{len(leads)}] {name}")
            build_site(
                name=name,
                business_type=lead.get("type", lead.get("business_type", "Business")),
                city=lead.get("city", "Boston"),
                state=lead.get("state", "MA"),
                output_dir=args.output,
                address=lead.get("address", ""),
                phone=lead.get("phone", ""),
                owner=lead.get("owner_name", ""),
                notes=lead.get("notes", ""),
            )
        print(f"\n  Done! {len(leads)} premium websites built.\n")
    elif args.name:
        build_site(args.name, args.business_type, args.city, args.state, args.output,
                   args.address, args.phone, args.owner)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
