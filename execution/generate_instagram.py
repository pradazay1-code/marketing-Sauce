#!/usr/bin/env python3
"""
Instagram Content Generator — Execution Script
Generates Instagram-ready content: posts, carousels, reels, stories, calendars.
Works standalone or integrated with the LeadPilot dashboard.
"""

import argparse
import json
import os
import random
import sys
from datetime import datetime, timedelta

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)

# ---------------------------------------------------------------------------
# Content Pillars & Templates
# ---------------------------------------------------------------------------

REAL_ESTATE_PILLARS = [
    "listing",
    "education",
    "community",
    "behind_the_scenes",
    "testimonial",
    "market_stats",
]

PILLAR_LABELS = {
    "listing": "Listings & Market Updates",
    "education": "Buyer/Seller Education",
    "community": "Community Spotlight",
    "behind_the_scenes": "Behind the Scenes",
    "testimonial": "Client Success Story",
    "market_stats": "Market Authority",
}

# Hook templates by pillar
HOOKS = {
    "listing": [
        "This home just hit the market and it won't last long.",
        "POV: You just found your next home.",
        "New listing alert 🏠 — {city}, MA",
        "Under $XXX,000 in {city}? It exists.",
        "3 things that make this property stand out ↓",
        "Would you live here? Be honest.",
        "Just listed — and the backyard alone is worth it.",
        "This {city} home checks every box.",
    ],
    "education": [
        "Nobody tells first-time buyers this.",
        "Stop making this mistake when selling your home.",
        "The #1 thing that kills deals (it's not price).",
        "Here's exactly what happens after your offer gets accepted.",
        "Your credit score doesn't need to be perfect to buy a home.",
        "Renting vs. buying in 2026 — let's talk real numbers.",
        "5 hidden costs of buying a home nobody warns you about.",
        "The inspection came back — now what?",
        "Pre-approved ≠ pre-qualified. Here's the difference.",
        "How to win a bidding war without overpaying.",
    ],
    "community": [
        "Why {city} is one of MA's best-kept secrets.",
        "My favorite spots in {city} — save this list.",
        "New restaurant in {city} you need to try.",
        "This neighborhood has everything — here's proof.",
        "Living in {city}: the honest truth.",
        "3 reasons families are moving to {city}.",
    ],
    "behind_the_scenes": [
        "What a day in real estate actually looks like.",
        "This is what happened at today's showing.",
        "The part of real estate nobody shows you.",
        "Early morning showings hit different.",
        "Real talk — this job isn't just open houses.",
        "Another closing day in the books ✅",
        "Behind the scenes of a big deal.",
    ],
    "testimonial": [
        "Another family in their forever home.",
        "From pre-approval to keys in 45 days.",
        "They said the market was too tough. We proved them wrong.",
        "Closing day never gets old.",
        "\"We didn't think we could afford it\" — here's their story.",
        "First-time buyers → homeowners. That's the goal.",
    ],
    "market_stats": [
        "MA housing market update — {month} 2026.",
        "Home prices in {city} just did something unexpected.",
        "Interest rates this week: what it means for you.",
        "Is it a buyer's or seller's market right now? Let's look at the data.",
        "The numbers don't lie — here's what's happening in MA real estate.",
        "3 market trends every buyer needs to know right now.",
        "Inventory is shifting — here's what that means.",
    ],
}

# Body templates by pillar
BODY_TEMPLATES = {
    "listing": [
        "📍 {city}, MA\n\n✅ {beds} bed / {baths} bath\n✅ {sqft} sq ft\n✅ {feature1}\n✅ {feature2}\n✅ {feature3}\n\nThis one's priced to move. If you've been waiting for the right property, this might be it.\n\nSchedule a private showing before it's gone.",
        "New on the market in {city} 👇\n\nThis property has everything today's buyers are looking for — updated kitchen, natural light throughout, and a location that's hard to beat.\n\nI've already had multiple inquiries. Don't sleep on this one.\n\nDM me \"TOUR\" for details + showing times.",
    ],
    "education": [
        "Most people overcomplicate this. Here's the simple version:\n\n1️⃣ {step1}\n2️⃣ {step2}\n3️⃣ {step3}\n4️⃣ {step4}\n5️⃣ {step5}\n\nBookmark this for when you need it. And if you have questions, my DMs are always open.",
        "I see this mistake constantly.\n\n{mistake_description}\n\nThe fix? {fix_description}\n\nThis alone could save you thousands (or prevent a deal from falling apart).\n\n💬 Drop a question below — I answer everything.",
    ],
    "community": [
        "I get asked \"where should I move in MA?\" all the time.\n\n{city} keeps coming up, and here's why:\n\n🏫 Great schools\n🍽️ Amazing local restaurants\n🏡 Homes that actually hold value\n🚗 Easy commute to Boston\n\nWant to know more about living here? I'll send you my neighborhood guide — just DM me \"{city}\".",
    ],
    "behind_the_scenes": [
        "Today's schedule:\n\n7:00 AM — Coffee + market research\n9:00 AM — Client call (first-time buyer)\n10:30 AM — Showing in {city}\n12:00 PM — Lunch meeting with lender\n2:00 PM — Contract review\n4:00 PM — Open house prep\n6:00 PM — Listing photos\n\nThis job is anything but 9-5. But watching clients get their keys makes every long day worth it.",
    ],
    "testimonial": [
        "Meet my latest clients 🎉\n\nWhen we first connected, they were told they couldn't buy in this market. Too competitive. Not enough inventory.\n\nBut here's what actually happened:\n\n✅ Got pre-approved in 5 days\n✅ Found the perfect home in 3 weeks\n✅ Closed under asking price\n\nThe market isn't impossible — you just need someone who knows how to navigate it.\n\nReady to start your journey? Link in bio.",
    ],
    "market_stats": [
        "📊 MA Real Estate Update — {month} 2026\n\n🏠 Median Home Price: ${median_price}\n📈 YoY Change: {yoy_change}\n📦 Active Inventory: {inventory}\n⏱️ Avg Days on Market: {dom}\n\nWhat this means for you:\n\n🔵 Buyers: {buyer_insight}\n🟢 Sellers: {seller_insight}\n\nWant a breakdown for your specific city? DM me your zip code.",
    ],
}

# CTA options
CTAS = [
    "DM me to get started.",
    "Link in bio for a free consultation.",
    "Comment \"INFO\" and I'll reach out.",
    "Save this for later 📌",
    "Share this with someone who needs to hear it.",
    "DM me your zip code for a free market report.",
    "Tag someone who's thinking about buying.",
    "Follow for daily real estate tips.",
    "Ready to make a move? Let's talk → link in bio.",
    "Drop a 🏠 if you're house hunting right now.",
]

# Hashtag bank by category
HASHTAGS = {
    "broad": [
        "#realestate", "#realtor", "#home", "#property", "#househunting",
        "#dreamhome", "#newhome", "#homesforsale", "#realtorlife",
        "#investment", "#luxury", "#interiordesign",
    ],
    "medium": [
        "#firsttimehomebuyer", "#homebuyertips", "#sellingyourhome",
        "#realestateinvesting", "#realestateagent", "#homebuying",
        "#openhouse", "#justlisted", "#homesearch", "#propertyinvestment",
        "#realtortips", "#homeownership", "#closingday", "#newlisting",
        "#housegoals", "#realestatelife", "#mortgagetips",
    ],
    "niche_ma": [
        "#massachusettsrealestate", "#marealestate", "#bostonrealestate",
        "#southshorema", "#metrowestma", "#masshomes", "#livinginma",
        "#massachusettshomes", "#mareaitor", "#newenglandrealestate",
        "#newenglandhomes", "#bostonhomes", "#mahomesforsale",
    ],
    "engagement": [
        "#realestatetips", "#housingmarket", "#marketupdate",
        "#homevalue", "#buyersmarket", "#sellersmarket",
    ],
}

MA_CITIES = [
    "Boston", "Worcester", "Springfield", "Cambridge", "Lowell",
    "Brockton", "New Bedford", "Quincy", "Lynn", "Fall River",
    "Newton", "Somerville", "Framingham", "Brookline", "Plymouth",
    "Bridgewater", "Taunton", "Attleboro", "Weymouth", "Medford",
]

FEATURES = [
    "Updated kitchen with quartz counters", "Hardwood floors throughout",
    "Finished basement", "Central AC", "2-car garage",
    "Private backyard", "Open floor plan", "Renovated bathrooms",
    "Walk-in closets", "Stainless steel appliances",
    "Fireplace", "In-unit laundry", "Deck/patio",
    "New roof (2024)", "Energy-efficient windows",
    "Close to public transit", "Top-rated school district",
]

CAROUSEL_TOPICS = {
    "education": [
        {
            "title": "5 Things to Do BEFORE You Start House Hunting",
            "slides": [
                "5 Things to Do BEFORE You Start House Hunting",
                "1. Check your credit score\nKnow where you stand. Anything above 620 can work — 740+ gets the best rates.",
                "2. Get pre-approved (not pre-qualified)\nPre-approval means a lender actually verified your finances. Sellers take it seriously.",
                "3. Calculate your REAL budget\nMortgage + taxes + insurance + maintenance. Most people forget the last two.",
                "4. Save beyond the down payment\nClosing costs = 2-5% of purchase price. Plus you'll want a move-in buffer.",
                "5. Find an agent BEFORE you find a house\nA good agent will find homes before they hit the market and negotiate in your favor.",
                "The biggest mistake? Skipping these steps and jumping straight into Zillow.\n\nDo this first. Thank me later.",
                "Ready to start the right way?\n\nDM me \"READY\" and I'll walk you through it step by step.\n\n— Kunal Patel\nAkira Real Estate",
            ],
        },
        {
            "title": "Buying vs. Renting in MA — The Real Math",
            "slides": [
                "Buying vs. Renting in MA\nThe real math nobody shows you 📊",
                "Average MA rent: $2,800/mo\nThat's $33,600/year going to your landlord's mortgage.",
                "Average MA mortgage: $2,950/mo\n(on a $450K home, 6.5% rate, 10% down)",
                "\"But buying is more expensive!\"\n\nNot when you factor in:\n✅ Equity building\n✅ Tax deductions\n✅ Fixed payments (rent goes up every year)",
                "After 5 years renting:\n$168,000 spent → $0 equity\n\nAfter 5 years owning:\n$177,000 spent → ~$85,000 in equity",
                "The gap closes fast.\nAnd in a market like MA where home values appreciate 3-5% annually? Buying wins long-term.",
                "Is buying right for YOU?\nIt depends on your timeline, finances, and goals.\n\nDM me — I'll give you an honest answer.",
                "Kunal Patel\nAkira Real Estate\n📱 DM or link in bio",
            ],
        },
        {
            "title": "What Sellers Do Wrong (And How to Fix It)",
            "slides": [
                "What Sellers Do Wrong\n(And how to fix it before listing)",
                "❌ Overpricing based on emotion\n✅ Price based on comps + market data\n\nYour home is worth what buyers will pay — not what you spent on renovations.",
                "❌ Skipping staging\n✅ Stage key rooms at minimum\n\nStaged homes sell 73% faster. Even decluttering + fresh paint makes a huge difference.",
                "❌ Bad listing photos\n✅ Invest in professional photography\n\nFirst impression is online. Dark, blurry photos = instant scroll past.",
                "❌ Being inflexible on showings\n✅ Make it easy for buyers to see the home\n\nEvery missed showing is a missed offer.",
                "❌ Ignoring the first 2 weeks\n✅ Launch strong and generate urgency\n\n90% of activity happens in the first 14 days. Don't waste your best window.",
                "Get it right the first time.\n\nDM me \"SELL\" and I'll send you my pre-listing checklist for free.",
                "Kunal Patel | Akira Real Estate\n📱 DM or link in bio",
            ],
        },
    ],
    "market_stats": [
        {
            "title": "MA Housing Market — What's Really Happening",
            "slides": [
                "MA Housing Market\nWhat's REALLY happening right now 📊",
                "📈 Home prices are still climbing\nMedian sale price: ~$575,000\nUp from $548K last year",
                "📦 Inventory is finally increasing\nMore homes = more options for buyers\nBut still below pre-2020 levels",
                "⏱️ Homes are selling in ~21 days\nDown from 30+ days last year\nGood homes go FAST",
                "💰 Interest rates: 6.2-6.8%\nNot the 3% days, but historically still normal\nDon't wait for rates that may never come back",
                "What this means for BUYERS:\nMore choices than last year, but act fast on good ones. Get pre-approved NOW.",
                "What this means for SELLERS:\nYou still have the advantage. Price it right and you'll get multiple offers.",
                "Want a free market report for YOUR zip code?\n\nDM me your zip → I'll send it within 24 hours.\n\nKunal Patel | Akira Real Estate",
            ],
        },
    ],
}

REEL_SCRIPTS = [
    {
        "pillar": "education",
        "title": "3 Signs You're Ready to Buy",
        "hook": "If you can check all 3 of these boxes, you're ready to buy a home.",
        "scenes": [
            {"time": "0-3s", "visual": "Face to camera, bold text overlay", "text": "3 signs you're ready to buy a home 🏠", "action": "Hook — stop the scroll"},
            {"time": "3-8s", "visual": "Hold up 1 finger", "text": "1. You've been at your job for 2+ years", "action": "Lenders want stability"},
            {"time": "8-13s", "visual": "Hold up 2 fingers", "text": "2. You have 3-6 months of expenses saved", "action": "Beyond the down payment"},
            {"time": "13-18s", "visual": "Hold up 3 fingers", "text": "3. Your rent is more than a mortgage would be", "action": "Show the math"},
            {"time": "18-23s", "visual": "Lean in to camera", "text": "If that's you — stop paying someone else's mortgage.", "action": "CTA"},
            {"time": "23-28s", "visual": "Point to bio / DM button", "text": "DM me 'READY' and let's get you started.", "action": "Close"},
        ],
        "audio": "Trending audio — upbeat, motivational",
        "duration": "28 seconds",
    },
    {
        "pillar": "behind_the_scenes",
        "title": "Day in My Life as a Realtor",
        "hook": "What being a realtor actually looks like (no glamour shots)",
        "scenes": [
            {"time": "0-3s", "visual": "Alarm clock / morning routine", "text": "6:30 AM — Day in my life as a MA realtor", "action": "Hook"},
            {"time": "3-8s", "visual": "Coffee + laptop", "text": "7 AM — Checking new listings + responding to overnight leads", "action": "Morning routine"},
            {"time": "8-12s", "visual": "Driving", "text": "9 AM — Driving to first showing", "action": "Transition"},
            {"time": "12-17s", "visual": "Walking through house", "text": "10 AM — Walking a buyer through a property they found at 11 PM last night", "action": "Showing"},
            {"time": "17-22s", "visual": "On phone / laptop", "text": "1 PM — Writing an offer + negotiating with listing agent", "action": "The real work"},
            {"time": "22-27s", "visual": "Happy clients / keys", "text": "This is why I do it 🔑", "action": "Emotional payoff"},
        ],
        "audio": "Lo-fi / chill background — 'day in my life' vibe",
        "duration": "27 seconds",
    },
    {
        "pillar": "market_stats",
        "title": "Stop Waiting for Rates to Drop",
        "hook": "Everyone's waiting for rates to drop. Here's why that's a mistake.",
        "scenes": [
            {"time": "0-3s", "visual": "Face to camera, serious expression", "text": "Stop waiting for rates to drop.", "action": "Controversial hook"},
            {"time": "3-8s", "visual": "Show historical rate chart", "text": "In the 80s, rates were 18%. In the 2000s, 6-7%. The 3% era was the exception, not the norm.", "action": "Context"},
            {"time": "8-15s", "visual": "Calculator / numbers on screen", "text": "If rates drop 1%, prices will jump 10-15% because of demand. You'll pay MORE for the same house.", "action": "The math"},
            {"time": "15-20s", "visual": "Face to camera", "text": "Buy now, refinance later. Date the rate, marry the house.", "action": "Advice"},
            {"time": "20-25s", "visual": "Point to camera", "text": "DM me — I'll show you what you can afford TODAY.", "action": "CTA"},
        ],
        "audio": "Dramatic / attention-grabbing trending sound",
        "duration": "25 seconds",
    },
]

STORY_SEQUENCES = [
    {
        "theme": "This or That — Home Edition",
        "frames": [
            {"type": "text", "content": "This or That 🏠\nHome Edition", "sticker": None},
            {"type": "poll", "content": "Open floor plan vs. Defined rooms", "sticker": "poll"},
            {"type": "poll", "content": "Big backyard vs. Low maintenance", "sticker": "poll"},
            {"type": "poll", "content": "Move-in ready vs. Fixer-upper (save $$$)", "sticker": "poll"},
            {"type": "poll", "content": "City living vs. Suburbs", "sticker": "poll"},
            {"type": "text", "content": "Want to find a home that matches YOUR answers?\n\nDM me — let's chat 💬", "sticker": None},
        ],
    },
    {
        "theme": "Quick Tip Tuesday",
        "frames": [
            {"type": "text", "content": "Quick Tip Tuesday 💡", "sticker": None},
            {"type": "text", "content": "Before you make an offer...\n\nAlways check what the neighbors sold for.", "sticker": None},
            {"type": "text", "content": "This tells you:\n✅ If the price is fair\n✅ What the market supports\n✅ Your negotiation leverage", "sticker": None},
            {"type": "question", "content": "What's your biggest question about buying?", "sticker": "question_box"},
            {"type": "text", "content": "I answer every DM 📱\n\nKunal Patel | Akira Real Estate", "sticker": None},
        ],
    },
    {
        "theme": "Market Update Monday",
        "frames": [
            {"type": "text", "content": "Market Update Monday 📊", "sticker": None},
            {"type": "text", "content": "This week in MA real estate:\n\n📈 New listings up 12%\n⏱️ Avg days on market: 19\n💰 Median price: $575K", "sticker": None},
            {"type": "slider", "content": "How's the market feeling to you?", "sticker": "emoji_slider (🔥)"},
            {"type": "text", "content": "Want a report for YOUR area?\n\nDM me your zip code 📍", "sticker": None},
        ],
    },
]


def load_client_profile(client_name):
    """Load client profile from CLIENT_SUMMARY.md."""
    path = os.path.join(PROJECT_ROOT, "clients", client_name, "CLIENT_SUMMARY.md")
    if os.path.exists(path):
        with open(path) as f:
            return f.read()
    return ""


def pick_hashtags(count=25):
    """Generate a balanced hashtag set."""
    tags = []
    tags.extend(random.sample(HASHTAGS["broad"], min(5, len(HASHTAGS["broad"]))))
    tags.extend(random.sample(HASHTAGS["medium"], min(8, len(HASHTAGS["medium"]))))
    tags.extend(random.sample(HASHTAGS["niche_ma"], min(8, len(HASHTAGS["niche_ma"]))))
    tags.extend(random.sample(HASHTAGS["engagement"], min(4, len(HASHTAGS["engagement"]))))
    random.shuffle(tags)
    return tags[:count]


def generate_post(pillar=None, city=None, owner="Kunal Patel", brand="Akira Real Estate"):
    """Generate a single Instagram post."""
    if not pillar:
        pillar = random.choice(REAL_ESTATE_PILLARS)
    if not city:
        city = random.choice(MA_CITIES)

    month = datetime.now().strftime("%B")
    price = random.choice(["350", "399", "425", "449", "475", "499", "525", "549", "599"])
    hook = random.choice(HOOKS[pillar]).format(city=city, month=month)
    hook = hook.replace("$XXX,000", f"${price},000")
    body_template = random.choice(BODY_TEMPLATES[pillar])

    features = random.sample(FEATURES, 5)
    body = body_template.format(
        city=city,
        month=month,
        beds=random.choice(["3", "4", "5"]),
        baths=random.choice(["2", "2.5", "3"]),
        sqft=random.choice(["1,800", "2,200", "2,500", "3,000"]),
        feature1=features[0],
        feature2=features[1],
        feature3=features[2],
        step1="Check your credit score — know where you stand",
        step2="Get pre-approved with a lender (not just pre-qualified)",
        step3="Set your REAL budget — mortgage + taxes + insurance",
        step4="Find an agent who knows the local market",
        step5="Start touring homes — but don't rush into offers",
        mistake_description="Buyers skip the pre-approval and go straight to touring homes. Then they find the perfect house — and lose it because they can't move fast enough.",
        fix_description="Get pre-approved FIRST. It takes 24-48 hours and puts you ahead of 80% of other buyers.",
        median_price="575,000",
        yoy_change="+4.9%",
        inventory="12,400 active listings",
        dom="21 days",
        buyer_insight="More inventory means more options. Get pre-approved and act fast on the right one.",
        seller_insight="Pricing correctly is everything. Overpriced homes sit — well-priced homes get multiple offers.",
    )

    cta = random.choice(CTAS)
    hashtags = pick_hashtags(25)

    caption = f"{hook}\n\n{body}\n\n{cta}\n\n— {owner}\n{brand}"

    return {
        "type": "post",
        "pillar": pillar,
        "pillar_label": PILLAR_LABELS[pillar],
        "hook": hook,
        "caption": caption,
        "hashtags": " ".join(hashtags),
        "cta": cta,
        "suggested_visual": _suggest_visual(pillar, city),
        "city": city,
        "generated_at": datetime.now().isoformat(),
    }


_used_carousel_titles = set()

def generate_carousel(topic_pillar=None, owner="Kunal Patel", brand="Akira Real Estate"):
    """Generate a carousel post with slide-by-slide text."""
    if not topic_pillar:
        topic_pillar = random.choice(list(CAROUSEL_TOPICS.keys()))

    topics = CAROUSEL_TOPICS[topic_pillar]
    available = [t for t in topics if t["title"] not in _used_carousel_titles]
    if not available:
        _used_carousel_titles.clear()
        available = topics
    topic = random.choice(available)
    _used_carousel_titles.add(topic["title"])

    hashtags = pick_hashtags(25)
    cta = random.choice(CTAS)

    caption = f"{topic['slides'][0]}\n\nSwipe through for the full breakdown 👉\n\n{cta}\n\n— {owner}\n{brand}"

    return {
        "type": "carousel",
        "pillar": topic_pillar,
        "pillar_label": PILLAR_LABELS[topic_pillar],
        "title": topic["title"],
        "slides": [{"slide_number": i + 1, "text": slide} for i, slide in enumerate(topic["slides"])],
        "slide_count": len(topic["slides"]),
        "caption": caption,
        "hashtags": " ".join(hashtags),
        "cta": cta,
        "design_notes": "Use brand colors. Slide 1 = bold title. Middle slides = clean text on solid bg. Last slide = CTA with contact info.",
        "generated_at": datetime.now().isoformat(),
    }


def generate_reel(owner="Kunal Patel", brand="Akira Real Estate"):
    """Generate a reel script."""
    script = random.choice(REEL_SCRIPTS)
    hashtags = pick_hashtags(25)
    cta = random.choice(CTAS)

    caption = f"{script['hook']}\n\n{cta}\n\n— {owner}\n{brand}"

    return {
        "type": "reel",
        "pillar": script["pillar"],
        "pillar_label": PILLAR_LABELS[script["pillar"]],
        "title": script["title"],
        "hook": script["hook"],
        "duration": script["duration"],
        "scenes": script["scenes"],
        "audio_suggestion": script["audio"],
        "caption": caption,
        "hashtags": " ".join(hashtags),
        "cta": cta,
        "generated_at": datetime.now().isoformat(),
    }


def generate_story():
    """Generate a story sequence."""
    story = random.choice(STORY_SEQUENCES)

    return {
        "type": "story",
        "theme": story["theme"],
        "frame_count": len(story["frames"]),
        "frames": [
            {
                "frame_number": i + 1,
                "type": frame["type"],
                "content": frame["content"],
                "sticker": frame.get("sticker"),
            }
            for i, frame in enumerate(story["frames"])
        ],
        "generated_at": datetime.now().isoformat(),
    }


def generate_calendar(days=7, owner="Kunal Patel", brand="Akira Real Estate"):
    """Generate a content calendar for N days."""
    _used_carousel_titles.clear()
    calendar = []
    start_date = datetime.now()

    pillar_rotation = [
        "education", "listing", "community",
        "behind_the_scenes", "education", "testimonial", "market_stats",
    ]
    content_type_rotation = [
        "carousel", "post", "reel", "post", "carousel", "post", "story",
    ]

    for i in range(days):
        post_date = start_date + timedelta(days=i)
        pillar = pillar_rotation[i % len(pillar_rotation)]
        content_type = content_type_rotation[i % len(content_type_rotation)]

        if content_type == "carousel":
            content = generate_carousel(
                topic_pillar=pillar if pillar in CAROUSEL_TOPICS else None,
                owner=owner, brand=brand,
            )
        elif content_type == "reel":
            content = generate_reel(owner=owner, brand=brand)
        elif content_type == "story":
            content = generate_story()
        else:
            content = generate_post(pillar=pillar, owner=owner, brand=brand)

        entry = {
            "day": i + 1,
            "date": post_date.strftime("%Y-%m-%d"),
            "day_of_week": post_date.strftime("%A"),
            "content_type": content_type,
            "pillar": pillar,
            "pillar_label": PILLAR_LABELS[pillar],
            "best_time": random.choice(["11:00 AM", "12:00 PM", "7:00 PM", "8:00 PM"]),
            "content": content,
        }
        calendar.append(entry)

    return calendar


def _suggest_visual(pillar, city):
    """Suggest a visual for the post."""
    visuals = {
        "listing": f"High-quality property photos — exterior + best interior room. Location: {city}, MA.",
        "education": "Clean graphic with numbered list or bold text on brand-colored background.",
        "community": f"Local photos of {city} — downtown, restaurants, parks, neighborhood shots.",
        "behind_the_scenes": "Raw/authentic photos or video — showing, desk work, driving, client meetings.",
        "testimonial": "Client closing day photo with keys, or text-over photo with their quote.",
        "market_stats": "Data visualization — bar chart, line graph, or bold stat numbers on clean background.",
    }
    return visuals.get(pillar, "Professional photo related to the topic.")


def format_calendar_markdown(calendar_data, owner="Kunal Patel", brand="Akira Real Estate"):
    """Format calendar data as readable Markdown."""
    lines = [
        f"# Instagram Content Calendar — {brand}",
        f"**Prepared by:** Aventis Marketing",
        f"**Generated:** {datetime.now().strftime('%B %d, %Y')}",
        f"**Client:** {owner} | {brand}",
        "",
        "---",
        "",
    ]

    for entry in calendar_data:
        lines.append(f"## Day {entry['day']} — {entry['day_of_week']}, {entry['date']}")
        lines.append(f"**Type:** {entry['content_type'].upper()} | **Pillar:** {entry['pillar_label']} | **Post at:** {entry['best_time']} EST")
        lines.append("")

        content = entry["content"]

        if entry["content_type"] == "carousel":
            lines.append(f"### 📑 Carousel: {content.get('title', '')}")
            lines.append("")
            for slide in content.get("slides", []):
                lines.append(f"**Slide {slide['slide_number']}:**")
                lines.append(f"> {slide['text']}")
                lines.append("")
            lines.append(f"**Caption:**")
            lines.append(f"```\n{content.get('caption', '')}\n```")
            lines.append("")

        elif entry["content_type"] == "reel":
            lines.append(f"### 🎬 Reel: {content.get('title', '')}")
            lines.append(f"**Duration:** {content.get('duration', '30s')} | **Audio:** {content.get('audio_suggestion', '')}")
            lines.append("")
            for scene in content.get("scenes", []):
                lines.append(f"- **[{scene['time']}]** {scene['text']} — _{scene['action']}_")
            lines.append("")
            lines.append(f"**Caption:**")
            lines.append(f"```\n{content.get('caption', '')}\n```")
            lines.append("")

        elif entry["content_type"] == "story":
            lines.append(f"### 📱 Story: {content.get('theme', '')}")
            lines.append("")
            for frame in content.get("frames", []):
                sticker = f" [{frame['sticker']}]" if frame.get("sticker") else ""
                lines.append(f"- **Frame {frame['frame_number']}** ({frame['type']}{sticker}): {frame['content']}")
            lines.append("")

        else:
            lines.append(f"### 📸 Post: {content.get('pillar_label', '')}")
            lines.append("")
            lines.append(f"**Caption:**")
            lines.append(f"```\n{content.get('caption', '')}\n```")
            lines.append("")
            lines.append(f"**Visual:** {content.get('suggested_visual', '')}")
            lines.append("")

        if content.get("hashtags"):
            lines.append(f"**Hashtags:**")
            lines.append(f"`{content['hashtags']}`")
            lines.append("")

        lines.append("---")
        lines.append("")

    return "\n".join(lines)


def save_content(content, client_name, filename):
    """Save generated content to client's content folder."""
    content_dir = os.path.join(PROJECT_ROOT, "clients", client_name, "content")
    os.makedirs(content_dir, exist_ok=True)
    path = os.path.join(content_dir, filename)
    with open(path, "w") as f:
        if filename.endswith(".json"):
            json.dump(content, f, indent=2)
        else:
            f.write(content)
    return path


def main():
    parser = argparse.ArgumentParser(description="Instagram Content Generator")
    parser.add_argument("--client", default="akira-real-estate", help="Client folder name")
    parser.add_argument("--type", choices=["post", "carousel", "reel", "story", "calendar"],
                        default="calendar", help="Content type to generate")
    parser.add_argument("--count", type=int, default=7, help="Number of days (calendar) or posts")
    parser.add_argument("--pillar", choices=REAL_ESTATE_PILLARS, help="Content pillar")
    parser.add_argument("--city", help="City for location-based content")
    parser.add_argument("--owner", default="Kunal Patel", help="Client owner name")
    parser.add_argument("--brand", default="Akira Real Estate", help="Brand name")
    parser.add_argument("--save", action="store_true", help="Save output to client folder")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    if args.type == "post":
        results = [generate_post(pillar=args.pillar, city=args.city,
                                  owner=args.owner, brand=args.brand)
                   for _ in range(args.count)]
    elif args.type == "carousel":
        results = [generate_carousel(topic_pillar=args.pillar,
                                      owner=args.owner, brand=args.brand)
                   for _ in range(args.count)]
    elif args.type == "reel":
        results = [generate_reel(owner=args.owner, brand=args.brand)
                   for _ in range(args.count)]
    elif args.type == "story":
        results = [generate_story() for _ in range(args.count)]
    elif args.type == "calendar":
        results = generate_calendar(days=args.count, owner=args.owner, brand=args.brand)
    else:
        results = []

    if args.json:
        output = json.dumps(results, indent=2)
        print(output)
    elif args.type == "calendar":
        md = format_calendar_markdown(results, owner=args.owner, brand=args.brand)
        print(md)
    else:
        for i, item in enumerate(results):
            print(f"\n{'='*60}")
            print(f"  {item.get('type', '').upper()} #{i+1} — {item.get('pillar_label', '')}")
            print(f"{'='*60}\n")

            if item["type"] == "carousel":
                print(f"Title: {item['title']}")
                print(f"Slides: {item['slide_count']}")
                print()
                for slide in item["slides"]:
                    print(f"  [Slide {slide['slide_number']}]")
                    print(f"  {slide['text']}")
                    print()
            elif item["type"] == "reel":
                print(f"Title: {item['title']}")
                print(f"Duration: {item['duration']}")
                print(f"Audio: {item['audio_suggestion']}")
                print()
                for scene in item["scenes"]:
                    print(f"  [{scene['time']}] {scene['text']}")
                    print(f"           → {scene['action']}")
                print()
            elif item["type"] == "story":
                print(f"Theme: {item['theme']}")
                print()
                for frame in item["frames"]:
                    sticker = f" [{frame['sticker']}]" if frame.get("sticker") else ""
                    print(f"  Frame {frame['frame_number']} ({frame['type']}{sticker}):")
                    print(f"    {frame['content']}")
                print()
            else:
                print(f"Visual: {item.get('suggested_visual', '')}")
                print()

            print("CAPTION:")
            print(item.get("caption", ""))
            print()
            if item.get("hashtags"):
                print("HASHTAGS:")
                print(item["hashtags"])

    if args.save:
        if args.type == "calendar":
            md = format_calendar_markdown(results, owner=args.owner, brand=args.brand)
            md_path = save_content(md, args.client, "instagram_calendar.md")
            json_path = save_content(results, args.client, "instagram_calendar.json")
            print(f"\n✅ Saved: {md_path}")
            print(f"✅ Saved: {json_path}")
        else:
            json_path = save_content(results, args.client, f"instagram_{args.type}s.json")
            print(f"\n✅ Saved: {json_path}")


if __name__ == "__main__":
    main()
