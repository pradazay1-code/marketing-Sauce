"""DraftKings public endpoints client.

DraftKings' own web app calls these endpoints unauthenticated. We use the
same routes. Category and subcategory IDs change between seasons, so we
discover them dynamically by walking the eventgroup payload and matching
on human-readable labels.
"""

from __future__ import annotations

import time
from typing import Any, Iterable

import requests

BASE = "https://sportsbook-nash.draftkings.com/sites/US-SB/api/v5"

LEAGUE_IDS = {
    "nba": 42648,
    "mlb": 84240,
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
    "Accept-Language": "en-US,en;q=0.9",
    "Origin": "https://sportsbook.draftkings.com",
    "Referer": "https://sportsbook.draftkings.com/",
}


def _get(url: str, retries: int = 3, backoff: float = 1.5) -> dict[str, Any]:
    last_exc: Exception | None = None
    for attempt in range(retries):
        try:
            r = requests.get(url, headers=HEADERS, timeout=20)
            if r.status_code == 200:
                return r.json()
            if r.status_code in (429, 500, 502, 503, 504):
                time.sleep(backoff ** (attempt + 1))
                continue
            r.raise_for_status()
        except requests.RequestException as e:
            last_exc = e
            time.sleep(backoff ** (attempt + 1))
    if last_exc:
        raise last_exc
    raise RuntimeError(f"DK fetch failed: {url}")


def fetch_eventgroup(league: str) -> dict[str, Any]:
    league_id = LEAGUE_IDS[league]
    return _get(f"{BASE}/eventgroups/{league_id}?format=json")


def list_categories(eventgroup: dict[str, Any]) -> list[dict[str, Any]]:
    eg = eventgroup.get("eventGroup", {})
    return eg.get("offerCategories", []) or []


def find_category_id(eventgroup: dict[str, Any], names: Iterable[str]) -> int | None:
    wanted = {n.lower() for n in names}
    for cat in list_categories(eventgroup):
        if (cat.get("name") or "").lower() in wanted:
            return cat.get("offerCategoryId")
    return None


def fetch_category(league: str, category_id: int) -> dict[str, Any]:
    league_id = LEAGUE_IDS[league]
    return _get(
        f"{BASE}/eventgroups/{league_id}/categories/{category_id}?format=json"
    )


def list_events(eventgroup: dict[str, Any]) -> list[dict[str, Any]]:
    return eventgroup.get("eventGroup", {}).get("events", []) or []


def iter_offers(category_payload: dict[str, Any]) -> Iterable[tuple[dict, dict, dict]]:
    """Yield (subcategory, offer_group, offer) triples from a category payload."""
    eg = category_payload.get("eventGroup", {})
    for cat in eg.get("offerCategories", []) or []:
        for sub_desc in cat.get("offerSubcategoryDescriptors", []) or []:
            sub = sub_desc.get("offerSubcategory") or {}
            for offer_group in sub.get("offers", []) or []:
                # offer_group is a list of offers (one per event usually)
                for offer in offer_group:
                    yield sub_desc, sub, offer


def american_to_prob(odds: int | float | None) -> float | None:
    if odds is None:
        return None
    odds = float(odds)
    if odds >= 100:
        return 100.0 / (odds + 100.0)
    return -odds / (-odds + 100.0)
