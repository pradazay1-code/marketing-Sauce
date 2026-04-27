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

from .odds import fetch_nba_props, fetch_mlb_props
from .stats import nba_stats, mlb_stats
from .models import nba_projections, mlb_projections, ranker
from .grading import grader

DATA = pathlib.Path(__file__).resolve().parent / "data"
PUBLIC = DATA / "public"
PUBLIC.mkdir(parents=True, exist_ok=True)


def _safe(name: str, fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except Exception as e:
        traceback.print_exc()
        print(f"[pipeline] {name} failed: {e}", file=sys.stderr)
        return None


def run_nba(today: str) -> list[dict]:
    odds = _safe("nba odds", fetch_nba_props.fetch_all) or []
    if not odds:
        return []
    odds_path = DATA / "odds" / f"nba_{today}.json"
    odds_path.parent.mkdir(parents=True, exist_ok=True)
    odds_path.write_text(json.dumps(odds, indent=2))

    nba_stats.refresh_all()
    gamelog = json.loads((DATA / "stats" / f"nba_player_gamelog_{today}.json").read_text())
    team_adv = json.loads((DATA / "stats" / f"nba_team_advanced_{today}.json").read_text())

    player_picks = nba_projections.project_props(odds, gamelog, team_adv)
    total_picks = nba_projections.project_team_totals(odds, team_adv)
    return player_picks + total_picks


def run_mlb(today: str) -> list[dict]:
    odds = _safe("mlb odds", fetch_mlb_props.fetch_all) or []
    if not odds:
        return []
    odds_path = DATA / "odds" / f"mlb_{today}.json"
    odds_path.parent.mkdir(parents=True, exist_ok=True)
    odds_path.write_text(json.dumps(odds, indent=2))

    schedule_path = mlb_stats.refresh_schedule()
    schedule = json.loads(schedule_path.read_text())

    return (
        mlb_projections.project_player_hits(odds, schedule)
        + mlb_projections.project_pitcher_strikeouts(odds, schedule)
        + mlb_projections.project_moneylines(odds, schedule)
    )


def main() -> int:
    today = dt.date.today().isoformat()

    print(f"[pipeline] grading pending predictions...")
    _safe("grade", grader.grade_pending)

    print(f"[pipeline] generating picks for {today}...")
    nba_picks = _safe("nba run", run_nba, today) or []
    mlb_picks = _safe("mlb run", run_mlb, today) or []

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
    }
    (PUBLIC / "today.json").write_text(json.dumps(public, indent=2))

    calibration = grader.aggregate_calibration()
    (PUBLIC / "calibration.json").write_text(json.dumps(calibration, indent=2))

    print(f"[pipeline] wrote {sum(len(v) for v in top.values())} picks across {len(top)} markets")
    print(f"[pipeline] hit rate so far: {calibration.get('overall', {}).get('hit_rate')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
