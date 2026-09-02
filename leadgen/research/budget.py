"""Credit budget guard and ledger.

Firecrawl credits are finite and easy to burn through by accident -- one
enthusiastic batch run can spend a month's allowance in ninety seconds. Nothing
in this codebase may call a paid API without going through here.

Three protections:

  1. LEDGER      every spend is recorded with what it bought
  2. CAP         a hard monthly ceiling, checked before each call
  3. ESTIMATE    a run reports its cost before it starts, and refuses to
                 begin if it cannot afford to finish

Plus a cache, which is the only one that actually *saves* credits rather than
merely limiting them: the same URL is never paid for twice.

Set FIRECRAWL_CREDIT_BUDGET to your remaining balance. It defaults low on
purpose -- an unconfigured budget should be conservative, not unlimited.
"""

import hashlib
import json
import os
from datetime import datetime, timedelta

DEFAULT_BUDGET = 50
CACHE_TTL_DAYS = 30


def monthly_budget():
    try:
        return int(os.getenv("FIRECRAWL_CREDIT_BUDGET", DEFAULT_BUDGET))
    except (TypeError, ValueError):
        return DEFAULT_BUDGET


def record(feature, credits=1, detail="", provider="firecrawl"):
    """Log a spend. Call this *after* a paid call succeeds."""
    from database import get_db
    conn = get_db()
    conn.execute(
        """INSERT INTO credit_ledger (provider, feature, credits, detail, spent_at)
           VALUES (?, ?, ?, ?, ?)""",
        (provider, feature, int(credits), (detail or "")[:300],
         datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()


def spent_this_month(provider="firecrawl"):
    from database import get_db
    start = datetime.now().replace(day=1, hour=0, minute=0, second=0,
                                   microsecond=0).isoformat()
    conn = get_db()
    cur = conn.execute(
        "SELECT COALESCE(SUM(credits), 0) FROM credit_ledger "
        "WHERE provider = ? AND spent_at >= ?", (provider, start))
    row = cur.fetchone()
    conn.close()
    return int((row[0] if not isinstance(row, dict) else list(row.values())[0]) or 0)


def remaining(provider="firecrawl"):
    return max(monthly_budget() - spent_this_month(provider), 0)


def status(provider="firecrawl"):
    spent = spent_this_month(provider)
    budget = monthly_budget()
    return {
        "provider": provider,
        "budget": budget,
        "spent": spent,
        "remaining": max(budget - spent, 0),
        "pct_used": round(spent / budget * 100, 1) if budget else 0,
        "env": "FIRECRAWL_CREDIT_BUDGET",
    }


def can_afford(credits, provider="firecrawl"):
    """(ok, message). Check before spending, not after."""
    left = remaining(provider)
    if credits <= left:
        return True, ""
    return False, (
        f"Would cost {credits} credits but only {left} remain this month "
        f"(budget {monthly_budget()}). Raise FIRECRAWL_CREDIT_BUDGET or narrow "
        f"the run.")


def recent(limit=40, provider=None):
    from database import get_db
    conn = get_db()
    if provider:
        cur = conn.execute(
            "SELECT * FROM credit_ledger WHERE provider = ? "
            "ORDER BY spent_at DESC LIMIT ?", (provider, limit))
    else:
        cur = conn.execute(
            "SELECT * FROM credit_ledger ORDER BY spent_at DESC LIMIT ?", (limit,))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def by_feature(provider="firecrawl"):
    """Where the credits actually went, so waste is visible."""
    from database import get_db
    start = datetime.now().replace(day=1, hour=0, minute=0, second=0,
                                   microsecond=0).isoformat()
    conn = get_db()
    cur = conn.execute(
        """SELECT feature, SUM(credits) AS c, COUNT(*) AS n
             FROM credit_ledger WHERE provider = ? AND spent_at >= ?
            GROUP BY feature ORDER BY c DESC""", (provider, start))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return [{"feature": r["feature"], "credits": int(r["c"]),
             "calls": int(r["n"])} for r in rows]


# ---------------------------------------------------------------------------
# Cache -- the only thing here that saves credits rather than rationing them
# ---------------------------------------------------------------------------

def _key(url, kind="scrape"):
    return hashlib.sha256(f"{kind}::{url}".encode()).hexdigest()[:40]


def cache_get(url, kind="scrape", ttl_days=CACHE_TTL_DAYS):
    """Return a cached payload, or None. A hit costs nothing."""
    from database import get_db
    cutoff = (datetime.now() - timedelta(days=ttl_days)).isoformat()
    conn = get_db()
    cur = conn.execute(
        "SELECT payload, fetched_at FROM scrape_cache "
        "WHERE cache_key = ? AND fetched_at >= ?", (_key(url, kind), cutoff))
    row = cur.fetchone()
    conn.close()
    if not row:
        return None
    try:
        return json.loads(dict(row)["payload"])
    except (ValueError, TypeError):
        return None


def cache_put(url, payload, kind="scrape"):
    from database import get_db
    conn = get_db()
    key = _key(url, kind)
    blob = json.dumps(payload)[:2_000_000]
    now = datetime.now().isoformat()
    conn.execute("DELETE FROM scrape_cache WHERE cache_key = ?", (key,))
    conn.execute(
        """INSERT INTO scrape_cache (cache_key, url, kind, payload, fetched_at)
           VALUES (?, ?, ?, ?, ?)""", (key, url[:500], kind, blob, now))
    conn.commit()
    conn.close()


def cache_stats():
    from database import get_db
    conn = get_db()
    cur = conn.execute("SELECT COUNT(*) AS n FROM scrape_cache")
    row = cur.fetchone()
    conn.close()
    n = int(dict(row)["n"] if isinstance(row, dict) else row[0])
    return {"entries": n, "credits_saved_estimate": n}


def clear_cache():
    from database import get_db
    conn = get_db()
    conn.execute("DELETE FROM scrape_cache")
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------

def guarded_scrape(url, feature, formats=None, force=False):
    """The only sanctioned way to spend a Firecrawl scrape credit.

    Cache first, then budget check, then the paid call. Returns the usual
    Firecrawl page dict plus `from_cache` and `credits_spent`.
    """
    from research import firecrawl_client as fc

    if not force:
        hit = cache_get(url, "scrape")
        if hit:
            hit["from_cache"] = True
            hit["credits_spent"] = 0
            return hit

    ok, msg = can_afford(1)
    if not ok:
        return {"ok": False, "error": msg, "url": url,
                "from_cache": False, "credits_spent": 0, "budget_blocked": True}

    page = fc.scrape(url, formats=formats)
    if page.get("ok"):
        record(feature, 1, detail=url)
        page["credits_spent"] = 1
        cache_put(url, page, "scrape")
    else:
        # A failed scrape may still have consumed a credit upstream, but we
        # cannot know -- err toward not over-counting the user's balance.
        page["credits_spent"] = 0
    page["from_cache"] = False
    return page
