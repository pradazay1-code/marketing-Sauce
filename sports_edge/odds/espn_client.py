"""ESPN public scoreboard / odds client.

ESPN exposes free, unauthenticated endpoints that return today's games for
every league, including the consensus line (spread + total + moneyline) when
sportsbooks have posted it. ESPN does NOT publish player props, so this is
strictly a backup for game-lines and a source-of-truth for game schedule /
final scores. Used to populate the "Live Lines" tab and as a last-ditch
fallback when both DK and Pinnacle fail.

ESPN's APIs are accessible from any cloud IP — no geofence, no auth.
"""

from __future__ import annotations

import datetime as dt
import time
from typing import Any

import requests

BASES = {
    "nba": "https://site.api.espn.com/apis/site/v2/sports/basketball/nba",
    "mlb": "https://site.api.espn.com/apis/site/v2/sports/baseball/mlb",
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 sports-edge/1.0",
    "Accept": "application/json",
}


def _get(url: str, retries: int = 3) -> Any:
    backoff = 1.5
    for attempt in range(retries):
        try:
            r = requests.get(url, headers=HEADERS, timeout=15)
            if r.status_code == 200:
                return r.json()
            if r.status_code in (429, 502, 503, 504):
                time.sleep(backoff); backoff *= 2; continue
            r.raise_for_status()
        except requests.RequestException:
            time.sleep(backoff); backoff *= 2
    raise RuntimeError(f"espn fetch failed: {url}")


def todays_scoreboard(league: str, date: str | None = None) -> dict:
    base = BASES[league]
    qs = ""
    if date:
        # ESPN expects YYYYMMDD
        qs = f"?dates={date.replace('-', '')}"
    return _get(f"{base}/scoreboard{qs}")


def parse_games(payload: dict) -> list[dict]:
    """Normalize ESPN scoreboard to: [{event_id, name, away, home, start_time, status, lines}]"""
    out = []
    for ev in payload.get("events", []):
        comps = (ev.get("competitions") or [{}])[0]
        teams = comps.get("competitors", [])
        home = next((t for t in teams if t.get("homeAway") == "home"), None)
        away = next((t for t in teams if t.get("homeAway") == "away"), None)
        if not (home and away):
            continue
        odds_block = (comps.get("odds") or [{}])[0] if comps.get("odds") else {}
        out.append({
            "event_id": ev.get("id"),
            "name": ev.get("name") or f"{(away.get('team') or {}).get('displayName')} @ {(home.get('team') or {}).get('displayName')}",
            "away_team": (away.get("team") or {}).get("displayName"),
            "home_team": (home.get("team") or {}).get("displayName"),
            "away_score": away.get("score"),
            "home_score": home.get("score"),
            "start_time": ev.get("date"),
            "status": (ev.get("status") or {}).get("type", {}).get("description"),
            "spread": odds_block.get("details"),
            "over_under": odds_block.get("overUnder"),
            "favorite": odds_block.get("favoriteAbbreviation"),
        })
    return out


def live_lines(league: str) -> list[dict]:
    """Convenience: today's normalized lines for a league."""
    today = dt.date.today().isoformat()
    payload = todays_scoreboard(league, today)
    return parse_games(payload)


if __name__ == "__main__":
    import json, sys
    league = sys.argv[1] if len(sys.argv) > 1 else "nba"
    print(json.dumps(live_lines(league), indent=2))
