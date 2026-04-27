"""MLB stats from statsapi.mlb.com (official, free, no key).

Pulls: today's schedule, per-player game logs, team splits, probable pitchers.
"""

from __future__ import annotations

import datetime as dt
import json
import pathlib
import time
from typing import Any

import requests

BASE = "https://statsapi.mlb.com/api/v1"
HEADERS = {"Accept": "application/json", "User-Agent": "sports-edge/1.0"}


def _get(path: str, params: dict[str, Any] | None = None, retries: int = 3) -> dict:
    url = f"{BASE}/{path}"
    backoff = 1.5
    for attempt in range(retries):
        try:
            r = requests.get(url, headers=HEADERS, params=params or {}, timeout=20)
            if r.status_code == 200:
                return r.json()
            if r.status_code in (429, 502, 503, 504):
                time.sleep(backoff)
                backoff *= 2
                continue
            r.raise_for_status()
        except requests.RequestException:
            time.sleep(backoff)
            backoff *= 2
    raise RuntimeError(f"statsapi failed: {path}")


def todays_schedule(date: str | None = None) -> list[dict]:
    date = date or dt.date.today().isoformat()
    payload = _get(
        "schedule",
        {
            "sportId": 1,
            "date": date,
            "hydrate": "probablePitcher(note),lineups,team,linescore,weather,venue",
        },
    )
    games = []
    for d in payload.get("dates", []):
        for g in d.get("games", []):
            games.append(g)
    return games


def player_game_log(player_id: int, season: int | None = None) -> list[dict]:
    season = season or dt.date.today().year
    payload = _get(
        f"people/{player_id}/stats",
        {"stats": "gameLog", "season": season, "group": "hitting,pitching"},
    )
    out: list[dict] = []
    for s in payload.get("stats", []):
        group = s.get("group", {}).get("displayName")
        for split in s.get("splits", []):
            row = dict(split.get("stat", {}))
            row["date"] = split.get("date")
            row["opponent_id"] = split.get("opponent", {}).get("id")
            row["opponent"] = split.get("opponent", {}).get("name")
            row["is_home"] = split.get("isHome")
            row["group"] = group
            out.append(row)
    return out


def player_season_splits(player_id: int, season: int | None = None) -> dict:
    season = season or dt.date.today().year
    payload = _get(
        f"people/{player_id}/stats",
        {
            "stats": "statSplits",
            "season": season,
            "group": "hitting,pitching",
            "sitCodes": "vr,vl,h,a,risp,n",
        },
    )
    return payload


def team_pitching_splits(team_id: int, season: int | None = None) -> dict:
    season = season or dt.date.today().year
    return _get(
        f"teams/{team_id}/stats",
        {"stats": "season", "season": season, "group": "pitching"},
    )


def team_batting_splits(team_id: int, season: int | None = None) -> dict:
    season = season or dt.date.today().year
    return _get(
        f"teams/{team_id}/stats",
        {"stats": "season", "season": season, "group": "hitting"},
    )


def cache_path(name: str) -> pathlib.Path:
    p = pathlib.Path(__file__).resolve().parents[1] / "data" / "stats"
    p.mkdir(parents=True, exist_ok=True)
    return p / name


def refresh_schedule(force: bool = False) -> pathlib.Path:
    today = dt.date.today().isoformat()
    p = cache_path(f"mlb_schedule_{today}.json")
    if force or not p.exists():
        p.write_text(json.dumps(todays_schedule(today)))
    return p


if __name__ == "__main__":
    print(refresh_schedule())
