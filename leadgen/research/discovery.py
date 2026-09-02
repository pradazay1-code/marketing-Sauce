"""Multi-source discovery with consensus.

This is the deliberate, slow path. Instead of taking the first search result and
calling it a lead, a run:

  1. queries every configured source, across several search terms per industry
  2. clusters the results into one record per real business
  3. scores each by how many independent sources corroborate it
  4. keeps only records above a confidence floor
  5. deduplicates against the entire CRM before writing

It is paced on purpose -- a small delay between calls keeps free tiers from
rate-limiting, and the point of the run is quality, not speed.

Because serverless functions are capped at 60 seconds, a thorough run is
resumable: `plan_run` produces the list of (source, term) steps, and each
`run_step` call executes one. The pooled candidates live in the database
between invocations.
"""

import json
import time
from datetime import datetime

from . import industries as ind
from .consensus import build_consensus, to_lead
from .dedupe import dedupe_batch
from .sources import providers          # noqa: F401 -- registers the sources
from .sources.base import Candidate, get_sources, all_status

# Confidence floors. "Balanced" is the default: it admits a business two decent
# sources agree on, and rejects one that only a single web search saw.
THRESHOLDS = {
    "wide":     25,   # maximum volume, expect noise
    "balanced": 45,   # default
    "strict":   65,   # only well-corroborated businesses
}

PACE_SECONDS = float(0.4)


def source_status():
    return all_status()


def configured_source_names():
    return [s.name for s in get_sources()]


def plan_run(industry_key, city, state, terms_per_industry=3, sources=None):
    """The (source, term) steps a thorough run will execute."""
    terms = ind.search_terms(industry_key) or [industry_key.replace("_", " ")]
    terms = terms[:max(1, terms_per_industry)]
    srcs = [s.name for s in get_sources(only=sources)]
    return [{"source": s, "term": t, "city": city, "state": state}
            for s in srcs for t in terms]


def run_step(step, limit=20):
    """Execute one (source, term) pair. Returns serializable candidates."""
    srcs = {s.name: s for s in get_sources(only=[step["source"]])}
    src = srcs.get(step["source"])
    if not src:
        return []
    found = src.search(step["term"], step["city"], step["state"], limit=limit)
    time.sleep(PACE_SECONDS)
    return [c.to_dict() | {"source": c.source} for c in found]


def discover(industry_key, city, state, limit=20, mode="balanced",
             terms_per_industry=3, sources=None, save=True,
             min_sources=1, progress=None):
    """Run the full thorough pipeline in one call.

    Suitable for a long-lived server or a CLI. On serverless, drive the same
    work through plan_run/run_step/finalize instead.
    """
    from database import add_lead, all_lead_dedupe_fields

    threshold = THRESHOLDS.get(mode, THRESHOLDS["balanced"])
    steps = plan_run(industry_key, city, state, terms_per_industry, sources)
    if not steps:
        return {"ok": False,
                "error": "No sources configured. Add at least one API key.",
                "added": 0, "sources_used": []}

    pooled, per_source = [], {}
    for i, step in enumerate(steps, 1):
        if progress:
            progress(f"[{i}/{len(steps)}] {step['source']}: {step['term']}")
        raw = run_step(step, limit=limit)
        per_source[step["source"]] = per_source.get(step["source"], 0) + len(raw)
        pooled.extend(_rehydrate(raw))

    return finalize(pooled, industry_key, city, state, threshold,
                    per_source, save=save, min_sources=min_sources)


def finalize(candidates, industry_key, city, state, threshold,
             per_source=None, save=True, min_sources=1):
    """Cluster, score, dedupe, and optionally write the surviving leads."""
    from database import add_lead, all_lead_dedupe_fields

    trust_map = {s.name: s.trust for s in get_sources(configured_only=False)}
    accepted, rejected = build_consensus(candidates, trust_map, threshold)

    if min_sources > 1:
        held = [a for a in accepted if a["source_count"] < min_sources]
        accepted = [a for a in accepted if a["source_count"] >= min_sources]
        for h in held:
            h["reject_reason"] = (
                f"only {h['source_count']} source, {min_sources} required")
        rejected.extend(held)

    label = ind.industry_label(industry_key)
    leads = [to_lead(a, industry_key, label) for a in accepted]

    unique, dupes = dedupe_batch(leads, all_lead_dedupe_fields() if save else [])

    added = 0
    if save:
        for lead in unique:
            try:
                if add_lead(lead):
                    added += 1
            except Exception as e:                       # noqa: BLE001
                print(f"[Discover] add_lead failed for "
                      f"{lead.get('business_name')}: {str(e)[:120]}")

    return {
        "ok": True,
        "error": "",
        "industry": industry_key,
        "industry_label": label,
        "location": f"{city}, {state}",
        "raw_candidates": len(candidates),
        "per_source": per_source or {},
        "clustered": len(accepted) + len(rejected),
        "accepted": len(accepted),
        "rejected_low_confidence": len(rejected),
        "duplicates": [{"name": d[0]["business_name"], "reason": d[1]}
                       for d in dupes],
        "duplicate_count": len(dupes),
        "added": added,
        "sources_used": sorted(per_source.keys()) if per_source else [],
        "threshold": threshold,
        "preview": [
            {
                "business_name": a["business_name"],
                "phone": a["phone"],
                "website": a["website"],
                "city": a["city"],
                "confidence": a["confidence"],
                "source_count": a["source_count"],
                "sources": a["sources"],
                "conflicts": a["conflicts"],
                "has_website": bool(a["website"]),
            }
            for a in accepted[:40]
        ],
        "rejected_preview": [
            {"business_name": r.get("business_name", "(no name)"),
             "confidence": r["confidence"],
             "sources": r["sources"],
             "reason": r.get("reject_reason", "")}
            for r in rejected[:25]
        ],
        "finished_at": datetime.now().isoformat(),
    }


def _rehydrate(rows):
    """dicts -> Candidates, ignoring keys the dataclass does not define."""
    out = []
    allowed = set(Candidate.__dataclass_fields__.keys())
    for r in rows:
        out.append(Candidate(**{k: v for k, v in r.items() if k in allowed}))
    return out


# ---------------------------------------------------------------------------
# Serverless: pool candidates in the DB across invocations
# ---------------------------------------------------------------------------

def pool_key(industry_key, city, state):
    return f"discover::{industry_key}::{city}::{state}".lower()


def pool_append(key, rows):
    """Append this step's candidates to the run's pool.

    Reuses saved_searches as durable scratch space rather than adding a table
    for something that lives for the length of one run.
    """
    from database import get_db
    conn = get_db()
    cur = conn.execute("SELECT id, filters FROM saved_searches WHERE name = ?",
                       (key,))
    row = cur.fetchone()
    if row:
        d = dict(row)
        try:
            existing = json.loads(d["filters"])
        except (ValueError, TypeError):
            existing = []
        existing.extend(rows)
        conn.execute("UPDATE saved_searches SET filters = ? WHERE id = ?",
                     (json.dumps(existing)[:4_000_000], d["id"]))
    else:
        conn.execute("INSERT INTO saved_searches (name, filters) VALUES (?, ?)",
                     (key, json.dumps(rows)))
    conn.commit()
    conn.close()


def pool_read(key):
    from database import get_db
    conn = get_db()
    cur = conn.execute("SELECT filters FROM saved_searches WHERE name = ?", (key,))
    row = cur.fetchone()
    conn.close()
    if not row:
        return []
    try:
        return _rehydrate(json.loads(dict(row)["filters"]))
    except (ValueError, TypeError):
        return []


def pool_clear(key):
    from database import get_db
    conn = get_db()
    conn.execute("DELETE FROM saved_searches WHERE name = ?", (key,))
    conn.commit()
    conn.close()
