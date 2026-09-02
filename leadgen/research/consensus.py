"""Cross-source consensus.

Running six sources against one query returns the same businesses many times,
with conflicting phone numbers, half-missing websites, and a long tail of things
that are not businesses at all. This module turns that into one record per real
business, each carrying a confidence score you can filter on.

Three stages:

  1. CLUSTER   group candidates that refer to the same business
  2. MERGE     resolve each field by weighted vote across the cluster
  3. SCORE     confidence from corroboration, agreement, and completeness

The point is that a business found by four independent sources that agree on its
phone number is a materially better lead than one found once by a web search --
and only a consensus pass can tell you which is which.
"""

import re
from collections import defaultdict
from difflib import SequenceMatcher

# Similarity above which two normalized names in the same city are treated as
# the same business. 0.88 merges "joesjunkremoval" / "joejunkremoval" (one
# character apart) while keeping "joeslandscaping" / "joesplumbing" separate.
NAME_SIMILARITY = 0.88

from .sources.base import Candidate, norm_phone, norm_website


def _name_key(name, city=""):
    """Bare alphanumerics plus locality.

    Matches the dedupe module's normalization so clustering and duplicate
    detection agree: corporate suffixes and word boundaries are exactly what
    differ between sources for the same business.
    """
    if not name:
        return ""
    n = name.lower()
    n = re.sub(r"[^a-z0-9\s]", " ", n)
    n = re.sub(r"\b(llc|inc|corp|co|ltd|the|and|of|services?|company)\b", " ", n)
    n = re.sub(r"[^a-z0-9]", "", n)
    loc = re.sub(r"[^a-z0-9]", "", (city or "").lower())
    return f"{n}|{loc}" if n else ""


def _domain(url):
    if not url:
        return ""
    u = url.split("://")[-1].split("/")[0].lower().replace("www.", "")
    return u if "." in u else ""


def cluster(candidates):
    """Group candidates that describe the same business.

    Union-find over three linking keys -- phone, domain, name+city. Two records
    join the same cluster if they share any one of them, which chains correctly:
    A and B share a phone, B and C share a domain, so all three are one business.
    """
    parent = list(range(len(candidates)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    by_key = defaultdict(list)
    for i, c in enumerate(candidates):
        if c.phone:
            by_key[("p", c.phone)].append(i)
        d = _domain(c.website)
        if d:
            by_key[("d", d)].append(i)
        nk = _name_key(c.business_name, c.city)
        if nk:
            by_key[("n", nk)].append(i)

    for idxs in by_key.values():
        for j in idxs[1:]:
            union(idxs[0], j)

    # Fuzzy pass. Exact keys miss the common case where one source spells the
    # business slightly differently AND reports a different phone -- "Joe's Junk
    # Removal" vs "Joe Junk Removal Co". Without this they survive as two leads,
    # which is the repeat-contact problem the whole system exists to avoid.
    #
    # Bucketed by locality so this stays cheap and cannot merge same-named
    # businesses in different towns.
    buckets = defaultdict(list)
    for i, c in enumerate(candidates):
        nk = _name_key(c.business_name, c.city)
        if nk:
            name_part, _, loc = nk.partition("|")
            buckets[loc].append((i, name_part))

    for entries in buckets.values():
        for a in range(len(entries)):
            ia, na = entries[a]
            for b in range(a + 1, len(entries)):
                ib, nb = entries[b]
                if find(ia) == find(ib):
                    continue
                # Length gate first -- SequenceMatcher is the expensive part.
                if abs(len(na) - len(nb)) > 4:
                    continue
                if SequenceMatcher(None, na, nb).ratio() >= NAME_SIMILARITY:
                    union(ia, ib)

    groups = defaultdict(list)
    for i, c in enumerate(candidates):
        groups[find(i)].append(c)
    return list(groups.values())


def _vote(values_with_weight):
    """Weighted majority vote. Returns (winner, agreement 0-1, distinct count).

    Agreement is the winner's share of total weight, so a field two sources
    contradict scores lower than one they both confirm.
    """
    tally = defaultdict(float)
    for val, w in values_with_weight:
        if val not in (None, "", 0):
            tally[val] += w
    if not tally:
        return None, 0.0, 0
    total = sum(tally.values())
    winner = max(tally, key=tally.get)
    return winner, tally[winner] / total, len(tally)


def merge_cluster(cluster_items, trust_map):
    """Collapse one cluster into a single record plus a confidence report."""
    sources = sorted({c.source for c in cluster_items})
    weights = [(c, trust_map.get(c.source, 0.5)) for c in cluster_items]

    def vote(attr):
        return _vote([(getattr(c, attr), w) for c, w in weights])

    name, name_agree, _ = vote("business_name")
    phone, phone_agree, phone_variants = vote("phone")
    website, site_agree, _ = vote("website")
    address, _, _ = vote("address")
    city, _, _ = vote("city")
    state, _, _ = vote("state")
    zip_code, _, _ = vote("zip_code")
    category, _, _ = vote("category")

    # Reviews: take the highest count seen and the rating that came with it.
    # Sources sample at different times, and the larger count is the fresher one.
    best_reviews, best_rating = None, None
    for c, _w in weights:
        if c.review_count is not None:
            if best_reviews is None or c.review_count > best_reviews:
                best_reviews = c.review_count
                best_rating = c.review_rating
    if best_rating is None:
        best_rating, _, _ = vote("review_rating")

    lat, _, _ = vote("latitude")
    lng, _, _ = vote("longitude")

    # ---- confidence -----------------------------------------------------
    #
    # Corroboration dominates. One source finding a business proves it appears
    # somewhere; four independent sources finding it proves it exists and is
    # trading. Trust-weighted so a Google Places hit counts more than a blog.
    trust_sum = sum(trust_map.get(s, 0.5) for s in sources)
    corroboration = min(trust_sum / 2.5, 1.0)

    filled = sum(1 for v in (name, phone, website, address, city) if v)
    completeness = filled / 5.0

    agreements = [a for a in (name_agree, phone_agree, site_agree) if a]
    agreement = sum(agreements) / len(agreements) if agreements else 0.0

    confidence = int(round(
        (corroboration * 0.50 + completeness * 0.25 + agreement * 0.25) * 100))

    conflicts = []
    if phone_variants > 1:
        conflicts.append(f"{phone_variants} different phone numbers reported")
    if name_agree < 0.6 and len(cluster_items) > 1:
        conflicts.append("sources disagree on the business name")

    return {
        "business_name": name or "",
        "phone": phone or "",
        "website": website or "",
        "address": address or "",
        "city": city or "",
        "state": state or "",
        "zip_code": zip_code or "",
        "latitude": lat,
        "longitude": lng,
        "category": category or "",
        "review_count": best_reviews,
        "review_rating": best_rating,
        "sources": sources,
        "source_count": len(sources),
        "confidence": confidence,
        "corroboration": round(corroboration, 2),
        "completeness": round(completeness, 2),
        "agreement": round(agreement, 2),
        "conflicts": conflicts,
    }


def build_consensus(candidates, trust_map, min_confidence=0):
    """Full pipeline: cluster, merge, score, sort.

    Returns (accepted, rejected). Rejected records keep their score and reason
    so a run can explain what it threw away -- "found 60, kept 12" is only
    trustworthy if the other 48 are inspectable.
    """
    if not candidates:
        return [], []

    merged = [merge_cluster(g, trust_map) for g in cluster(candidates)]
    merged.sort(key=lambda m: (-m["confidence"], -m["source_count"]))

    accepted, rejected = [], []
    for m in merged:
        if m["confidence"] < min_confidence:
            m["reject_reason"] = (
                f"confidence {m['confidence']} below threshold {min_confidence} "
                f"({m['source_count']} source"
                f"{'s' if m['source_count'] != 1 else ''})")
            rejected.append(m)
        elif not m["business_name"]:
            m["reject_reason"] = "no business name"
            rejected.append(m)
        else:
            accepted.append(m)
    return accepted, rejected


def to_lead(record, industry_key, industry_label, source_label=""):
    """Shape a consensus record into a CRM lead row."""
    has_site = 1 if record.get("website") else 0
    return {
        "business_name": record["business_name"],
        "phone": record.get("phone", ""),
        "website_url": record.get("website", ""),
        "has_website": has_site,
        "address": record.get("address", ""),
        "city": record.get("city", ""),
        "state": record.get("state", ""),
        "zip_code": record.get("zip_code", ""),
        "latitude": record.get("latitude"),
        "longitude": record.get("longitude"),
        "industry": industry_key,
        "category": industry_label,
        "business_type": industry_label,
        "review_count": record.get("review_count"),
        "review_rating": record.get("review_rating"),
        "icp_score": record.get("confidence", 0),
        "source": source_label or "Consensus: " + ", ".join(record["sources"]),
        "status": "new",
        "priority": "high" if not has_site else "medium",
        "notes": _note(record),
    }


def _note(record):
    bits = [
        f"Found by {record['source_count']} source"
        f"{'s' if record['source_count'] != 1 else ''}: "
        f"{', '.join(record['sources'])}",
        f"Confidence {record['confidence']}/100 "
        f"(corroboration {record['corroboration']}, "
        f"completeness {record['completeness']}, "
        f"agreement {record['agreement']})",
    ]
    if record.get("conflicts"):
        bits.append("Conflicts: " + "; ".join(record["conflicts"]))
    return " | ".join(bits)[:900]
