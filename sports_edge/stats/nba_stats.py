"""NBA stats from stats.nba.com (free, unofficial, used by NBA.com itself).

Pulls:
  - league-wide player game logs for the current season (one row per player-game)
  - team advanced stats (pace, defensive rating)
  - opponent positional defense (pts/reb/3s allowed vs each position)

Caches results to sports_edge/data/stats/nba_*.json so we don't hammer the
API every run.
"""

from __future__ import annotations

import datetime as dt
import json
import pathlib
import time
from typing import Any

import requests

BASE = "https://stats.nba.com/stats"
HEADERS = {
    "Host": "stats.nba.com",
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Origin": "https://www.nba.com",
    "Referer": "https://www.nba.com/",
    "x-nba-stats-origin": "stats",
    "x-nba-stats-token": "true",
    "Connection": "keep-alive",
}


def current_season() -> str:
    today = dt.date.today()
    start_year = today.year if today.month >= 10 else today.year - 1
    return f"{start_year}-{str(start_year + 1)[-2:]}"


def _get(path: str, params: dict[str, Any], retries: int = 4) -> dict:
    url = f"{BASE}/{path}"
    backoff = 2.0
    for attempt in range(retries):
        try:
            r = requests.get(url, headers=HEADERS, params=params, timeout=30)
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
    raise RuntimeError(f"stats.nba.com failed: {path} {params}")


def _rows_to_dicts(payload: dict, result_set: str = "") -> list[dict]:
    sets = payload.get("resultSets") or payload.get("resultSet") or []
    if isinstance(sets, dict):
        sets = [sets]
    if result_set:
        sets = [s for s in sets if s.get("name") == result_set]
    out: list[dict] = []
    for s in sets:
        headers = s.get("headers", [])
        for row in s.get("rowSet", []):
            out.append(dict(zip(headers, row)))
    return out


def league_player_gamelog(season: str | None = None) -> list[dict]:
    season = season or current_season()
    payload = _get(
        "leaguegamelog",
        {
            "Counter": 1000,
            "DateFrom": "",
            "DateTo": "",
            "Direction": "DESC",
            "LeagueID": "00",
            "PlayerOrTeam": "P",
            "Season": season,
            "SeasonType": "Regular Season",
            "Sorter": "DATE",
        },
    )
    return _rows_to_dicts(payload, "LeagueGameLog")


def league_team_advanced(season: str | None = None) -> list[dict]:
    season = season or current_season()
    payload = _get(
        "leaguedashteamstats",
        {
            "MeasureType": "Advanced",
            "PerMode": "PerGame",
            "PlusMinus": "N",
            "PaceAdjust": "N",
            "Rank": "N",
            "LeagueID": "00",
            "Season": season,
            "SeasonType": "Regular Season",
            "Outcome": "",
            "Location": "",
            "Month": 0,
            "SeasonSegment": "",
            "DateFrom": "",
            "DateTo": "",
            "OpponentTeamID": 0,
            "VsConference": "",
            "VsDivision": "",
            "TeamID": 0,
            "Conference": "",
            "Division": "",
            "GameSegment": "",
            "Period": 0,
            "ShotClockRange": "",
            "LastNGames": 0,
            "GameScope": "",
            "PlayerExperience": "",
            "PlayerPosition": "",
            "StarterBench": "",
            "TwoWay": 0,
        },
    )
    return _rows_to_dicts(payload)


def opponent_positional_defense(season: str | None = None, position: str = "") -> list[dict]:
    """Per-team allowed averages, optionally filtered to a position bucket (G/F/C)."""
    season = season or current_season()
    payload = _get(
        "leaguedashptdefend",
        {
            "DefenseCategory": "Overall",
            "PerMode": "PerGame",
            "Season": season,
            "SeasonType": "Regular Season",
            "LeagueID": "00",
            "Month": 0,
            "PORound": 0,
            "DateFrom": "",
            "DateTo": "",
            "TeamID": 0,
            "Period": 0,
            "OpponentTeamID": 0,
            "PlayerPosition": position,
            "GameSegment": "",
            "LastNGames": 0,
            "Outcome": "",
            "Location": "",
            "VsConference": "",
            "VsDivision": "",
        },
    )
    return _rows_to_dicts(payload)


def todays_scoreboard() -> list[dict]:
    today = dt.date.today().strftime("%m/%d/%Y")
    payload = _get(
        "scoreboardv3",
        {"GameDate": today, "LeagueID": "00", "DayOffset": 0},
    )
    games = payload.get("scoreboard", {}).get("games", [])
    return games


def cache_path(name: str) -> pathlib.Path:
    p = pathlib.Path(__file__).resolve().parents[1] / "data" / "stats"
    p.mkdir(parents=True, exist_ok=True)
    return p / name


def refresh_all(force: bool = False) -> dict[str, pathlib.Path]:
    today = dt.date.today().isoformat()
    out = {}

    gamelog_p = cache_path(f"nba_player_gamelog_{today}.json")
    if force or not gamelog_p.exists():
        rows = league_player_gamelog()
        gamelog_p.write_text(json.dumps(rows))
    out["gamelog"] = gamelog_p

    team_p = cache_path(f"nba_team_advanced_{today}.json")
    if force or not team_p.exists():
        rows = league_team_advanced()
        team_p.write_text(json.dumps(rows))
    out["team_advanced"] = team_p

    return out


if __name__ == "__main__":
    print(refresh_all())
