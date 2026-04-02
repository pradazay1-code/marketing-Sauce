#!/usr/bin/env python3
"""Generate simple, professional HTML websites for each of the 15 leads."""
import os

leads = [
    {
        "name": "Torres Family Barber Shop",
        "folder": "torres-family-barbershop",
        "type": "Barbershop",
        "city": "Westborough, MA",
        "address": "72 East Main St, 2nd Floor, Westborough, MA",
        "tagline": "Family Cuts. Clean Fades. Community First.",
        "about": "Torres Family Barber Shop is a family-owned barbershop located in the heart of Westborough, Massachusetts. With over 8 years of experience, owner Jose Torres brings precision cuts and a welcoming atmosphere to every visit. Whether you need a classic cut, a clean fade, or a beard trim — we've got you covered.",
        "services": ["Classic Haircuts", "Skin Fades", "Beard Trims & Shaping", "Kids Cuts", "Hot Towel Shaves", "Line-Ups & Edge-Ups"],
        "color1": "#1a1a2e", "color2": "#e94560", "color3": "#f5f5f5",
        "hours": "Tues - Sat: 9AM - 7PM | Sun - Mon: Closed"
    },
    {
        "name": "Thela Indian Street Food",
        "folder": "thela-street-food",
        "type": "Restaurant",
        "city": "Westborough, MA",
        "address": "72 East Main St, Lower Level, Westborough, MA",
        "tagline": "Authentic Indian Street Food. Bold Flavors.",
        "about": "Thela brings the vibrant flavors of India's street food scene to Westborough, Massachusetts. From savory chaat to crispy samosas and aromatic curries, every dish is crafted with authentic spices and fresh ingredients. Experience the taste of India right here in New England.",
        "services": ["Chaat & Snacks", "Samosas & Pakoras", "Curry Bowls", "Biryani", "Masala Chai & Lassi", "Catering Available"],
        "color1": "#ff6f00", "color2": "#1b5e20", "color3": "#fff8e1",
        "hours": "Mon - Sun: 11AM - 9PM"
    },
    {
        "name": "Rancho Alegre",
        "folder": "rancho-alegre",
        "type": "Mexican Restaurant",
        "city": "Westborough, MA",
        "address": "East Main St, Westborough, MA",
        "tagline": "Authentic Mexican Cuisine. Alegre Spirit.",
        "about": "Rancho Alegre brings the warmth and tradition of Mexican cooking to Westborough. Our kitchen prepares fresh, authentic dishes daily — from hand-rolled tacos and enchiladas to sizzling fajitas and homemade salsas. Come enjoy a taste of Mexico with your family and friends.",
        "services": ["Tacos & Burritos", "Enchiladas & Fajitas", "Fresh Guacamole & Salsas", "Margaritas & Cocktails", "Family Platters", "Weekend Brunch"],
        "color1": "#b71c1c", "color2": "#1b5e20", "color3": "#fff3e0",
        "hours": "Mon - Thu: 11AM - 9PM | Fri - Sat: 11AM - 10PM | Sun: 12PM - 8PM"
    },
    {
        "name": "Ace of Babes Vintage",
        "folder": "ace-of-babes-vintage",
        "type": "Vintage Clothing",
        "city": "Worcester, MA",
        "address": "Portland Street, Downtown Worcester, MA",
        "tagline": "Curated Vintage. One-of-a-Kind Style.",
        "about": "Ace of Babes Vintage is an independently owned vintage clothing shop in the heart of downtown Worcester. We hand-pick every piece in our collection — from retro denim and leather jackets to statement accessories and rare finds. Step in and discover your next favorite piece.",
        "services": ["Vintage Denim & Jackets", "Retro Dresses & Tops", "Accessories & Jewelry", "Rare & One-of-a-Kind Finds", "Seasonal Collections", "Buy & Trade"],
        "color1": "#4a148c", "color2": "#ff6f00", "color3": "#fce4ec",
        "hours": "Wed - Sat: 11AM - 6PM | Sun: 12PM - 5PM | Mon - Tue: Closed"
    },
    {
        "name": "Boom Jewels",
        "folder": "boom-jewels",
        "type": "Jewelry Boutique",
        "city": "Worcester, MA",
        "address": "Main Street, Owl Shop Building, Worcester, MA",
        "tagline": "Bold Jewelry. Timeless Beauty.",
        "about": "Boom Jewels is a boutique jewelry shop nestled inside Worcester's historic Owl Shop Building on Main Street. We offer a curated selection of handcrafted and designer jewelry — from everyday essentials to statement pieces for special occasions. Find something that sparkles.",
        "services": ["Handcrafted Necklaces", "Rings & Bracelets", "Earrings & Studs", "Custom Jewelry Orders", "Gift Sets & Packaging", "Bridal & Special Occasion"],
        "color1": "#1a1a1a", "color2": "#d4af37", "color3": "#fafafa",
        "hours": "Tue - Sat: 10AM - 6PM | Sun: 12PM - 4PM | Mon: Closed"
    },
    {
        "name": "Monalessa's Kitchen",
        "folder": "monalessas-kitchen",
        "type": "Indian Restaurant & Grill",
        "city": "Fall River, MA",
        "address": "756 Brayton Ave, Fall River, MA",
        "tagline": "Flavorful Indian Cuisine. Made with Love.",
        "about": "Monalessa's Kitchen brings authentic Indian flavors to Fall River's South End. From rich curries and tender tandoori to sizzling kebabs and fragrant biryanis, every dish is prepared fresh with traditional spices. Join us for a dining experience that feels like home.",
        "services": ["Tandoori & Kebabs", "Curry Specialties", "Biryani & Rice Dishes", "Naan & Breads", "Vegetarian Options", "Catering & Takeout"],
        "color1": "#880e4f", "color2": "#ff6f00", "color3": "#fff3e0",
        "hours": "Mon - Sun: 11AM - 10PM"
    },
    {
        "name": "The Counting House",
        "folder": "the-counting-house",
        "type": "Cocktail Bar & Restaurant",
        "city": "Fall River, MA",
        "address": "Near Durfee Mills, Downtown Fall River, MA",
        "tagline": "Craft Cocktails. Historic Charm.",
        "about": "The Counting House is an intimate cocktail bar and small plates restaurant set inside a beautifully restored historic building near the Durfee Mills in Fall River. We serve craft cocktails, espresso martinis, mocktails, and Nitro coffee on tap alongside shareable plates with Italian and Portuguese inspirations.",
        "services": ["Craft Cocktails", "Espresso Martinis", "Mocktails & Nitro Coffee", "Italian-Inspired Small Plates", "Portuguese-Inspired Dishes", "Private Events"],
        "color1": "#263238", "color2": "#c9a96e", "color3": "#efebe9",
        "hours": "Wed - Sat: 5PM - 12AM | Sun: 4PM - 10PM | Mon - Tue: Closed"
    },
    {
        "name": "Morgan's Cantina",
        "folder": "morgans-cantina",
        "type": "Mexican Restaurant & Bar",
        "city": "Fall River, MA",
        "address": "1 Ferry St, Fall River Waterfront, MA",
        "tagline": "Waterfront Mexican Dining. Fresh & Authentic.",
        "about": "Morgan's Cantina is a waterfront Mexican restaurant on the Fall River waterfront, offering stunning views of Mount Hope Bay. Owners Michael and Nicole Lund bring handmade authentic Mexican cuisine and fresh craft cocktails to a beautifully renovated waterfront space. From tacos and enchiladas to margaritas and tequila flights — it's all here.",
        "services": ["Handmade Tacos & Enchiladas", "Fresh Craft Margaritas", "Tequila & Mezcal Flights", "Waterfront Dining", "Weekend Brunch", "Private Events"],
        "color1": "#e65100", "color2": "#1b5e20", "color3": "#fff8e1",
        "hours": "Mon - Thu: 11:30AM - 9PM | Fri - Sat: 11:30AM - 10PM | Sun: 11AM - 8PM"
    },
    {
        "name": "Slades Ferry Grille",
        "folder": "slades-ferry-grille",
        "type": "Restaurant",
        "city": "Somerset, MA",
        "address": "Former Magoni's Ferry Landing, Somerset, MA",
        "tagline": "A Somerset Tradition. Reimagined.",
        "about": "Slades Ferry Grille honors Somerset's rich history while bringing a fresh, modern dining experience to the iconic space that once housed Magoni's Ferry Landing for over 70 years. After extensive renovations, we're proud to carry on the tradition of great food and warm hospitality on the waterfront.",
        "services": ["Fresh Seafood", "Steaks & Chops", "Craft Cocktails & Local Beers", "Waterfront Dining", "Sunday Brunch", "Private Events & Functions"],
        "color1": "#0d47a1", "color2": "#b71c1c", "color3": "#e3f2fd",
        "hours": "Tue - Thu: 4PM - 9PM | Fri - Sat: 11:30AM - 10PM | Sun: 10AM - 8PM | Mon: Closed"
    },
    {
        "name": "Surfside Seafood",
        "folder": "surfside-seafood",
        "type": "Seafood Restaurant",
        "city": "Orleans, MA",
        "address": "18 Old Colony Way, Orleans, MA",
        "tagline": "Caught Fresh. Served Right. Cape Cod Style.",
        "about": "Surfside Seafood is a Cape Cod seafood restaurant run by two local fishermen who believe the best seafood comes straight from the boat to your plate. Located in Orleans, we serve the freshest catches prepared Cape Cod style — fried, grilled, or raw. Taste the difference that real, local seafood makes.",
        "services": ["Fresh Lobster Rolls", "Fried Clams & Scallops", "Fish & Chips", "Raw Bar & Oysters", "Clam Chowder", "Seasonal Specials"],
        "color1": "#01579b", "color2": "#e65100", "color3": "#e0f7fa",
        "hours": "Mon - Sun: 11AM - 8PM (Seasonal Hours May Vary)"
    },
    {
        "name": "Liberty Artisanal Bakery",
        "folder": "liberty-artisanal-bakery",
        "type": "Bakery & Coffee",
        "city": "Chatham, MA",
        "address": "1223 Main St, Chatham, MA",
        "tagline": "Artisan Breads. Fresh Pastries. Great Coffee.",
        "about": "Liberty Artisanal Bakery is a craft bakery and coffee bar on Main Street in Chatham, Cape Cod. We bake artisan breads and pastries from scratch daily using time-honored techniques and quality ingredients. Pair your pastry with a hand-pulled espresso or a freshly brewed coffee.",
        "services": ["Artisan Sourdough & Breads", "Croissants & Pastries", "Espresso & Coffee Bar", "Cakes & Special Orders", "Breakfast Sandwiches", "Seasonal Baked Goods"],
        "color1": "#4e342e", "color2": "#ff8f00", "color3": "#efebe9",
        "hours": "Tue - Sun: 7AM - 3PM | Mon: Closed"
    },
    {
        "name": "Cape Life Brand Company",
        "folder": "cape-life-brand",
        "type": "Apparel & Accessories",
        "city": "Harwich Port, MA",
        "address": "537 Main St, Harwich Port, MA",
        "tagline": "Live the Cape Life. Wear the Cape Life.",
        "about": "Cape Life Brand Company is a lifestyle brand and retail shop in Harwich Port celebrating everything that makes Cape Cod special. From stylish apparel and accessories to unique gifts, our designs capture the spirit of Cape life — beaches, sunsets, and salt air.",
        "services": ["Cape-Themed T-Shirts & Hoodies", "Hats & Accessories", "Beach & Lifestyle Gear", "Gifts & Souvenirs", "Stickers & Prints", "Online Orders"],
        "color1": "#006064", "color2": "#f57f17", "color3": "#e0f7fa",
        "hours": "Mon - Sat: 10AM - 6PM | Sun: 11AM - 5PM"
    },
    {
        "name": "Mac Daddies",
        "folder": "mac-daddies",
        "type": "Comfort Food Restaurant",
        "city": "Haverhill, MA",
        "address": "72 South Main St, Haverhill, MA",
        "tagline": "Gourmet Mac & Cheese. Comfort Elevated.",
        "about": "Mac Daddies is Haverhill's go-to spot for gourmet macaroni and cheese with creative, bold twists. From classic cheddar to loaded BBQ pulled pork mac, every bowl is made fresh and packed with flavor. We recently moved to a bigger location on South Main St to serve you better — and we're opening a second spot in Amesbury soon!",
        "services": ["Classic Mac & Cheese", "Loaded & Specialty Bowls", "Mac Flights (Samplers)", "Sides & Appetizers", "Kids Menu", "Catering & Events"],
        "color1": "#f57f17", "color2": "#d32f2f", "color3": "#fff8e1",
        "hours": "Tue - Sat: 11AM - 8PM | Sun: 12PM - 6PM | Mon: Closed"
    },
    {
        "name": "WCP Slice House",
        "folder": "wcp-slice-house",
        "type": "Pizza Restaurant",
        "city": "Lowell, MA",
        "address": "Central Street, Downtown Lowell, MA",
        "tagline": "South Shore Bar Pizza. Downtown Lowell.",
        "about": "WCP Slice House brings South Shore-style bar pizza to downtown Lowell. We serve up crispy, thin-crust bar pizza alongside Sicilian, New Haven style, and gluten-free options. Plus salads, appetizers, and desserts. Whether you're grabbing a quick slice or sitting down for a pie — we've got you.",
        "services": ["South Shore Bar Pizza", "Thin Crust & Sicilian", "New Haven Style Pizza", "Gluten-Free Options", "Salads & Appetizers", "Desserts"],
        "color1": "#b71c1c", "color2": "#1a1a1a", "color3": "#fff3e0",
        "hours": "Mon - Thu: 11AM - 9PM | Fri - Sat: 11AM - 10PM | Sun: 12PM - 8PM"
    },
    {
        "name": "A New Chapter",
        "folder": "a-new-chapter",
        "type": "Independent Bookstore",
        "city": "West Springfield, MA",
        "address": "Downtown West Springfield, MA",
        "tagline": "Every Book Starts a New Chapter.",
        "about": "A New Chapter is an independent bookstore in West Springfield, Massachusetts, founded by book lover Scott Szaban. We carry a thoughtfully curated selection of fiction, non-fiction, children's books, and local authors. Stop in, browse the shelves, and find your next great read in a warm, welcoming space.",
        "services": ["Fiction & Non-Fiction", "Children's & Young Adult", "Local & Regional Authors", "Book Clubs & Events", "Special Orders", "Gift Cards & Bookish Gifts"],
        "color1": "#1b5e20", "color2": "#4e342e", "color3": "#f1f8e9",
        "hours": "Tue - Sat: 10AM - 7PM | Sun: 11AM - 5PM | Mon: Closed"
    },
]

TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{name} | {city}</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:'Segoe UI',system-ui,-apple-system,sans-serif;color:#333;line-height:1.6}}
/* NAV */
nav{{background:{color1};padding:15px 30px;display:flex;justify-content:space-between;align-items:center;position:sticky;top:0;z-index:100;box-shadow:0 2px 10px rgba(0,0,0,0.2)}}
.logo{{font-size:1.5rem;font-weight:800;color:#fff;letter-spacing:1px}}
.logo span{{color:{color2}}}
nav ul{{list-style:none;display:flex;gap:25px}}
nav a{{color:#fff;text-decoration:none;font-weight:500;font-size:0.95rem;transition:color 0.3s}}
nav a:hover{{color:{color2}}}
/* HERO */
.hero{{background:linear-gradient(135deg,{color1} 0%,{color2} 100%);color:#fff;padding:100px 30px;text-align:center}}
.hero h1{{font-size:3rem;margin-bottom:15px;letter-spacing:2px}}
.hero p{{font-size:1.3rem;opacity:0.9;max-width:600px;margin:0 auto 30px}}
.btn{{display:inline-block;padding:14px 35px;background:{color2};color:#fff;text-decoration:none;border-radius:50px;font-weight:700;font-size:1rem;transition:transform 0.3s,box-shadow 0.3s}}
.btn:hover{{transform:translateY(-2px);box-shadow:0 5px 20px rgba(0,0,0,0.3)}}
/* SECTIONS */
section{{padding:70px 30px;max-width:1100px;margin:0 auto}}
.section-title{{text-align:center;font-size:2rem;margin-bottom:10px;color:{color1}}}
.section-sub{{text-align:center;color:#666;margin-bottom:40px;font-size:1.05rem}}
/* ABOUT */
.about-text{{max-width:750px;margin:0 auto;text-align:center;font-size:1.1rem;color:#555}}
/* SERVICES */
.services-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:25px}}
.service-card{{background:{color3};border-radius:12px;padding:30px;text-align:center;border-left:4px solid {color2};transition:transform 0.3s,box-shadow 0.3s}}
.service-card:hover{{transform:translateY(-5px);box-shadow:0 10px 25px rgba(0,0,0,0.1)}}
.service-card h3{{color:{color1};margin-bottom:8px;font-size:1.15rem}}
/* HOURS */
.hours-box{{background:{color1};color:#fff;border-radius:12px;padding:40px;text-align:center;max-width:600px;margin:0 auto}}
.hours-box h2{{margin-bottom:15px;font-size:1.8rem}}
.hours-box p{{font-size:1.15rem;opacity:0.9}}
.hours-box .address{{margin-top:15px;font-size:1rem;opacity:0.75}}
/* CTA */
.cta{{background:linear-gradient(135deg,{color2} 0%,{color1} 100%);color:#fff;padding:60px 30px;text-align:center}}
.cta h2{{font-size:2rem;margin-bottom:15px}}
.cta p{{font-size:1.15rem;opacity:0.9;margin-bottom:25px}}
.btn-light{{background:#fff;color:{color1};padding:14px 35px;border-radius:50px;text-decoration:none;font-weight:700;transition:transform 0.3s}}
.btn-light:hover{{transform:translateY(-2px)}}
/* FOOTER */
footer{{background:{color1};color:#fff;text-align:center;padding:25px;font-size:0.9rem;opacity:0.8}}
/* MOBILE */
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
  <p class="section-sub">{type} in {city}</p>
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
    <p class="address">{address}</p>
  </div>
</section>

<div class="cta" id="contact">
  <h2>Ready to Visit?</h2>
  <p>Stop by {name} today. We'd love to see you!</p>
  <a href="https://maps.google.com/?q={address_encoded}" class="btn-light" target="_blank">Get Directions</a>
</div>

<footer>
  <p>&copy; 2026 {name}. All rights reserved. | Website by Marketing Sauce</p>
</footer>
</body>
</html>"""

base = "/home/user/marketing-Sauce/clients/leads/websites"
os.makedirs(base, exist_ok=True)

for lead in leads:
    folder = os.path.join(base, lead["folder"])
    os.makedirs(folder, exist_ok=True)

    # Split name for logo styling
    parts = lead["name"].split()
    if len(parts) >= 2:
        logo_first = " ".join(parts[:-1]) + " "
        logo_second = parts[-1]
    else:
        logo_first = lead["name"]
        logo_second = ""

    services_html = ""
    for s in lead["services"]:
        services_html += f'    <div class="service-card"><h3>{s}</h3></div>\n'

    html = TEMPLATE.format(
        name=lead["name"],
        city=lead["city"],
        type=lead["type"],
        tagline=lead["tagline"],
        about=lead["about"],
        color1=lead["color1"],
        color2=lead["color2"],
        color3=lead["color3"],
        hours=lead["hours"],
        address=lead["address"],
        address_encoded=lead["address"].replace(" ", "+").replace(",", "%2C"),
        logo_first=logo_first,
        logo_second=logo_second,
        services_html=services_html,
    )

    filepath = os.path.join(folder, "index.html")
    with open(filepath, "w") as f:
        f.write(html)
    print(f"Created: {filepath}")

print(f"\nDone! {len(leads)} websites generated.")
