"""Pinnacle public 'arcadia' API client.

Pinnacle exposes guest endpoints used by their own web app. They're globally
accessible (no US geofence like DK) and publish player props for both NBA and
MLB. Lines from Pinnacle are sharper than retail books, so they're a good
ground truth for the model and a solid fallback when DK is unavailable.

We pull two endpoints per league:
  - /leagues/{id}/matchups           list of games + special (player prop) markets
  - /leagues/{id}/markets/straight   odds for each matchup

Player props live in matchups with `type=special`; the `units` field
describes the stat (Points, Rebounds, 3 Point FG, Hits, Strikeouts, ...) and
the parent matchup is the underlying game.
"""

from __future__ import annotations

import datetime as dt
import json
import pathlib
import sys
import time
from typing import Any

import requests

BASE = "https://guest.api.arcadia.pinnacle.com/0.1"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
    "Referer": "https://www.pinnacle.com/",
    "Origin": "https://www.pinnacle.com",
    "X-API-Key": "CmX2KcMrXuFmNg6YFbmTxE0y9CIrOi0R",
}

LEAGUE_IDS = {"nba": 487, "mlb": 246}

# Map Pinnacle "units" string -> our market key.
UNITS_TO_MARKET = {
    "(Points)": "player_points",
    "Points": "player_points",
    "Total Points": "player_points",
    "(Rebounds)": "player_rebounds",
    "Rebounds": "player_rebounds",
    "Total Rebounds": "player_rebounds",
    "3 Point FG": "player_threes",
    "3 Point Field Goals": "player_threes",
    "(3 Point FG)": "player_threes",
    "Hits": "player_hits",
    "(Hits)": "player_hits",
    "Strikeouts": "pitcher_strikeouts",
    "(Strikeouts)": "pitcher_strikeouts",
}


def _get(url: str, retries: int = 3) -> Any:
    backoff = 1.5
    for attempt in range(retries):
        try:
            r = requests.get(url, headers=HEADERS, timeout=20)
            if r.status_code == 200:
                return r.json()
            if r.status_code in (429, 502, 503, 504):
                time.sleep(backoff); backoff *= 2; continue
            r.raise_for_status()
        except requests.RequestException:
            time.sleep(backoff); backoff *= 2
    raise RuntimeError(f"pinnacle fetch failed: {url}")


def fetch_matchups(league: str) -> list[dict]:
    league_id = LEAGUE_IDS[league]
    return _get(f"{BASE}/leagues/{league_id}/matchups") or []


def fetch_markets(league: str) -> list[dict]:
    league_id = LEAGUE_IDS[league]
    return _get(f"{BASE}/leagues/{league_id}/markets/straight") or []


def decimal_to_american(decimal_odds: float | None) -> int | None:
    if decimal_odds is None:
        return None
    d = float(decimal_odds)
    if d <= 1.0:
        return None
    if d >= 2.0:
        return int(round((d - 1.0) * 100))
    return int(round(-100.0 / (d - 1.0)))


def implied_prob(decimal_odds: float | None) -> float | None:
    if decimal_odds is None or decimal_odds <= 0:
        return None
    return 1.0 / float(decimal_odds)


def build_props(league: str) -> list[dict]:
    """Return a normalized list of prop offers compatible with our DK schema."""
    matchups = fetch_matchups(league)
    markets = fetch_markets(league)

    by_id: dict[int, dict] = {m["id"]: m for m in matchups if "id" in m}
    markets_by_matchup: dict[int, list[dict]] = {}
    for m in markets:
        mid = m.get("matchupId")
        if mid:
            markets_by_matchup.setdefault(mid, []).append(m)

    captured = dt.datetime.utcnow().isoformat(timespec="seconds") + "Z"
    out: list[dict] = []

    for mu in matchups:
        mu_type = mu.get("type")
        units = (mu.get("units") or "").strip()
        market_key = UNITS_TO_MARKET.get(units)
        parent = (mu.get("parent") or {}).get("id")

        # Player prop (special) lookup
        if mu_type == "special" and market_key:
            game = by_id.get(parent) if parent else None
            event_name = None
            start_time = None
            if game:
                parts = game.get("participants") or []
                names = [p.get("name") for p in parts if p.get("name")]
                if len(names) >= 2:
                    event_name = f"{names[0]} @ {names[1]}"
                start_time = game.get("startTime")

            # Player name comes from the special's own description / participants
            participants = mu.get("participants") or []
            # Some specials have a single subject (the player) with two outcomes (Over/Under)
            player = mu.get("description") or (participants[0].get("name") if participants else None)
            # Find over/under prices in markets attached to this special's matchup id
            mkts = markets_by_matchup.get(mu["id"], [])
            line = None
            over_dec = None
            under_dec = None
            for mk in mkts:
                if mk.get("type") not in ("total", "moneyline"):
                    continue
                for price in mk.get("prices") or []:
                    desig = (price.get("designation") or "").lower()
                    if desig == "over":
                        line = price.get("points") or line
                        over_dec = price.get("price")
                    elif desig == "under":
                        line = price.get("points") or line
                        under_dec = price.get("price")
            if not (player and line is not None and over_dec and under_dec):
                continue
            out.append({
                "market": market_key,
                "player": player,
                "event_id": parent,
                "event_name": event_name,
                "start_time": start_time,
                "line": float(line),
                "over_odds": decimal_to_american(over_dec),
                "under_odds": decimal_to_american(under_dec),
                "over_prob": implied_prob(over_dec),
                "under_prob": implied_prob(under_dec),
                "captured_at": captured,
                "book": "pinnacle",
            })

        # Game lines: moneyline (MLB) and totals (game_total)
        # Filter to FULL-GAME markets only — Pinnacle returns alt lines, partial-
        # game (1H, 1Q, etc.), and special markets in the same response. Their
        # `key` encoding is "s;<period>;<type>;<param>"; period=0 is full game.
        if mu_type == "matchup" and league in ("nba", "mlb"):
            mkts = markets_by_matchup.get(mu["id"], [])
            parts = mu.get("participants") or []
            names = [p.get("name") for p in parts if p.get("name")]
            event_name = f"{names[0]} @ {names[1]}" if len(names) >= 2 else None

            for mk in mkts:
                key = mk.get("key") or ""
                if not key.startswith("s;0;"):
                    continue  # skip alt periods / partial-game lines

                if mk.get("type") == "moneyline" and league == "mlb":
                    prices = mk.get("prices") or []
                    if len(prices) != 2:
                        continue
                    a, b = prices[0], prices[1]
                    a_dec = a.get("price"); b_dec = b.get("price")
                    # Sanity: ignore obviously stale / novelty lines
                    if not (1.05 < float(a_dec or 0) < 50 and 1.05 < float(b_dec or 0) < 50):
                        continue
                    out.append({
                        "market": "moneyline",
                        "event_id": mu["id"],
                        "event_name": event_name,
                        "start_time": mu.get("startTime"),
                        "team_a": next((p.get("name") for p in parts if (p.get("alignment") or "").lower() == (a.get("designation") or "").lower()), names[0] if names else None),
                        "team_a_odds": decimal_to_american(a_dec),
                        "team_a_prob": implied_prob(a_dec),
                        "team_b": next((p.get("name") for p in parts if (p.get("alignment") or "").lower() == (b.get("designation") or "").lower()), names[1] if len(names) > 1 else None),
                        "team_b_odds": decimal_to_american(b_dec),
                        "team_b_prob": implied_prob(b_dec),
                        "captured_at": captured,
                        "book": "pinnacle",
                    })
                if mk.get("type") == "total" and league == "nba":
                    over = next((p for p in (mk.get("prices") or []) if (p.get("designation") or "").lower() == "over"), None)
                    under = next((p for p in (mk.get("prices") or []) if (p.get("designation") or "").lower() == "under"), None)
                    if not (over and under):
                        continue
                    line = over.get("points") or under.get("points")
                    o_dec = over.get("price"); u_dec = under.get("price")
                    if line is None or not (1.5 < float(o_dec or 0) < 3.0 and 1.5 < float(u_dec or 0) < 3.0):
                        continue
                    out.append({
                        "market": "game_total",
                        "event_id": mu["id"],
                        "event_name": event_name,
                        "start_time": mu.get("startTime"),
                        "line": float(line),
                        "over_odds": decimal_to_american(o_dec),
                        "under_odds": decimal_to_american(u_dec),
                        "over_prob": implied_prob(o_dec),
                        "under_prob": implied_prob(u_dec),
                        "captured_at": captured,
                        "book": "pinnacle",
                    })

    return out


if __name__ == "__main__":
    league = sys.argv[1] if len(sys.argv) > 1 else "nba"
    rows = build_props(league)
    print(f"pinnacle {league}: {len(rows)} offers")
    print(json.dumps(rows[:3], indent=2))
