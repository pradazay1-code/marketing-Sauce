"""Industry taxonomy for lead discovery and filtering.

Each industry carries the search terms that actually find it on each source,
plus an ICP weight reflecting how well that trade converts for a local
marketing agency.

The three the CRM is tuned for -- landscaping, junk removal, and newly licensed
real estate agents -- sit at weight 1.0. Everything else is scored relative to
them.

`search_terms` feed keyword search (Firecrawl, Yellow Pages). `osm_tags` feed
OpenStreetMap/Overpass, which uses a fixed tag vocabulary rather than free text.
"""

INDUSTRIES = {
    "landscaping": {
        "label": "Landscaping & Lawn Care",
        "icp_weight": 1.0,
        "search_terms": [
            "landscaping company", "lawn care service", "landscaper",
            "lawn maintenance", "hardscaping contractor", "yard cleanup service",
        ],
        "osm_tags": ["shop=garden_centre", "craft=gardener", "landscaping=yes"],
        "seasonal_peak": "Mar-May",
        "why": "High ticket, repeat seasonal revenue, and most run on word of "
               "mouth alone. Spring is the buying window -- pitch in Jan-Feb.",
    },
    "junk_removal": {
        "label": "Junk Removal & Hauling",
        "icp_weight": 1.0,
        "search_terms": [
            "junk removal", "junk hauling", "debris removal service",
            "dumpster rental", "estate cleanout service", "furniture removal",
        ],
        "osm_tags": ["amenity=waste_transfer_station", "office=company"],
        "seasonal_peak": "Apr-Sep",
        "why": "Almost pure lead-gen economics. Nearly every job starts as a "
               "search, so ranking is the whole business.",
    },
    "real_estate_new": {
        "label": "Real Estate Agents (newly licensed)",
        "icp_weight": 1.0,
        "search_terms": [
            "new real estate agent", "realtor recently licensed",
            "real estate agent", "realtor", "buyers agent",
        ],
        "osm_tags": ["office=estate_agent"],
        "seasonal_peak": "Year-round",
        "why": "Newly licensed agents have a commission budget, no brand, and "
               "no marketing support from their brokerage. Highest urgency in "
               "the taxonomy.",
    },
    "hvac_plumbing": {
        "label": "HVAC & Plumbing",
        "icp_weight": 0.9,
        "search_terms": ["hvac contractor", "plumber", "heating and cooling",
                         "emergency plumber", "boiler repair"],
        "osm_tags": ["craft=plumber", "craft=hvac"],
        "seasonal_peak": "Dec-Feb, Jun-Aug",
        "why": "Emergency intent means searches convert immediately.",
    },
    "roofing": {
        "label": "Roofing & Siding",
        "icp_weight": 0.9,
        "search_terms": ["roofing contractor", "roof repair", "siding contractor"],
        "osm_tags": ["craft=roofer"],
        "seasonal_peak": "Apr-Oct",
        "why": "Very high ticket. One closed job pays for a year of marketing.",
    },
    "auto_repair": {
        "label": "Auto Repair & Detailing",
        "icp_weight": 0.7,
        "search_terms": ["auto repair shop", "mechanic", "car detailing",
                         "collision repair"],
        "osm_tags": ["shop=car_repair"],
        "seasonal_peak": "Year-round",
        "why": "Local search dependent, but thinner margins than the trades.",
    },
    "salon_spa": {
        "label": "Salons, Barbers & Spas",
        "icp_weight": 0.7,
        "search_terms": ["hair salon", "barbershop", "nail salon", "day spa",
                         "med spa"],
        "osm_tags": ["shop=hairdresser", "shop=beauty", "leisure=spa"],
        "seasonal_peak": "Year-round",
        "why": "Instagram-native, so visual content lands. Booking automation "
               "is an easy first win.",
    },
    "restaurant": {
        "label": "Restaurants & Food Service",
        "icp_weight": 0.5,
        "search_terms": ["restaurant", "pizzeria", "cafe", "catering service"],
        "osm_tags": ["amenity=restaurant", "amenity=cafe", "amenity=fast_food"],
        "seasonal_peak": "Year-round",
        "why": "Thin margins and high churn. Included for coverage, not focus.",
    },
    "fitness": {
        "label": "Gyms & Fitness Studios",
        "icp_weight": 0.8,
        "search_terms": ["gym", "fitness studio", "personal trainer",
                         "crossfit box", "yoga studio"],
        "osm_tags": ["leisure=fitness_centre"],
        "seasonal_peak": "Dec-Feb",
        "why": "Membership LTV justifies real ad spend. January is the window.",
    },
    "contractor_general": {
        "label": "General Contractors & Remodeling",
        "icp_weight": 0.9,
        "search_terms": ["general contractor", "home remodeling",
                         "kitchen remodeling", "bathroom remodeling"],
        "osm_tags": ["craft=builder", "office=construction_company"],
        "seasonal_peak": "Mar-Oct",
        "why": "High ticket with long consideration -- retargeting pays.",
    },
    "cleaning": {
        "label": "Cleaning Services",
        "icp_weight": 0.8,
        "search_terms": ["house cleaning service", "commercial cleaning",
                         "maid service", "carpet cleaning"],
        "osm_tags": ["shop=laundry", "craft=cleaning"],
        "seasonal_peak": "Year-round",
        "why": "Recurring revenue, and owners feel the cost of a missed call.",
    },
    "other": {
        "label": "Other / Uncategorized",
        "icp_weight": 0.4,
        "search_terms": [],
        "osm_tags": [],
        "seasonal_peak": "",
        "why": "Anything that did not match a defined industry.",
    },
}

# Priority order for classification: the first industry whose keywords match
# wins, so the focus trades are checked before the broad catch-alls.
CLASSIFY_ORDER = [
    "junk_removal", "landscaping", "real_estate_new", "roofing",
    "hvac_plumbing", "contractor_general", "cleaning", "salon_spa",
    "fitness", "auto_repair", "restaurant",
]

# Substrings checked against business name + category + type. Deliberately
# narrow -- a false positive here misroutes the whole pitch.
_KEYWORDS = {
    "junk_removal": ["junk", "hauling", "haul away", "dumpster", "cleanout",
                     "clean out", "debris", "rubbish", "got junk"],
    "landscaping": ["landscap", "lawn", "yard", "hardscap", "irrigation",
                    "tree service", "arborist", "mulch", "sod", "groundskeep"],
    "real_estate_new": ["real estate", "realtor", "realty", "broker",
                        "buyers agent", "listing agent", "keller williams",
                        "re/max", "remax", "coldwell", "compass real"],
    "roofing": ["roof", "siding", "gutter"],
    "hvac_plumbing": ["hvac", "plumb", "heating", "cooling", "air condition",
                      "boiler", "furnace", "drain"],
    "contractor_general": ["contractor", "remodel", "construction", "carpentry",
                           "renovation", "builder", "handyman"],
    "cleaning": ["cleaning", "maid", "janitorial", "housekeep", "carpet clean",
                 "power wash", "pressure wash"],
    "salon_spa": ["salon", "barber", "spa", "nails", "hair", "beauty",
                  "lash", "brow", "massage"],
    "fitness": ["gym", "fitness", "crossfit", "yoga", "pilates",
                "personal train", "martial arts"],
    "auto_repair": ["auto", "mechanic", "collision", "tire", "detailing",
                    "transmission", "muffler"],
    # "pizz" not "pizza" -- "pizzeria" does not contain "pizza".
    "restaurant": ["restaurant", "pizz", "cafe", "coffee", "diner", "bakery",
                   "catering", "grill", "tavern", "deli", "bistro", "eatery"],
}


def classify(business_name="", category="", business_type=""):
    """Best-guess industry key from the text we already hold about a lead."""
    haystack = " ".join(
        str(x or "") for x in (business_name, category, business_type)
    ).lower()
    if not haystack.strip():
        return "other"
    for key in CLASSIFY_ORDER:
        for kw in _KEYWORDS.get(key, []):
            if kw in haystack:
                return key
    return "other"


def industry_label(key):
    return INDUSTRIES.get(key, INDUSTRIES["other"])["label"]


def icp_weight(key):
    return INDUSTRIES.get(key, INDUSTRIES["other"])["icp_weight"]


def search_terms(key):
    return INDUSTRIES.get(key, {}).get("search_terms", [])


def all_industries():
    """Serializable list for the UI, focus industries first."""
    order = CLASSIFY_ORDER + ["other"]
    return [
        {
            "key": k,
            "label": INDUSTRIES[k]["label"],
            "icp_weight": INDUSTRIES[k]["icp_weight"],
            "seasonal_peak": INDUSTRIES[k]["seasonal_peak"],
            "why": INDUSTRIES[k]["why"],
            "focus": INDUSTRIES[k]["icp_weight"] >= 1.0,
        }
        for k in order if k in INDUSTRIES
    ]
