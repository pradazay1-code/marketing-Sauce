"""NBA player projections.

Approach:
  1. For each player in the gamelog, compute season + last-N rolling means
     and standard deviations for PTS / REB / FG3M / MIN.
  2. Build per-team pace and defensive-rating multipliers.
  3. For each prop (player, market, line), project mu and sigma using:
       mu = 0.55*last10 + 0.30*season + 0.15*lastN_vs_opponent
       sigma = empirical std (floor 1.5 for points, 1.0 for rebounds, 0.7 for threes)
       mu *= pace_factor(opponent) * defense_factor(opponent, market)
  4. Convert to prob_over via Normal (points) or Poisson (rebounds/threes).
  5. Compute edge vs sportsbook implied probability and EV.

This is a starting model. The feedback loop (grader.py) tracks calibration
so weights can be retrained from logged outcomes weekly.
"""

from __future__ import annotations

import json
import math
import pathlib
import statistics
from collections import defaultdict
from typing import Any

from . import distributions as dist

DATA = pathlib.Path(__file__).resolve().parents[1] / "data"

MARKET_TO_COL = {
    "player_points": "PTS",
    "player_rebounds": "REB",
    "player_threes": "FG3M",
}

# Empirical floor for sigma to avoid overconfident projections from small samples.
SIGMA_FLOOR = {
    "player_points": 6.0,
    "player_rebounds": 2.5,
    "player_threes": 1.2,
}

# Markets where the count-distribution Poisson fits better than Normal.
USE_POISSON = {"player_threes"}


def _load_json(p: pathlib.Path) -> Any:
    return json.loads(p.read_text())


def _index_gamelog(rows: list[dict]) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        name = r.get("PLAYER_NAME")
        if not name:
            continue
        out[name].append(r)
    # newest first, which leaguegamelog already returns
    return out


def _team_index(team_rows: list[dict]) -> dict[str, dict]:
    """Multiple keys (abbr + full name + nickname) -> stat row, for fuzzy lookup."""
    out: dict[str, dict] = {}
    for r in team_rows:
        keys = []
        if r.get("TEAM_ABBREVIATION"): keys.append(r["TEAM_ABBREVIATION"])
        if r.get("TEAM_NAME"): keys.append(r["TEAM_NAME"])
        # Last token of full name is usually the nickname (Lakers, Celtics, ...).
        if r.get("TEAM_NAME"):
            tail = r["TEAM_NAME"].split()[-1]
            keys.append(tail)
        for k in keys:
            out[k.lower()] = r
    return out


def _lookup_team(idx: dict[str, dict], substr: str | None) -> dict | None:
    if not substr:
        return None
    s = substr.lower()
    if s in idx:
        return idx[s]
    for k, v in idx.items():
        if k in s or s in k:
            return v
    return None


def _team_pace(team_rows: list[dict]) -> dict[str, float]:
    out: dict[str, float] = {}
    for r in team_rows:
        abbr = r.get("TEAM_ABBREVIATION") or r.get("TEAM_NAME")
        pace = r.get("PACE") or r.get("PACE_PER40")
        if abbr and pace:
            out[abbr] = float(pace)
    return out


def _team_defrtg(team_rows: list[dict]) -> dict[str, float]:
    out: dict[str, float] = {}
    for r in team_rows:
        abbr = r.get("TEAM_ABBREVIATION") or r.get("TEAM_NAME")
        defrtg = r.get("DEF_RATING")
        if abbr and defrtg:
            out[abbr] = float(defrtg)
    return out


def _split_event_name(event_name: str | None) -> tuple[str | None, str | None]:
    if not event_name or " @ " not in event_name:
        return None, None
    away, home = [p.strip() for p in event_name.split(" @ ", 1)]
    return away, home


def _player_team_from_log(games: list[dict]) -> str | None:
    for g in games:
        if g.get("TEAM_ABBREVIATION"):
            return g["TEAM_ABBREVIATION"]
    return None


def _opponent_for_player(player_team: str | None, away: str | None, home: str | None) -> str | None:
    if not player_team:
        return None
    pt = player_team.lower()
    if away and pt in away.lower():
        return home
    if home and pt in home.lower():
        return away
    return None


def _project_market(games: list[dict], col: str) -> tuple[float, float]:
    vals = [g.get(col) for g in games if g.get(col) is not None]
    vals = [float(v) for v in vals]
    if not vals:
        return 0.0, 0.0
    last10 = vals[:10]
    season = vals
    mu = 0.55 * (sum(last10) / len(last10)) + 0.45 * (sum(season) / len(season))
    sigma = statistics.pstdev(season) if len(season) >= 4 else statistics.pstdev(season + season)
    return mu, sigma


def project_props(odds: list[dict], gamelog_rows: list[dict], team_rows: list[dict]) -> list[dict]:
    by_player = _index_gamelog(gamelog_rows)
    team_idx = _team_index(team_rows)
    pace_vals = [float(r.get("PACE") or r.get("PACE_PER40") or 0) for r in team_rows if (r.get("PACE") or r.get("PACE_PER40"))]
    defrtg_vals = [float(r.get("DEF_RATING") or 0) for r in team_rows if r.get("DEF_RATING")]
    league_pace = (sum(pace_vals) / len(pace_vals)) if pace_vals else 100.0
    league_def = (sum(defrtg_vals) / len(defrtg_vals)) if defrtg_vals else 113.0

    results: list[dict] = []
    for prop in odds:
        market = prop.get("market")
        col = MARKET_TO_COL.get(market)
        if not col:
            continue
        player = prop.get("player")
        line = prop.get("line")
        if not player or line is None:
            continue
        games = by_player.get(player) or []
        if len(games) < 4:
            continue

        mu, sigma = _project_market(games, col)
        sigma = max(sigma, SIGMA_FLOOR.get(market, 1.0))

        # Pace + defense adjustment using opponent
        away, home = _split_event_name(prop.get("event_name"))
        player_team = _player_team_from_log(games)
        opp = _opponent_for_player(player_team, away, home)
        # opp is full team name in event_name; pace dict is by abbreviation.
        # We approximate by matching on substring.
        pace_factor = 1.0
        def_factor = 1.0
        opp_row = _lookup_team(team_idx, opp)
        if opp_row:
            opp_pace = float(opp_row.get("PACE") or opp_row.get("PACE_PER40") or league_pace)
            opp_def = float(opp_row.get("DEF_RATING") or league_def)
            pace_factor = opp_pace / league_pace
            # Higher def_rating = worse defense = boost mu
            def_factor = opp_def / league_def

        adj_mu = mu * pace_factor * def_factor

        if market in USE_POISSON:
            prob_over = dist.prob_over_poisson(line, adj_mu)
        else:
            prob_over = dist.prob_over_normal(line, adj_mu, sigma)
        prob_under = 1.0 - prob_over

        book_over = prop.get("over_prob") or 0.0
        book_under = prop.get("under_prob") or 0.0

        edge_over = prob_over - book_over
        edge_under = prob_under - book_under

        ev_over = dist.expected_value(prob_over, prop.get("over_odds"))
        ev_under = dist.expected_value(prob_under, prop.get("under_odds"))

        if ev_over >= ev_under:
            side = "over"
            prob = prob_over
            odds_used = prop.get("over_odds")
            edge = edge_over
            ev = ev_over
        else:
            side = "under"
            prob = prob_under
            odds_used = prop.get("under_odds")
            edge = edge_under
            ev = ev_under

        results.append(
            {
                "league": "nba",
                "market": market,
                "player": player,
                "team": player_team,
                "opponent": opp,
                "event_id": prop.get("event_id"),
                "event_name": prop.get("event_name"),
                "start_time": prop.get("start_time"),
                "line": line,
                "side": side,
                "model_mu": round(adj_mu, 2),
                "model_sigma": round(sigma, 2),
                "model_prob": round(prob, 4),
                "book_prob": round((book_over if side == "over" else book_under), 4),
                "edge": round(edge, 4),
                "ev": round(ev, 4),
                "odds": odds_used,
                "pace_factor": round(pace_factor, 3),
                "def_factor": round(def_factor, 3),
                "n_games": len(games),
                "captured_at": prop.get("captured_at"),
                "book": prop.get("book"),
            }
        )
    return results


def project_team_totals(odds: list[dict], team_rows: list[dict]) -> list[dict]:
    """Game total over/under projections from team off/def ratings + pace."""
    team_idx = _team_index(team_rows)
    if not team_idx:
        return []

    results: list[dict] = []

    for prop in odds:
        if prop.get("market") != "game_total":
            continue
        line = prop.get("line")
        away, home = _split_event_name(prop.get("event_name"))
        if not (away and home):
            continue

        a_row = _lookup_team(team_idx, away)
        h_row = _lookup_team(team_idx, home)
        if not (a_row and h_row):
            continue
        try:
            a_off = float(a_row["OFF_RATING"]); a_def = float(a_row["DEF_RATING"])
            h_off = float(h_row["OFF_RATING"]); h_def = float(h_row["DEF_RATING"])
            a_pace = float(a_row.get("PACE") or a_row.get("PACE_PER40"))
            h_pace = float(h_row.get("PACE") or h_row.get("PACE_PER40"))
        except (TypeError, KeyError, ValueError):
            continue

        game_pace = (a_pace + h_pace) / 2.0
        # Expected points = (offensive rating vs opponent's defensive rating) * pace / 100
        a_proj = ((a_off + h_def) / 2.0) * game_pace / 100.0
        h_proj = ((h_off + a_def) / 2.0) * game_pace / 100.0
        proj_total = a_proj + h_proj
        sigma = 11.0  # historical std dev of NBA team-total errors

        prob_over = dist.prob_over_normal(line, proj_total, sigma)
        prob_under = 1.0 - prob_over
        ev_over = dist.expected_value(prob_over, prop.get("over_odds"))
        ev_under = dist.expected_value(prob_under, prop.get("under_odds"))

        if ev_over >= ev_under:
            side = "over"; prob = prob_over; odds_used = prop.get("over_odds"); ev = ev_over
            edge = prob_over - (prop.get("over_prob") or 0.0)
        else:
            side = "under"; prob = prob_under; odds_used = prop.get("under_odds"); ev = ev_under
            edge = prob_under - (prop.get("under_prob") or 0.0)

        results.append(
            {
                "league": "nba",
                "market": "game_total",
                "event_id": prop.get("event_id"),
                "event_name": prop.get("event_name"),
                "start_time": prop.get("start_time"),
                "line": line,
                "side": side,
                "model_mu": round(proj_total, 2),
                "model_sigma": sigma,
                "model_prob": round(prob, 4),
                "edge": round(edge, 4),
                "ev": round(ev, 4),
                "odds": odds_used,
                "captured_at": prop.get("captured_at"),
                "book": prop.get("book"),
            }
        )
    return results
