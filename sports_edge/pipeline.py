"""Daily pipeline: pull odds + stats, project, rank, log predictions, grade
yesterday's picks, write JSON for the dashboard.

Run: `python -m sports_edge.pipeline`
"""

from __future__ import annotations

import datetime as dt
import json
import pathlib
import sys
import traceback

from .odds import fetch_nba_props, fetch_mlb_props, pinnacle_client, espn_client
from .stats import nba_stats, mlb_stats
from .models import nba_projections, mlb_projections, ranker
from .grading import grader

DATA = pathlib.Path(__file__).resolve().parent / "data"
PUBLIC = DATA / "public"
PUBLIC.mkdir(parents=True, exist_ok=True)

# Tracks per-step health to expose in the status panel on the dashboard.
STATUS: dict[str, dict] = {}


def _safe(name: str, fn, *args, **kwargs):
    try:
        result = fn(*args, **kwargs)
        STATUS[name] = {"ok": True, "n": (len(result) if hasattr(result, "__len__") else None)}
        return result
    except Exception as e:
        traceback.print_exc()
        STATUS[name] = {"ok": False, "error": str(e)[:200]}
        print(f"[pipeline] {name} failed: {e}", file=sys.stderr)
        return None


def run_nba(today: str) -> list[dict]:
    odds = _safe("nba_odds_dk", fetch_nba_props.fetch_all) or []
    if not odds:
        odds = _safe("nba_odds_pinnacle", pinnacle_client.build_props, "nba") or []
    if not odds:
        return []
    (DATA / "odds").mkdir(parents=True, exist_ok=True)
    (DATA / "odds" / f"nba_{today}.json").write_text(json.dumps(odds, indent=2))

    refreshed = _safe("nba_stats", nba_stats.refresh_all)
    if not refreshed:
        return []
    try:
        gamelog = json.loads((DATA / "stats" / f"nba_player_gamelog_{today}.json").read_text())
        team_adv = json.loads((DATA / "stats" / f"nba_team_advanced_{today}.json").read_text())
    except FileNotFoundError:
        return []

    player_picks = nba_projections.project_props(odds, gamelog, team_adv)
    total_picks = nba_projections.project_team_totals(odds, team_adv)
    return player_picks + total_picks


def run_mlb(today: str) -> list[dict]:
    odds = _safe("mlb_odds_dk", fetch_mlb_props.fetch_all) or []
    if not odds:
        odds = _safe("mlb_odds_pinnacle", pinnacle_client.build_props, "mlb") or []
    if not odds:
        return []
    (DATA / "odds").mkdir(parents=True, exist_ok=True)
    (DATA / "odds" / f"mlb_{today}.json").write_text(json.dumps(odds, indent=2))

    schedule_path = _safe("mlb_schedule", mlb_stats.refresh_schedule)
    if not schedule_path:
        return []
    schedule = json.loads(schedule_path.read_text())

    return (
        mlb_projections.project_player_hits(odds, schedule)
        + mlb_projections.project_pitcher_strikeouts(odds, schedule)
        + mlb_projections.project_moneylines(odds, schedule)
    )


def collect_live_lines() -> dict[str, list[dict]]:
    """Today's games + ESPN consensus lines per league. Always populated when
    ESPN works, regardless of whether Pinnacle/DK gave us odds."""
    out = {}
    for league in ("nba", "mlb"):
        rows = _safe(f"{league}_espn", espn_client.live_lines, league) or []
        out[league] = rows
    return out


def main() -> int:
    today = dt.date.today().isoformat()

    print(f"[pipeline] grading pending predictions...")
    _safe("grader", grader.grade_pending)

    print(f"[pipeline] generating picks for {today}...")
    nba_picks = _safe("nba_run", run_nba, today) or []
    mlb_picks = _safe("mlb_run", run_mlb, today) or []
    live = collect_live_lines()

    all_picks = nba_picks + mlb_picks
    top = ranker.top_n(all_picks, n=15)

    pred_doc = {
        "date": today,
        "generated_at": dt.datetime.utcnow().isoformat() + "Z",
        "picks": [pick for picks in top.values() for pick in picks],
    }
    (DATA / "predictions").mkdir(parents=True, exist_ok=True)
    (DATA / "predictions" / f"{today}.json").write_text(json.dumps(pred_doc, indent=2))

    public = {
        "date": today,
        "generated_at": pred_doc["generated_at"],
        "categories": top,
        "totals": {m: len(rows) for m, rows in top.items()},
        "live_lines": live,
        "status": STATUS,
        "raw_pick_counts": {
            "nba_total": len(nba_picks),
            "mlb_total": len(mlb_picks),
        },
    }
    (PUBLIC / "today.json").write_text(json.dumps(public, indent=2))

    calibration = grader.aggregate_calibration()
    (PUBLIC / "calibration.json").write_text(json.dumps(calibration, indent=2))

    n_picks = sum(len(v) for v in top.values())
    n_games = sum(len(v) for v in live.values())
    print(f"[pipeline] wrote {n_picks} ranked picks, {n_games} live games tracked")
    print(f"[pipeline] hit rate so far: {calibration.get('overall', {}).get('hit_rate')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
