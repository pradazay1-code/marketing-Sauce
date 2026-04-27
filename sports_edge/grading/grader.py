"""Auto-grade yesterday's predictions and update running calibration stats.

Algorithm:
  1. Load every prediction file from data/predictions/ that hasn't been graded.
  2. For each pick, look up the actual stat:
       NBA player props: scrape stats.nba.com gamelog for the date.
       NBA game totals: stats.nba.com scoreboardv3 final scores.
       MLB player props: statsapi.mlb.com player game log for the date.
       MLB moneylines: statsapi.mlb.com schedule final state.
  3. Mark each pick win/loss/push, write to data/results/.
  4. Aggregate calibration: brier score, hit rate, units P/L, by market.

Brier score and hit-rate-by-confidence-bucket are what we use to retrain
the model weights. The retraining runs weekly; this script runs daily.
"""

from __future__ import annotations

import datetime as dt
import json
import pathlib
from collections import defaultdict
from typing import Any

import requests

from ..stats import nba_stats, mlb_stats

DATA = pathlib.Path(__file__).resolve().parents[1] / "data"
PRED_DIR = DATA / "predictions"
RESULT_DIR = DATA / "results"
RESULT_DIR.mkdir(parents=True, exist_ok=True)


def _payout(odds: float | int | None, won: bool) -> float:
    if odds is None or not won:
        return -1.0 if not won else 0.0
    o = float(odds)
    if won:
        return (o / 100.0) if o > 0 else (100.0 / -o)
    return -1.0


def _grade_ou(pick: dict, actual: float) -> str:
    line = pick.get("line")
    side = pick.get("side")
    if line is None or actual is None:
        return "unknown"
    if actual == line:
        return "push"
    if side == "over":
        return "win" if actual > line else "loss"
    return "win" if actual < line else "loss"


def _nba_actuals_for_date(date: str) -> dict[tuple[str, str], dict]:
    """Return {(player_lower, team_lower): row} from leaguegamelog for a single date."""
    rows = nba_stats.league_player_gamelog()  # season-to-date, includes that date
    out: dict[tuple[str, str], dict] = {}
    for r in rows:
        d = (r.get("GAME_DATE") or "")[:10]
        if d != date:
            continue
        name = (r.get("PLAYER_NAME") or "").lower()
        team = (r.get("TEAM_ABBREVIATION") or "").lower()
        out[(name, team)] = r
    return out


def _nba_team_totals_for_date(date: str) -> dict[int, dict]:
    """Map eventId -> {home_pts, away_pts, total} for the given date."""
    # We look at scoreboardv3 final scores. eventId from DK doesn't equal NBA gameId,
    # so we match by team names later.
    out = {}
    try:
        games = nba_stats.todays_scoreboard()
    except Exception:
        games = []
    for g in games:
        if g.get("gameStatus") != 3:
            continue
        home = g.get("homeTeam") or {}
        away = g.get("awayTeam") or {}
        out[g.get("gameId")] = {
            "home_team": home.get("teamName"),
            "away_team": away.get("teamName"),
            "home_pts": home.get("score"),
            "away_pts": away.get("score"),
            "total": (home.get("score") or 0) + (away.get("score") or 0),
        }
    return out


def grade_file(pred_path: pathlib.Path) -> dict:
    pred = json.loads(pred_path.read_text())
    pred_date = pred.get("date")
    picks = pred.get("picks", [])

    # Group lookups by league for one fetch each.
    nba_actuals = None
    nba_finals = None
    mlb_finals_by_gpk: dict[int, dict] = {}

    results = []
    for p in picks:
        league = p.get("league")
        market = p.get("market")
        actual = None
        outcome = "pending"

        if league == "nba" and market in ("player_points", "player_rebounds", "player_threes"):
            if nba_actuals is None:
                nba_actuals = _nba_actuals_for_date(pred_date)
            name = (p.get("player") or "").lower()
            team = (p.get("team") or "").lower()
            row = nba_actuals.get((name, team))
            if row is None:
                # fall back to player-name-only match
                row = next((v for (n, _), v in nba_actuals.items() if n == name), None)
            if row:
                col = {"player_points": "PTS", "player_rebounds": "REB", "player_threes": "FG3M"}[market]
                actual = float(row.get(col) or 0)
                outcome = _grade_ou(p, actual)
        elif league == "nba" and market == "game_total":
            if nba_finals is None:
                nba_finals = _nba_team_totals_for_date(pred_date)
            label = (p.get("event_name") or "").lower()
            game = next(
                (g for g in nba_finals.values() if (g.get("home_team") or "").lower() in label and (g.get("away_team") or "").lower() in label),
                None,
            )
            if game:
                actual = float(game["total"])
                outcome = _grade_ou(p, actual)
        elif league == "mlb" and market in ("player_hits", "pitcher_strikeouts"):
            pid = p.get("player_id")
            if pid:
                try:
                    log = mlb_stats.player_game_log(pid)
                    row = next((g for g in log if g.get("date") == pred_date), None)
                    if row:
                        col = "hits" if market == "player_hits" else "strikeOuts"
                        actual = float(row.get(col) or 0)
                        outcome = _grade_ou(p, actual)
                except Exception:
                    pass
        elif league == "mlb" and market == "moneyline":
            try:
                schedule = mlb_stats.todays_schedule(pred_date)
            except Exception:
                schedule = []
            label = (p.get("event_name") or "").lower()
            sched_game = None
            for g in schedule:
                home = ((g.get("teams") or {}).get("home") or {}).get("team", {}).get("name", "").lower()
                away = ((g.get("teams") or {}).get("away") or {}).get("team", {}).get("name", "").lower()
                if home and away and home in label and away in label:
                    sched_game = g
                    break
            if sched_game:
                ls = sched_game.get("linescore") or {}
                if (sched_game.get("status") or {}).get("abstractGameState") == "Final":
                    home_score = ((ls.get("teams") or {}).get("home") or {}).get("runs")
                    away_score = ((ls.get("teams") or {}).get("away") or {}).get("runs")
                    if home_score is not None and away_score is not None:
                        winner = "home" if home_score > away_score else "away"
                        pick_label = (p.get("pick") or "").lower()
                        home_name = ((sched_game.get("teams") or {}).get("home") or {}).get("team", {}).get("name", "").lower()
                        away_name = ((sched_game.get("teams") or {}).get("away") or {}).get("team", {}).get("name", "").lower()
                        won = (winner == "home" and pick_label == home_name) or (winner == "away" and pick_label == away_name)
                        outcome = "win" if won else "loss"
                        actual = f"{away_score}-{home_score}"

        graded = dict(p)
        graded["actual"] = actual
        graded["outcome"] = outcome
        if outcome == "win":
            graded["units"] = round(_payout(p.get("odds"), True), 3)
        elif outcome == "loss":
            graded["units"] = -1.0
        elif outcome == "push":
            graded["units"] = 0.0
        else:
            graded["units"] = None
        results.append(graded)

    out = {"date": pred_date, "graded_at": dt.datetime.utcnow().isoformat() + "Z", "picks": results}
    out_path = RESULT_DIR / f"{pred_date}.json"
    out_path.write_text(json.dumps(out, indent=2))
    return out


def grade_pending() -> list[dict]:
    """Grade every prediction file that doesn't yet have a results file, but only
    for dates strictly before today (so games are final)."""
    today = dt.date.today().isoformat()
    out = []
    for pred_path in sorted(PRED_DIR.glob("*.json")):
        date = pred_path.stem
        if date >= today:
            continue
        result_path = RESULT_DIR / f"{date}.json"
        if result_path.exists():
            existing = json.loads(result_path.read_text())
            # Re-grade only if there are still pending picks.
            if not any(p.get("outcome") == "pending" for p in existing.get("picks", [])):
                continue
        out.append(grade_file(pred_path))
    return out


def aggregate_calibration() -> dict:
    """Roll up calibration stats across all graded picks."""
    by_market: dict[str, dict] = defaultdict(lambda: {
        "n": 0, "wins": 0, "losses": 0, "pushes": 0,
        "units": 0.0, "brier_sum": 0.0, "brier_n": 0,
    })
    overall = {"n": 0, "wins": 0, "units": 0.0}

    for res_path in sorted(RESULT_DIR.glob("*.json")):
        res = json.loads(res_path.read_text())
        for pick in res.get("picks", []):
            outcome = pick.get("outcome")
            market = pick.get("market") or "unknown"
            row = by_market[market]
            if outcome in ("win", "loss"):
                row["n"] += 1
                overall["n"] += 1
                if outcome == "win":
                    row["wins"] += 1
                    overall["wins"] += 1
                else:
                    row["losses"] += 1
                u = pick.get("units") or 0.0
                row["units"] += u
                overall["units"] += u
                # Brier: (model_prob_win - 1{win})^2
                p = pick.get("model_prob")
                if p is not None:
                    target = 1.0 if outcome == "win" else 0.0
                    row["brier_sum"] += (float(p) - target) ** 2
                    row["brier_n"] += 1
            elif outcome == "push":
                row["pushes"] += 1

    summary = {"overall": overall, "by_market": {}}
    for m, r in by_market.items():
        n = r["n"]
        r["hit_rate"] = round(r["wins"] / n, 4) if n else None
        r["roi"] = round(r["units"] / n, 4) if n else None
        r["brier"] = round(r["brier_sum"] / r["brier_n"], 4) if r["brier_n"] else None
        del r["brier_sum"]; del r["brier_n"]
        summary["by_market"][m] = r
    overall["hit_rate"] = round(overall["wins"] / overall["n"], 4) if overall["n"] else None
    overall["roi"] = round(overall["units"] / overall["n"], 4) if overall["n"] else None
    return summary


if __name__ == "__main__":
    grade_pending()
    summary = aggregate_calibration()
    (DATA / "public" / "calibration.json").write_text(json.dumps(summary, indent=2))
    print(summary)
