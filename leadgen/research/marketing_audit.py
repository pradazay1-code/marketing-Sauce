"""Marketing-need audit.

Turns a business's web presence into a 0-100 score where **high means they need
marketing help**, plus the specific findings behind it and the pitch angles they
support.

This is deliberately inverted from a normal SEO grader. A perfect website scores
near 0 here -- it is a bad lead. A business with no site, no reviews and no
tracking scores near 100, because every gap is something One Vision can sell and
then visibly fix.

Every finding carries the evidence that produced it, so a voicemail or email can
name the specific problem instead of saying "I noticed some issues."
"""

import re
from datetime import datetime
from urllib.parse import urlparse

# Weight per signal. These sum to more than 100 on purpose -- the raw total is
# normalized at the end, so adding a signal later does not require rebalancing
# every other number.
WEIGHTS = {
    "no_website": 34,
    "no_ssl": 8,
    "not_mobile_friendly": 12,
    "no_meta_description": 5,
    "weak_title": 5,
    "no_schema": 4,
    "no_analytics": 7,
    "no_pixel": 5,
    "no_social": 8,
    "no_contact_form": 7,
    "no_phone_on_site": 6,
    "thin_content": 8,
    "stale_copyright": 6,
    "no_reviews": 9,
    "low_rating": 7,
    "no_gbp": 10,
    "no_booking": 5,
}

_SOCIAL = {
    "facebook": r"facebook\.com/(?!sharer|plugins)",
    "instagram": r"instagram\.com/",
    "linkedin": r"linkedin\.com/",
    "tiktok": r"tiktok\.com/",
    "youtube": r"youtube\.com/|youtu\.be/",
    "x": r"(?:twitter|x)\.com/",
}

_ANALYTICS = [
    r"googletagmanager\.com", r"google-analytics\.com", r"gtag\(",
    r"ga\('create'", r"plausible\.io", r"posthog", r"segment\.com",
    r"clarity\.ms", r"hotjar",
]

_PIXELS = [
    r"connect\.facebook\.net", r"fbq\(", r"snap\.licdn\.com",
    r"analytics\.tiktok\.com", r"ct\.pinterest\.com", r"bat\.bing\.com",
]

_BOOKING = [
    r"calendly\.com", r"acuityscheduling", r"squareup\.com/appointments",
    r"booksy", r"vagaro", r"setmore", r"schedulicity", r"housecallpro",
    r"jobber", r"servicetitan", r"book(ing)?[-_ ]?now",
]

_FORM_HINTS = [r"<form", r"type=[\"']email[\"']", r"contact[-_ ]?form",
               r"request[-_ ]?(a[-_ ])?quote", r"free[-_ ]?estimate"]


def _has(patterns, text):
    return any(re.search(p, text, re.I) for p in patterns)


def _finding(key, severity, title, detail, evidence="", pitch=""):
    return {
        "key": key,
        "severity": severity,          # critical | major | minor
        "points": WEIGHTS.get(key, 0),
        "title": title,
        "detail": detail,
        "evidence": evidence[:240],
        "pitch": pitch,
    }


def audit(lead, page=None):
    """Score one business.

    `lead` is the CRM row (dict). `page` is the Firecrawl scrape result for
    their site, or None when they have no site or the scrape failed.

    Returns a dict with score, grade, findings, pitch_angles and the raw signal
    map. Never raises -- a lead with nothing but a name still returns a usable
    result, because a missing signal is itself the finding.
    """
    findings = []
    signals = {}

    website = (lead.get("website_url") or "").strip()
    has_site = bool(website) and str(lead.get("has_website", "")).lower() not in ("0", "false", "no")

    html = ""
    markdown = ""
    meta = {}
    if page:
        html = page.get("html") or ""
        markdown = page.get("markdown") or ""
        meta = page.get("metadata") or {}
    blob = f"{html}\n{markdown}"

    # ---- the dominant signal -------------------------------------------
    if not has_site:
        findings.append(_finding(
            "no_website", "critical",
            "No website at all",
            "Nothing for search engines to rank and nowhere to send ad traffic. "
            "Every customer who looks them up finds a competitor instead.",
            pitch="A single-page site with a quote form is the fastest revenue "
                  "you can add to this business.",
        ))
        signals["has_website"] = False
    else:
        signals["has_website"] = True
        parsed = urlparse(website if "://" in website else f"https://{website}")
        signals["domain"] = parsed.netloc.lower().replace("www.", "")

        if parsed.scheme != "https":
            findings.append(_finding(
                "no_ssl", "major", "No HTTPS",
                "Browsers label the site 'Not secure', which visibly costs trust "
                "and is a confirmed ranking signal.",
                evidence=website,
                pitch="Free to fix, immediately visible. Good opener.",
            ))

        if page:
            # ---- mobile ------------------------------------------------
            if not re.search(r'name=[\'"]viewport[\'"]', html, re.I):
                findings.append(_finding(
                    "not_mobile_friendly", "critical",
                    "Not built for mobile",
                    "No viewport tag, so the site renders desktop-width on "
                    "phones. Most local searches are mobile.",
                    pitch="Show them their own site on your phone. Closes itself.",
                ))

            # ---- basic SEO ---------------------------------------------
            desc = (meta.get("description") or "").strip()
            if not desc:
                findings.append(_finding(
                    "no_meta_description", "minor",
                    "No meta description",
                    "Google writes its own snippet, so they have no control over "
                    "how the listing reads in results.",
                ))
            title = (meta.get("title") or "").strip()
            if not title or len(title) < 15:
                findings.append(_finding(
                    "weak_title", "major",
                    "Weak or missing page title",
                    "The title tag is the single strongest on-page ranking "
                    "factor and the headline of every search result.",
                    evidence=title or "(empty)",
                ))
            if not re.search(r'application/ld\+json|itemtype=', html, re.I):
                findings.append(_finding(
                    "no_schema", "minor",
                    "No schema markup",
                    "No LocalBusiness structured data, so no rich results and "
                    "weaker local relevance signals.",
                ))

            # ---- measurement -------------------------------------------
            if not _has(_ANALYTICS, blob):
                findings.append(_finding(
                    "no_analytics", "major",
                    "No analytics installed",
                    "They cannot see traffic, sources, or which pages convert. "
                    "Any spend so far has been unmeasured.",
                    pitch="'You're flying blind' is true and it lands.",
                ))
            if not _has(_PIXELS, blob):
                findings.append(_finding(
                    "no_pixel", "minor",
                    "No ad pixel",
                    "No Meta or Google pixel, so no retargeting and no "
                    "conversion tracking when ads do start.",
                ))

            # ---- conversion --------------------------------------------
            if not _has(_FORM_HINTS, html):
                findings.append(_finding(
                    "no_contact_form", "major",
                    "No contact or quote form",
                    "Visitors have no way to convert without picking up the "
                    "phone, which most will not do.",
                    pitch="A quote form is the highest-ROI single change here.",
                ))
            if not re.search(r'(\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}', blob):
                findings.append(_finding(
                    "no_phone_on_site", "major",
                    "No phone number visible",
                    "For a local service business the phone number is the "
                    "primary conversion path.",
                ))
            if not _has(_BOOKING, blob):
                findings.append(_finding(
                    "no_booking", "minor",
                    "No online booking",
                    "Every job has to be scheduled by hand over the phone.",
                ))

            # ---- content -----------------------------------------------
            words = len(re.findall(r"\w+", markdown))
            signals["word_count"] = words
            if words and words < 300:
                findings.append(_finding(
                    "thin_content", "major",
                    f"Thin content ({words} words)",
                    "Too little text to rank for anything beyond their own "
                    "business name.",
                    evidence=f"{words} words on the homepage",
                ))

            years = re.findall(r"(?:©|copyright|&copy;)\s*(\d{4})", blob, re.I)
            if years:
                newest = max(int(y) for y in years)
                signals["copyright_year"] = newest
                if newest < datetime.now().year - 1:
                    findings.append(_finding(
                        "stale_copyright", "minor",
                        f"Copyright still says {newest}",
                        "A visitor reads a stale footer as 'this business may "
                        "not be operating any more'.",
                        evidence=f"© {newest}",
                    ))

            # ---- social ------------------------------------------------
            found_social = [n for n, pat in _SOCIAL.items()
                            if re.search(pat, blob, re.I)]
            signals["social"] = found_social
            if not found_social:
                findings.append(_finding(
                    "no_social", "major",
                    "No social profiles linked",
                    "No Facebook or Instagram presence linked anywhere on the "
                    "site -- no organic reach, no social proof.",
                ))

    # ---- reputation (from CRM fields, not the page) ---------------------
    reviews = lead.get("review_count")
    rating = lead.get("review_rating")
    try:
        reviews = int(reviews) if reviews not in (None, "") else None
    except (TypeError, ValueError):
        reviews = None
    try:
        rating = float(rating) if rating not in (None, "") else None
    except (TypeError, ValueError):
        rating = None

    signals["review_count"] = reviews
    signals["review_rating"] = rating

    if reviews is not None and reviews < 10:
        findings.append(_finding(
            "no_reviews", "major",
            f"Only {reviews} review{'s' if reviews != 1 else ''}",
            "Below roughly ten reviews, a business loses the click to whoever "
            "has more, regardless of ranking.",
            pitch="An automated review request after every job fixes this in "
                  "weeks, and it is easy to demonstrate.",
        ))
    if rating is not None and rating < 4.0:
        findings.append(_finding(
            "low_rating", "major",
            f"Rating is {rating}",
            "Under 4.0 stars, ad spend actively loses money -- traffic arrives "
            "and bounces to a better-rated competitor.",
            pitch="Reputation before acquisition. Fix this first or nothing "
                  "else works.",
        ))
    if not lead.get("has_social_media") and not signals.get("social"):
        pass  # already captured by no_social

    if reviews is None and not has_site:
        findings.append(_finding(
            "no_gbp", "critical",
            "No Google Business Profile found",
            "Invisible in Maps and in the local pack, which is where local "
            "buying intent actually lands.",
            pitch="Free to claim, biggest single visibility win available.",
        ))

    # ---- score -----------------------------------------------------------
    #
    # Normalize against the signals that were actually *measurable*, not against
    # every signal in WEIGHTS. A business with no website cannot be assessed for
    # mobile-friendliness or analytics -- scoring those as "passed" would make
    # the single strongest buying signal in the system produce a mid-range
    # score, which is backwards.
    applicable = {"no_website": WEIGHTS["no_website"]}

    if has_site:
        applicable["no_ssl"] = WEIGHTS["no_ssl"]
        if page:
            for k in ("not_mobile_friendly", "no_meta_description", "weak_title",
                      "no_schema", "no_analytics", "no_pixel", "no_contact_form",
                      "no_phone_on_site", "no_booking", "no_social"):
                applicable[k] = WEIGHTS[k]
            if signals.get("word_count"):
                applicable["thin_content"] = WEIGHTS["thin_content"]
            if signals.get("copyright_year"):
                applicable["stale_copyright"] = WEIGHTS["stale_copyright"]

    if reviews is not None:
        applicable["no_reviews"] = WEIGHTS["no_reviews"]
    if rating is not None:
        applicable["low_rating"] = WEIGHTS["low_rating"]
    if reviews is None and not has_site:
        applicable["no_gbp"] = WEIGHTS["no_gbp"]

    raw = sum(f["points"] for f in findings)
    denom = sum(applicable.values()) or sum(WEIGHTS.values())
    score = int(round(min(raw / denom * 100, 100)))
    signals["signals_measured"] = len(applicable)

    if score >= 75:
        grade, label = "A", "Ideal prospect"
    elif score >= 55:
        grade, label = "B", "Strong prospect"
    elif score >= 35:
        grade, label = "C", "Worth a touch"
    elif score >= 18:
        grade, label = "D", "Low need"
    else:
        grade, label = "F", "Already well marketed"

    severity_rank = {"critical": 0, "major": 1, "minor": 2}
    findings.sort(key=lambda f: (severity_rank[f["severity"]], -f["points"]))

    return {
        "marketing_need_score": score,
        "grade": grade,
        "grade_label": label,
        "findings": findings,
        "signals": signals,
        "top_gaps": [f["title"] for f in findings[:3]],
        "pitch_angles": [f["pitch"] for f in findings if f.get("pitch")][:3],
        "audited_at": datetime.now().isoformat(),
    }


def one_line_pitch(result, business_name="this business"):
    """The single sentence to open a voicemail or email with."""
    if not result["findings"]:
        return f"{business_name} already has their marketing dialed in."
    top = result["findings"][0]
    return f"{business_name}: {top['title'].lower()} — {top['detail']}"
