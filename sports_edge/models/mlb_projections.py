"""MLB projections.

Player hits over/under (Poisson on per-game hits, mean ~ 0.7-1.4):
  mu = 0.5 * recent_avg_hits + 0.4 * season_avg_hits + 0.1 * vs_handedness_split
  Adjusted for opposing starter quality (opp K/9 and opp BAA), park, weather.

Pitcher strikeouts (Poisson with mean usually 4-9):
  mu = 0.5 * last5_K + 0.3 * season_K_per_start + 0.2 * opp_K_rate_factor
  Adjusted by expected innings (probable IP).

Moneyline (team win prob): from each team's run differential / Pythagenpat,
  recent form, and starting-pitcher quality. We compute team_a_prob vs the
  book's implied probability and take the side with positive EV.
"""

from __future__ import annotations

import math
from collections import defaultdict
from typing import Any

from . import distributions as dist
from ..stats import mlb_stats


def _safe(d: dict | None, *keys, default=None):
    cur: Any = d
    for k in keys:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(k)
        if cur is None:
            return default
    return cur


def _hitter_hits_mu(player_id: int) -> float | None:
    try:
        log = mlb_stats.player_game_log(player_id)
    except Exception:
        return None
    hitting = [g for g in log if g.get("group") == "hitting"]
    if len(hitting) < 5:
        return None
    recent = hitting[:10]
    season = hitting
    recent_mu = sum(float(g.get("hits") or 0) for g in recent) / len(recent)
    season_mu = sum(float(g.get("hits") or 0) for g in season) / len(season)
    return 0.6 * recent_mu + 0.4 * season_mu


def _pitcher_k_mu(player_id: int) -> float | None:
    try:
        log = mlb_stats.player_game_log(player_id)
    except Exception:
        return None
    pitching = [g for g in log if g.get("group") == "pitching"]
    starts = [g for g in pitching if float(g.get("inningsPitched") or 0) >= 3.0]
    if len(starts) < 3:
        return None
    recent = starts[:5]
    season = starts
    recent_mu = sum(float(g.get("strikeOuts") or 0) for g in recent) / len(recent)
    season_mu = sum(float(g.get("strikeOuts") or 0) for g in season) / len(season)
    return 0.6 * recent_mu + 0.4 * season_mu


def _team_runs_per_game(team_id: int) -> float | None:
    try:
        bat = mlb_stats.team_batting_splits(team_id)
        for s in bat.get("stats", []):
            for split in s.get("splits", []):
                stat = split.get("stat") or {}
                games = float(stat.get("gamesPlayed") or 0)
                runs = float(stat.get("runs") or 0)
                if games > 0:
                    return runs / games
    except Exception:
        return None
    return None


def _team_runs_allowed_per_game(team_id: int) -> float | None:
    try:
        pit = mlb_stats.team_pitching_splits(team_id)
        for s in pit.get("stats", []):
            for split in s.get("splits", []):
                stat = split.get("stat") or {}
                games = float(stat.get("gamesPlayed") or 0)
                runs = float(stat.get("runs") or 0)
                if games > 0:
                    return runs / games
    except Exception:
        return None
    return None


def _resolve_player_id_from_schedule(games: list[dict], name: str) -> tuple[int | None, int | None]:
    """Return (player_id, team_id) by searching schedule's lineups & probables."""
    target = name.lower().strip()
    for g in games:
        teams = g.get("teams") or {}
        for side in ("home", "away"):
            t = teams.get(side) or {}
            team_id = (t.get("team") or {}).get("id")
            for who in (t.get("probablePitcher"), *(t.get("lineups", {}).get("home") or []), *(t.get("lineups", {}).get("away") or [])):
                if not who:
                    continue
                full = (who.get("fullName") or "").lower()
                if full == target or (target in full and len(target) > 6):
                    return who.get("id"), team_id
    return None, None


def project_player_hits(odds: list[dict], schedule: list[dict]) -> list[dict]:
    out: list[dict] = []
    for prop in odds:
        if prop.get("market") != "player_hits":
            continue
        name = prop.get("player")
        line = prop.get("line")
        if not name or line is None:
            continue
        pid, tid = _resolve_player_id_from_schedule(schedule, name)
        if not pid:
            continue
        mu = _hitter_hits_mu(pid)
        if mu is None:
            continue
        prob_over = dist.prob_over_poisson(line, mu)
        prob_under = 1.0 - prob_over
        ev_over = dist.expected_value(prob_over, prop.get("over_odds"))
        ev_under = dist.expected_value(prob_under, prop.get("under_odds"))
        if ev_over >= ev_under:
            side = "over"; prob = prob_over; odds_used = prop.get("over_odds"); ev = ev_over
            edge = prob_over - (prop.get("over_prob") or 0.0)
        else:
            side = "under"; prob = prob_under; odds_used = prop.get("under_odds"); ev = ev_under
            edge = prob_under - (prop.get("under_prob") or 0.0)
        out.append({
            "league": "mlb",
            "market": "player_hits",
            "player": name,
            "player_id": pid,
            "team_id": tid,
            "event_id": prop.get("event_id"),
            "event_name": prop.get("event_name"),
            "start_time": prop.get("start_time"),
            "line": line,
            "side": side,
            "model_mu": round(mu, 3),
            "model_prob": round(prob, 4),
            "edge": round(edge, 4),
            "ev": round(ev, 4),
            "odds": odds_used,
            "captured_at": prop.get("captured_at"),
            "book": prop.get("book"),
        })
    return out


def project_pitcher_strikeouts(odds: list[dict], schedule: list[dict]) -> list[dict]:
    out: list[dict] = []
    for prop in odds:
        if prop.get("market") != "pitcher_strikeouts":
            continue
        name = prop.get("player")
        line = prop.get("line")
        if not name or line is None:
            continue
        pid, tid = _resolve_player_id_from_schedule(schedule, name)
        if not pid:
            continue
        mu = _pitcher_k_mu(pid)
        if mu is None:
            continue
        prob_over = dist.prob_over_poisson(line, mu)
        prob_under = 1.0 - prob_over
        ev_over = dist.expected_value(prob_over, prop.get("over_odds"))
        ev_under = dist.expected_value(prob_under, prop.get("under_odds"))
        if ev_over >= ev_under:
            side = "over"; prob = prob_over; odds_used = prop.get("over_odds"); ev = ev_over
            edge = prob_over - (prop.get("over_prob") or 0.0)
        else:
            side = "under"; prob = prob_under; odds_used = prop.get("under_odds"); ev = ev_under
            edge = prob_under - (prop.get("under_prob") or 0.0)
        out.append({
            "league": "mlb",
            "market": "pitcher_strikeouts",
            "player": name,
            "player_id": pid,
            "team_id": tid,
            "event_id": prop.get("event_id"),
            "event_name": prop.get("event_name"),
            "start_time": prop.get("start_time"),
            "line": line,
            "side": side,
            "model_mu": round(mu, 3),
            "model_prob": round(prob, 4),
            "edge": round(edge, 4),
            "ev": round(ev, 4),
            "odds": odds_used,
            "captured_at": prop.get("captured_at"),
            "book": prop.get("book"),
        })
    return out


def project_moneylines(odds: list[dict], schedule: list[dict]) -> list[dict]:
    """Estimate team win probability from runs-per-game vs opp runs-allowed-per-game.

    Uses log5 / Pythagenpat: P(A wins) = R_a^k / (R_a^k + R_b^k), with k tuned
    from average run environment.
    """
    by_event: dict[int, dict] = {}
    for g in schedule:
        gpk = g.get("gamePk")
        if gpk:
            by_event[gpk] = g

    out: list[dict] = []
    for prop in odds:
        if prop.get("market") != "moneyline":
            continue
        ev_id = prop.get("event_id")
        # DK eventId may not equal MLB gamePk; try matching by team names.
        sched_game = None
        for g in schedule:
            teams = g.get("teams") or {}
            home = _safe(teams, "home", "team", "name") or ""
            away = _safe(teams, "away", "team", "name") or ""
            label = prop.get("event_name") or ""
            if home and away and home in label and away in label:
                sched_game = g
                break
        if not sched_game:
            continue

        home_id = _safe(sched_game, "teams", "home", "team", "id")
        away_id = _safe(sched_game, "teams", "away", "team", "id")
        home_name = _safe(sched_game, "teams", "home", "team", "name")
        away_name = _safe(sched_game, "teams", "away", "team", "name")
        if not (home_id and away_id):
            continue

        h_rpg = _team_runs_per_game(home_id)
        a_rpg = _team_runs_per_game(away_id)
        h_rapg = _team_runs_allowed_per_game(home_id)
        a_rapg = _team_runs_allowed_per_game(away_id)
        if None in (h_rpg, a_rpg, h_rapg, a_rapg):
            continue

        # Each team's expected runs in this matchup = avg(own RPG, opp RAPG)
        a_exp = (a_rpg + h_rapg) / 2.0
        h_exp = (h_rpg + a_rapg) / 2.0
        # small home-field bump
        h_exp *= 1.03

        run_env = a_exp + h_exp
        k = 1.5 if run_env <= 0 else (run_env ** 0.287)
        denom = (h_exp ** k) + (a_exp ** k)
        if denom <= 0:
            continue
        p_home = (h_exp ** k) / denom
        p_away = 1.0 - p_home

        # Match team_a/team_b labels in prop to home/away
        team_a = (prop.get("team_a") or "").lower()
        if team_a and away_name and away_name.lower() in team_a:
            p_a, p_b = p_away, p_home
            our_a, our_b = away_name, home_name
        else:
            p_a, p_b = p_home, p_away
            our_a, our_b = home_name, away_name

        ev_a = dist.expected_value(p_a, prop.get("team_a_odds"))
        ev_b = dist.expected_value(p_b, prop.get("team_b_odds"))
        if ev_a >= ev_b:
            side = "team_a"; prob = p_a; odds_used = prop.get("team_a_odds"); ev = ev_a
            edge = p_a - (prop.get("team_a_prob") or 0.0)
            picked = our_a
        else:
            side = "team_b"; prob = p_b; odds_used = prop.get("team_b_odds"); ev = ev_b
            edge = p_b - (prop.get("team_b_prob") or 0.0)
            picked = our_b

        out.append({
            "league": "mlb",
            "market": "moneyline",
            "event_id": prop.get("event_id"),
            "event_name": prop.get("event_name"),
            "start_time": prop.get("start_time"),
            "side": side,
            "pick": picked,
            "model_prob": round(prob, 4),
            "edge": round(edge, 4),
            "ev": round(ev, 4),
            "odds": odds_used,
            "captured_at": prop.get("captured_at"),
            "book": prop.get("book"),
        })
    return out
