#!/usr/bin/env python3
"""Build professional HTML websites for leads with real photos and modern design."""
import argparse, json, os, re, hashlib, urllib.parse

PHOTOS = {
    "real_estate": ["https://images.unsplash.com/photo-1560518883-ce09059eeffa?w=1200&h=600&fit=crop",
                    "https://images.unsplash.com/photo-1582407947304-fd86f028f716?w=800&h=500&fit=crop",
                    "https://images.unsplash.com/photo-1512917774080-9991f1c4c750?w=800&h=500&fit=crop"],
    "barbershop": ["https://images.unsplash.com/photo-1585747860019-8e78f4937c39?w=1200&h=600&fit=crop",
                   "https://images.unsplash.com/photo-1503951914875-452162b0f3f1?w=800&h=500&fit=crop",
                   "https://images.unsplash.com/photo-1621605815971-fbc98d665033?w=800&h=500&fit=crop"],
    "restaurant": ["https://images.unsplash.com/photo-1517248135467-4c7edcad34c4?w=1200&h=600&fit=crop",
                   "https://images.unsplash.com/photo-1414235077428-338989a2e8c0?w=800&h=500&fit=crop",
                   "https://images.unsplash.com/photo-1559339352-11d035aa65de?w=800&h=500&fit=crop"],
    "bakery":     ["https://images.unsplash.com/photo-1509440159596-0249088772ff?w=1200&h=600&fit=crop",
                   "https://images.unsplash.com/photo-1558961363-fa8fdf82db35?w=800&h=500&fit=crop",
                   "https://images.unsplash.com/photo-1486427944544-d2c246c4df8d?w=800&h=500&fit=crop"],
    "seafood":    ["https://images.unsplash.com/photo-1615141982883-c7ad0e69fd62?w=1200&h=600&fit=crop",
                   "https://images.unsplash.com/photo-1559737558-2f5a35f4523b?w=800&h=500&fit=crop",
                   "https://images.unsplash.com/photo-1534604973900-c43ab4c2e0ab?w=800&h=500&fit=crop"],
    "vintage":    ["https://images.unsplash.com/photo-1558618666-fcd25c85f82e?w=1200&h=600&fit=crop",
                   "https://images.unsplash.com/photo-1441986300917-64674bd600d8?w=800&h=500&fit=crop",
                   "https://images.unsplash.com/photo-1567401893414-76b7b1e5a7a5?w=800&h=500&fit=crop"],
    "jewelry":    ["https://images.unsplash.com/photo-1515562141589-67f0d569b6c7?w=1200&h=600&fit=crop",
                   "https://images.unsplash.com/photo-1573408301185-9146fe634ad0?w=800&h=500&fit=crop",
                   "https://images.unsplash.com/photo-1611591437281-460bfbe1220a?w=800&h=500&fit=crop"],
    "bookstore":  ["https://images.unsplash.com/photo-1507842217343-583bb7270b66?w=1200&h=600&fit=crop",
                   "https://images.unsplash.com/photo-1521587760476-6c12a4b040da?w=800&h=500&fit=crop",
                   "https://images.unsplash.com/photo-1524578271613-d550eacf6090?w=800&h=500&fit=crop"],
    "mexican":    ["https://images.unsplash.com/photo-1613514785940-daed07799d9b?w=1200&h=600&fit=crop",
                   "https://images.unsplash.com/photo-1565299585323-38d6b0865b47?w=800&h=500&fit=crop",
                   "https://images.unsplash.com/photo-1551504734-5ee1c4a1479b?w=800&h=500&fit=crop"],
    "indian":     ["https://images.unsplash.com/photo-1585937421612-70a008356fbe?w=1200&h=600&fit=crop",
                   "https://images.unsplash.com/photo-1596797038530-2c107229654b?w=800&h=500&fit=crop",
                   "https://images.unsplash.com/photo-1567337710282-00832b415979?w=800&h=500&fit=crop"],
    "default":    ["https://images.unsplash.com/photo-1497366216548-37526070297c?w=1200&h=600&fit=crop",
                   "https://images.unsplash.com/photo-1497366811353-6870744d04b2?w=800&h=500&fit=crop",
                   "https://images.unsplash.com/photo-1497215728101-856f4ea42174?w=800&h=500&fit=crop"],
}

PALETTES = {
    "real_estate":{"p":"#0f172a","s":"#3b82f6","bg":"#f8fafc","txt":"#0f172a"},
    "restaurant":{"p":"#1a1a2e","s":"#e94560","bg":"#fff8f0","txt":"#2d2d2d"},
    "barbershop":{"p":"#1c1c1c","s":"#c9a96e","bg":"#faf9f6","txt":"#1c1c1c"},
    "bakery":{"p":"#3e2723","s":"#e65100","bg":"#fff8e1","txt":"#3e2723"},
    "seafood":{"p":"#01579b","s":"#ff6d00","bg":"#e8f5e9","txt":"#1a237e"},
    "vintage":{"p":"#4a148c","s":"#ff6f00","bg":"#fce4ec","txt":"#311b92"},
    "jewelry":{"p":"#212121","s":"#c9a96e","bg":"#fafafa","txt":"#212121"},
    "bookstore":{"p":"#1b5e20","s":"#795548","bg":"#f1f8e9","txt":"#1b5e20"},
    "mexican":{"p":"#b71c1c","s":"#f57f17","bg":"#fff3e0","txt":"#3e2723"},
    "indian":{"p":"#e65100","s":"#1a237e","bg":"#fff3e0","txt":"#212121"},
    "default":{"p":"#2c3e50","s":"#e74c3c","bg":"#f8f9fa","txt":"#2c3e50"},
}

SERVICES = {
    "real_estate":["Buyer Representation","Seller Representation","Market Analysis","Property Valuations","First-Time Buyers","Investment Properties"],
    "barber":["Classic Cuts","Skin Fades","Beard Grooming","Hot Towel Shaves","Kids Cuts","Line-Ups"],
    "restaurant":["Dine-In","Takeout & Delivery","Catering","Private Events","Daily Specials","Family Platters"],
    "bakery":["Artisan Breads","Pastries & Croissants","Espresso Bar","Wedding Cakes","Breakfast","Seasonal Specials"],
    "seafood":["Lobster Rolls","Fried Clams","Fish & Chips","Raw Bar","Chowder","Daily Catch"],
    "vintage":["Curated Vintage","Designer Consignment","Accessories","Seasonal Drops","Buy & Trade","Gift Cards"],
    "jewelry":["Custom Designs","Engagement Rings","Handcrafted Pieces","Repairs","Bridal","Gift Sets"],
    "book":["Fiction & Non-Fiction","Children's Books","Local Authors","Book Clubs","Special Orders","Gifts & Cards"],
    "mexican":["Tacos & Burritos","Fresh Guacamole","Margaritas","Street Corn","Family Platters","Catering"],
    "indian":["Curry & Tandoori","Biryani","Naan & Breads","Thali Plates","Vegetarian Specials","Catering"],
}

TAGLINES = {
    "real_estate":"Your trusted guide to finding home",
    "barber":"Where tradition meets style","restaurant":"Flavors that bring people together",
    "bakery":"Baked fresh daily with love","seafood":"Fresh from the ocean to your plate",
    "vintage":"Timeless style, curated for you","jewelry":"Handcrafted elegance",
    "book":"Stories waiting to be discovered","mexican":"Authentic flavors, made with soul",
    "indian":"Spices that tell a story",
}

def match_key(btype):
    t = btype.lower()
    if any(w in t for w in ["real estate", "realtor", "realty", "real_estate"]):
        return "real_estate"
    for k in PHOTOS:
        if k in t:
            return k
    return "default"

def slugify(name):
    s = re.sub(r"[''']","",name.lower().strip())
    return re.sub(r"[^a-z0-9]+","-",s).strip("-")

def get_services(btype):
    key = match_key(btype)
    if key in SERVICES:
        return SERVICES[key]
    t = btype.lower()
    for k,v in SERVICES.items():
        if k in t: return v
    return ["Our Services","Consultations","Custom Solutions","Quality Products","Support","Special Requests"]

def get_tagline(btype):
    key = match_key(btype)
    if key in TAGLINES:
        return TAGLINES[key]
    t = btype.lower()
    for k,v in TAGLINES.items():
        if k in t: return v
    return "Quality you can count on"

def build_site(name, btype, city, state, address="", phone="", owner="", notes="", output_dir="clients/leads/websites"):
    key = match_key(btype)
    pal = PALETTES.get(key, PALETTES["default"])
    photos = PHOTOS.get(key, PHOTOS["default"])
    services = get_services(btype)
    tagline = get_tagline(btype)
    slug = slugify(name)
    nm = urllib.parse.quote_plus(f"{name} {city} {state}")
    addr_display = f"{address}, {city}, {state}" if address else f"{city}, {state}"
    phone_html = f'<a href="tel:{phone}" style="color:#fff;text-decoration:none">{phone}</a>' if phone else "Call for info"

    svc_html = ""
    icons = ["&#9733;","&#9830;","&#9827;","&#10047;","&#9752;","&#10024;"]
    for i,s in enumerate(services):
        svc_html += f'<div class="svc"><span class="svc-icon">{icons[i%len(icons)]}</span><h3>{s}</h3><p>Quality service you can trust.</p></div>\n'

    gallery_html = "".join(f'<div class="gal-item"><img src="{p}" alt="{name}" loading="lazy"></div>' for p in photos[1:])

    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>{name} | {btype} in {city}, {state}</title>
<meta name="description" content="{name} is a {btype.lower()} in {city}, {state}. {tagline}.">
<meta property="og:title" content="{name} | {city}, {state}">
<meta property="og:description" content="{tagline}. Visit us in {city}, {state}.">
<meta property="og:image" content="{photos[0]}">
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
:root{{--p:{pal["p"]};--s:{pal["s"]};--bg:{pal["bg"]};--txt:{pal["txt"]}}}
body{{font-family:'Segoe UI',system-ui,sans-serif;color:var(--txt);line-height:1.7;overflow-x:hidden}}
img{{max-width:100%;height:auto;display:block}}

/* NAV */
nav{{background:var(--p);padding:0 40px;display:flex;justify-content:space-between;align-items:center;position:sticky;top:0;z-index:999;height:70px;box-shadow:0 2px 20px rgba(0,0,0,.3)}}
.logo{{font-size:1.6rem;font-weight:900;color:#fff;letter-spacing:1px}}.logo span{{color:var(--s)}}
nav ul{{list-style:none;display:flex;gap:30px}}
nav a{{color:rgba(255,255,255,.85);text-decoration:none;font-weight:500;font-size:.95rem;transition:.3s;position:relative}}
nav a:hover{{color:var(--s)}}
nav a::after{{content:"";position:absolute;bottom:-5px;left:0;width:0;height:2px;background:var(--s);transition:.3s}}
nav a:hover::after{{width:100%}}
.hamburger{{display:none;flex-direction:column;gap:5px;cursor:pointer;background:none;border:none;padding:5px}}
.hamburger span{{width:25px;height:2px;background:#fff;transition:.3s}}

/* HERO */
.hero{{position:relative;height:85vh;min-height:500px;display:flex;align-items:center;justify-content:center;text-align:center;color:#fff;overflow:hidden}}
.hero-bg{{position:absolute;inset:0;background:url('{photos[0]}') center/cover no-repeat}}
.hero-overlay{{position:absolute;inset:0;background:linear-gradient(135deg,rgba(0,0,0,.7),rgba(0,0,0,.4))}}
.hero-content{{position:relative;z-index:2;padding:20px;max-width:800px}}
.hero h1{{font-size:clamp(2.2rem,6vw,4rem);font-weight:900;margin-bottom:15px;text-shadow:2px 2px 10px rgba(0,0,0,.5);letter-spacing:2px}}
.hero p{{font-size:clamp(1rem,2.5vw,1.4rem);opacity:.95;margin-bottom:35px;font-weight:300}}
.btn{{display:inline-block;padding:16px 40px;border-radius:50px;font-weight:700;font-size:1rem;text-decoration:none;transition:.3s;cursor:pointer}}
.btn-primary{{background:var(--s);color:#fff;box-shadow:0 4px 15px rgba(0,0,0,.3)}}
.btn-primary:hover{{transform:translateY(-3px);box-shadow:0 8px 25px rgba(0,0,0,.4)}}
.btn-outline{{border:2px solid #fff;color:#fff;margin-left:15px}}
.btn-outline:hover{{background:#fff;color:var(--p)}}

/* SECTIONS */
section{{padding:80px 30px}}
.container{{max-width:1100px;margin:0 auto}}
.section-label{{text-transform:uppercase;letter-spacing:3px;color:var(--s);font-size:.85rem;font-weight:700;text-align:center;margin-bottom:8px}}
.section-title{{text-align:center;font-size:clamp(1.8rem,4vw,2.5rem);margin-bottom:15px;color:var(--p);font-weight:800}}
.section-sub{{text-align:center;color:#666;margin-bottom:50px;font-size:1.05rem;max-width:600px;margin-left:auto;margin-right:auto}}
.alt-bg{{background:var(--bg)}}

/* ABOUT */
.about-grid{{display:grid;grid-template-columns:1fr 1fr;gap:50px;align-items:center}}
.about-img img{{border-radius:16px;box-shadow:0 15px 40px rgba(0,0,0,.15)}}
.about-text h2{{font-size:2rem;margin-bottom:20px;color:var(--p)}}
.about-text p{{color:#555;font-size:1.05rem;margin-bottom:15px}}
.about-stats{{display:flex;gap:30px;margin-top:25px}}
.stat{{text-align:center}}.stat .num{{font-size:2rem;font-weight:900;color:var(--s)}}.stat .label{{font-size:.85rem;color:#777}}

/* SERVICES */
.svc-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:25px}}
.svc{{background:#fff;border-radius:16px;padding:35px 25px;text-align:center;box-shadow:0 5px 20px rgba(0,0,0,.06);transition:.3s;border-bottom:4px solid transparent}}
.svc:hover{{transform:translateY(-8px);box-shadow:0 15px 40px rgba(0,0,0,.12);border-bottom-color:var(--s)}}
.svc-icon{{font-size:2.5rem;margin-bottom:15px;display:block;color:var(--s)}}
.svc h3{{color:var(--p);margin-bottom:8px;font-size:1.2rem}}.svc p{{color:#777;font-size:.95rem}}

/* GALLERY */
.gal-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(350px,1fr));gap:20px}}
.gal-item{{border-radius:16px;overflow:hidden;box-shadow:0 8px 25px rgba(0,0,0,.1);transition:.3s}}
.gal-item:hover{{transform:scale(1.03);box-shadow:0 15px 40px rgba(0,0,0,.2)}}
.gal-item img{{width:100%;height:300px;object-fit:cover}}

/* CONTACT */
.contact-grid{{display:grid;grid-template-columns:1fr 1fr;gap:40px;align-items:start}}
.contact-info{{background:var(--p);color:#fff;padding:50px 40px;border-radius:16px}}
.contact-info h3{{font-size:1.5rem;margin-bottom:25px}}
.contact-item{{display:flex;align-items:flex-start;gap:15px;margin-bottom:20px}}
.contact-item .icon{{font-size:1.5rem;color:var(--s);min-width:30px}}
.contact-item p{{font-size:1rem;opacity:.9}}
.map-wrap{{border-radius:16px;overflow:hidden;box-shadow:0 10px 30px rgba(0,0,0,.1);height:100%;min-height:350px}}
.map-wrap iframe{{width:100%;height:100%;min-height:350px;border:none}}

/* CTA */
.cta-section{{background:linear-gradient(135deg,var(--p),var(--s));color:#fff;text-align:center;padding:80px 30px}}
.cta-section h2{{font-size:clamp(1.8rem,4vw,2.5rem);margin-bottom:15px}}.cta-section p{{font-size:1.1rem;opacity:.9;margin-bottom:30px;max-width:600px;margin-left:auto;margin-right:auto}}

/* FOOTER */
footer{{background:var(--p);color:rgba(255,255,255,.7);text-align:center;padding:30px;font-size:.9rem}}
footer a{{color:var(--s);text-decoration:none}}

/* SCROLL ANIM */
.reveal{{opacity:0;transform:translateY(30px);transition:.8s ease}}.reveal.visible{{opacity:1;transform:translateY(0)}}

/* MOBILE */
@media(max-width:768px){{
  nav ul{{position:fixed;top:70px;left:0;right:0;background:var(--p);flex-direction:column;align-items:center;padding:30px;gap:20px;transform:translateY(-150%);transition:.4s;z-index:998}}
  nav ul.open{{transform:translateY(0)}}
  .hamburger{{display:flex}}
  .about-grid,.contact-grid{{grid-template-columns:1fr}}
  .hero{{height:70vh;min-height:400px}}
  section{{padding:60px 20px}}
  .gal-grid{{grid-template-columns:1fr}}
}}
</style>
</head>
<body>
<nav>
  <div class="logo">{name.split()[0] if len(name.split())>1 else name}<span>{" ".join(name.split()[1:])}</span></div>
  <ul id="navMenu">
    <li><a href="#about">About</a></li>
    <li><a href="#services">Services</a></li>
    <li><a href="#gallery">Gallery</a></li>
    <li><a href="#contact">Contact</a></li>
  </ul>
  <button class="hamburger" onclick="document.getElementById('navMenu').classList.toggle('open')">
    <span></span><span></span><span></span>
  </button>
</nav>

<section class="hero">
  <div class="hero-bg"></div>
  <div class="hero-overlay"></div>
  <div class="hero-content">
    <h1>{name}</h1>
    <p>{tagline} &mdash; {city}, {state}</p>
    <a href="#contact" class="btn btn-primary">Visit Us</a>
    <a href="tel:{phone}" class="btn btn-outline">Call Now</a>
  </div>
</section>

<section id="about" class="alt-bg">
  <div class="container">
    <div class="about-grid reveal">
      <div class="about-img"><img src="{photos[1]}" alt="{name} interior"></div>
      <div class="about-text">
        <p class="section-label">Our Story</p>
        <h2>Welcome to {name}</h2>
        <p>{name} is a {btype.lower()} proudly serving {city}, {state} and the surrounding communities. We believe in quality, community, and creating memorable experiences for every customer.</p>
        <p>{notes if notes else f"Stop by and discover why locals love {name}."}</p>
        <div class="about-stats">
          <div class="stat"><div class="num">5&#9733;</div><div class="label">Rated</div></div>
          <div class="stat"><div class="num">100%</div><div class="label">Local</div></div>
          <div class="stat"><div class="num">{city}</div><div class="label">Based</div></div>
        </div>
      </div>
    </div>
  </div>
</section>

<section id="services">
  <div class="container">
    <p class="section-label">What We Offer</p>
    <h2 class="section-title">Our Services</h2>
    <p class="section-sub">Everything you need, all in one place.</p>
    <div class="svc-grid reveal">
{svc_html}
    </div>
  </div>
</section>

<section id="gallery" class="alt-bg">
  <div class="container">
    <p class="section-label">Take a Look</p>
    <h2 class="section-title">Gallery</h2>
    <p class="section-sub">A glimpse of what we have to offer.</p>
    <div class="gal-grid reveal">
{gallery_html}
    </div>
  </div>
</section>

<section class="cta-section">
  <h2>Ready to Experience {name}?</h2>
  <p>Come visit us in {city} — we'd love to welcome you.</p>
  <a href="https://maps.google.com/?q={nm}" class="btn btn-primary" target="_blank" style="background:#fff;color:var(--p)">Get Directions</a>
</section>

<section id="contact">
  <div class="container">
    <p class="section-label">Get In Touch</p>
    <h2 class="section-title">Contact Us</h2>
    <p class="section-sub">We'd love to hear from you.</p>
    <div class="contact-grid reveal">
      <div class="contact-info">
        <h3>{name}</h3>
        <div class="contact-item"><span class="icon">&#128205;</span><p>{addr_display}</p></div>
        <div class="contact-item"><span class="icon">&#128222;</span><p>{phone_html}</p></div>
        <div class="contact-item"><span class="icon">&#128336;</span><p>Call for current hours</p></div>
      </div>
      <div class="map-wrap">
        <iframe src="https://maps.google.com/maps?q={nm}&output=embed" allowfullscreen loading="lazy"></iframe>
      </div>
    </div>
  </div>
</section>

<footer>
  <p>&copy; 2026 {name}. All rights reserved. | Website by <a href="https://pradazay1-code.github.io/marketing-Sauce/" target="_blank">One Vision Marketing</a></p>
</footer>

<script>
// Scroll reveal
const obs=new IntersectionObserver((entries)=>{{entries.forEach(e=>{{if(e.isIntersecting){{e.target.classList.add('visible');obs.unobserve(e.target);}}}});}},{{threshold:0.1}});
document.querySelectorAll('.reveal').forEach(el=>obs.observe(el));
// Smooth scroll
document.querySelectorAll('a[href^="#"]').forEach(a=>{{a.addEventListener('click',e=>{{e.preventDefault();const t=document.querySelector(a.getAttribute('href'));if(t)t.scrollIntoView({{behavior:'smooth'}});document.getElementById('navMenu').classList.remove('open');}});}});
</script>
</body>
</html>'''

    folder = os.path.join(output_dir, slug)
    os.makedirs(folder, exist_ok=True)
    fp = os.path.join(folder, "index.html")
    with open(fp, "w") as f:
        f.write(html)
    print(f"Built: {fp}")
    return fp

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--name"); p.add_argument("--type",dest="btype",default="Business")
    p.add_argument("--city",default="Boston"); p.add_argument("--state",default="MA")
    p.add_argument("--address",default=""); p.add_argument("--phone",default="")
    p.add_argument("--owner",default=""); p.add_argument("--notes",default="")
    p.add_argument("--batch"); p.add_argument("--output",default="clients/leads/websites")
    args = p.parse_args()
    if args.batch:
        with open(args.batch) as f: leads = json.load(f)
        print(f"Building {len(leads)} websites...\n")
        for l in leads:
            build_site(l.get("business_name",l.get("name","Biz")),l.get("type",l.get("business_type","Business")),
                       l.get("city","Boston"),l.get("state","MA"),l.get("address",""),l.get("phone",""),
                       l.get("owner_name",""),l.get("notes",""),args.output)
        print(f"\nDone! {len(leads)} websites built.")
    elif args.name:
        build_site(args.name,args.btype,args.city,args.state,args.address,args.phone,args.owner,args.notes,args.output)
    else: p.print_help()

if __name__=="__main__": main()
