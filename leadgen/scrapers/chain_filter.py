"""
AventisAI — Chain/Franchise Filter

Filters out national chains, franchises, and big-box businesses from lead results.
We only want LOCAL small businesses for outreach — not McDonald's or Starbucks.
"""

import re

# Lowercase normalized chain names. Match via substring or exact.
# Organized by industry for maintainability.
CHAIN_NAMES = {
    # Fast food
    "mcdonald", "burger king", "wendy's", "wendys", "taco bell", "kfc",
    "kentucky fried", "chick-fil-a", "chickfila", "popeyes", "popeye's",
    "arby's", "arbys", "sonic drive", "jack in the box", "carl's jr",
    "hardee's", "hardees", "five guys", "whataburger", "in-n-out",
    "raising cane", "wingstop", "zaxby", "jimmy john", "jersey mike",
    "firehouse subs", "culver's", "culvers", "shake shack",
    "chipotle", "qdoba", "moe's southwest", "panera", "jason's deli",
    "mcalister", "potbelly", "which wich", "blaze pizza", "mod pizza",
    "panda express", "chick fil a", "del taco", "el pollo loco",
    "church's chicken", "churchs chicken", "rallys", "rally's",
    "checkers", "white castle", "krystal", "steak 'n shake",
    "steak n shake", "cook out", "cookout", "waba grill",
    "tropical smoothie", "smoothie king", "jamba juice", "jamba",
    "auntie anne", "cinnabon", "wetzel's pretzel", "charleys philly",

    # Coffee
    "starbucks", "dunkin", "tim horton", "peet's coffee", "peets coffee",
    "caribou coffee", "dutch bros", "scooter's coffee", "biggby",
    "the human bean", "coffee bean & tea", "community coffee",

    # Pizza chains
    "domino's", "dominos", "pizza hut", "papa john", "little caesars",
    "little caesar", "papa murphy", "marco's pizza", "marcos pizza",
    "hungry howie", "round table pizza", "jet's pizza", "jets pizza",
    "donatos", "cicis pizza", "cici's", "sbarro",

    # Casual dining chains
    "applebee", "chili's", "chilis", "tgi friday", "olive garden",
    "red lobster", "outback steakhouse", "longhorn steakhouse",
    "texas roadhouse", "cracker barrel", "denny's", "dennys",
    "ihop", "waffle house", "bob evans", "perkins", "golden corral",
    "cheddar's", "cheddars", "red robin", "buffalo wild wings",
    "hooters", "dave & buster", "dave and buster", "cheesecake factory",
    "p.f. chang", "pf chang", "bj's restaurant", "bjs restaurant",
    "carrabba", "benihana", "bonefish grill", "ruth's chris",
    "morton's steakhouse", "capital grille", "fleming's prime",
    "yard house", "the melting pot", "maggiano", "seasons 52",
    "bahama breeze", "noodles & company", "noodles and company",
    "bob's discount", "boston market", "wingstop",

    # Ice cream chains
    "dairy queen", "baskin-robbins", "baskin robbins", "cold stone creamery",
    "rita's italian ice", "ritas italian", "carvel", "friendly's", "friendlys",
    "marble slab", "maggie moo", "bruster's", "brusters",

    # Retail chains
    "walmart", "target", "costco", "sam's club", "sams club",
    "bj's wholesale", "dollar general", "dollar tree", "family dollar",
    "five below", "big lots", "tj maxx", "tjmaxx", "marshalls",
    "ross dress", "homegoods", "home goods", "kohl's", "kohls",
    "jcpenney", "jc penney", "macy's", "macys", "nordstrom",
    "burlington", "old navy", "gap", "banana republic",
    "bath & body works", "bath and body", "victoria's secret",
    "lululemon", "nike store", "adidas store", "foot locker",
    "finish line", "hot topic", "spencer's", "spencers",
    "forever 21", "h&m", "zara", "uniqlo", "primark",
    "best buy", "gamestop", "game stop", "staples", "office depot",
    "office max", "michael's craft", "michaels craft", "joann fabric",
    "hobby lobby", "ac moore", "pier 1", "world market",
    "bed bath & beyond", "bed bath and beyond", "williams-sonoma",
    "pottery barn", "crate & barrel", "crate and barrel",
    "restoration hardware", "ikea", "ashley furniture",
    "rooms to go", "la-z-boy", "lazy boy", "ethan allen",

    # Gas / Convenience
    "shell", "bp gas", "chevron", "exxonmobil", "exxon", "mobil gas",
    "texaco", "sunoco", "marathon gas", "speedway", "valero",
    "citgo", "cumberland farms", "wawa", "sheetz", "quiktrip",
    "racetrac", "casey's general", "caseys general", "love's travel",
    "loves travel", "pilot flying", "pilot travel", "flying j",
    "7-eleven", "7 eleven", "circle k", "royal farms",
    "kwik trip", "kwik star", "buc-ee", "bucees",

    # Pharmacy / Health
    "cvs pharmacy", "cvs health", "walgreens", "rite aid",
    "minute clinic", "urgent care", # careful with this one

    # Auto chains
    "autozone", "o'reilly auto", "oreilly auto", "advance auto",
    "napa auto", "jiffy lube", "midas", "meineke", "pep boys",
    "firestone complete", "goodyear auto", "valvoline instant",
    "take 5 oil", "maaco", "caliber collision", "safelite",
    "discount tire", "les schwab", "big o tires", "ntb ",
    "tire kingdom", "sullivan tire", "town fair tire",

    # Banks
    "chase bank", "bank of america", "wells fargo", "citibank",
    "us bank", "u.s. bank", "pnc bank", "td bank", "citizens bank",
    "capital one", "ally bank", "truist", "regions bank",
    "fifth third", "m&t bank", "mt bank", "huntington bank",
    "keybank", "key bank", "santander bank", "webster bank",
    "people's united", "peoples united", "eastern bank",
    "rockland trust", "berkshire bank",

    # Hotels
    "marriott", "hilton", "hyatt", "best western", "wyndham",
    "la quinta", "days inn", "super 8", "motel 6", "holiday inn",
    "hampton inn", "courtyard by", "fairfield inn", "springhill suites",
    "residence inn", "homewood suites", "embassy suites",
    "doubletree", "red roof inn", "extended stay", "comfort inn",
    "comfort suites", "quality inn", "sleep inn", "clarion hotel",
    "radisson", "sheraton", "westin", "four points", "aloft",
    "w hotel", "crowne plaza", "intercontinental",

    # Fitness chains
    "planet fitness", "anytime fitness", "la fitness",
    "gold's gym", "golds gym", "24 hour fitness",
    "orangetheory", "orange theory", "equinox",
    "crunch fitness", "f45 training", "snap fitness",
    "lifetime fitness", "life time fitness",
    "retro fitness", "esporta fitness", "blink fitness",
    "corepower yoga",

    # Beauty chains
    "great clips", "supercuts", "sport clips", "hair cuttery",
    "smartstyle", "cost cutters", "fantastic sams",
    "ulta beauty", "sephora", "sally beauty", "regis salon",
    "european wax center", "waxing the city", "drybar",
    "massage envy", "hand & stone", "hand and stone",
    "elements massage",

    # Pet chains
    "petsmart", "pet smart", "petco", "pet supplies plus",

    # Grocery
    "kroger", "safeway", "albertsons", "stop & shop", "stop and shop",
    "giant food", "giant eagle", "whole foods", "trader joe",
    "aldi", "lidl", "publix", "winn-dixie", "winn dixie",
    "sprouts farmers", "food lion", "hannaford", "market basket",
    "shaw's", "shaws", "price chopper", "shoprite", "shop rite",
    "wegmans", "h-e-b", "heb ", "piggly wiggly", "save-a-lot",
    "save a lot", "food city", "bi-lo", "bilo",

    # Home improvement
    "home depot", "lowe's", "lowes", "menards", "ace hardware",
    "true value", "harbor freight", "tractor supply",
    "sherwin-williams", "sherwin williams", "benjamin moore",

    # Telecom / Tech
    "verizon", "at&t", "t-mobile", "tmobile", "sprint",
    "comcast", "xfinity", "spectrum", "cox communication",

    # Shipping
    "usps", "ups store", "fedex", "dhl",

    # Car rental / dealers (large chains)
    "enterprise rent", "hertz", "avis", "budget rent",
    "national car rental",

    # Insurance chains
    "state farm", "allstate", "geico", "progressive",
    "liberty mutual", "farmers insurance", "nationwide",

    # Cleaning chains
    "servpro", "servicemaster", "stanley steemer",
    "chem-dry", "chemdry", "molly maid", "merry maids",
    "the maids",

    # Tax
    "h&r block", "hr block", "jackson hewitt", "liberty tax",

    # Misc franchises
    "subway", "quiznos", "which wich", "mcdonalds",
}

# Patterns that indicate a chain/franchise even if not in the list
CHAIN_PATTERNS = [
    re.compile(r"#\d{2,}", re.IGNORECASE),  # Store numbers like "#1234"
    re.compile(r"store\s*#?\d{2,}", re.IGNORECASE),
    re.compile(r"location\s*#?\d+", re.IGNORECASE),
    re.compile(r"unit\s*#?\d+", re.IGNORECASE),
]


def is_chain(business_name):
    """Check if a business name matches a known chain/franchise."""
    if not business_name:
        return False

    name_lower = business_name.lower().strip()

    for chain in CHAIN_NAMES:
        if chain in name_lower:
            return True

    for pattern in CHAIN_PATTERNS:
        if pattern.search(name_lower):
            return True

    return False


def filter_chains(leads, name_key="business_name"):
    """Remove chain businesses from a list of lead dicts.
    Returns (filtered_leads, removed_count)."""
    filtered = []
    removed = 0
    for lead in leads:
        name = lead.get(name_key, "")
        if is_chain(name):
            removed += 1
        else:
            filtered.append(lead)
    return filtered, removed
