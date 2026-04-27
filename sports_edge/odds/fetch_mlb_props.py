"""Pull MLB odds from DraftKings: hits o/u, strikeouts o/u, moneylines.

Outputs JSON to sports_edge/data/odds/mlb_YYYY-MM-DD.json.
"""

from __future__ import annotations

import datetime as dt
import json
import pathlib
import sys

from . import dk_client as dk

CATEGORY_ALIASES = {
    "hits": ["Hits", "Batter Hits", "Player Hits"],
    "strikeouts": ["Strikeouts", "Pitcher Strikeouts"],
    "game_lines": ["Game Lines", "Game"],
}


def _events_index(eventgroup: dict) -> dict[int, dict]:
    return {ev.get("eventId"): ev for ev in dk.list_events(eventgroup)}


def _extract_ou(category_payload: dict, market: str) -> list[dict]:
    rows = []
    for sub_desc, _sub, offer in dk.iter_offers(category_payload):
        sub_name = (sub_desc.get("name") or "").strip().lower()
        if market == "player_hits" and "hits" not in sub_name:
            continue
        if market == "pitcher_strikeouts" and "strikeout" not in sub_name:
            continue
        outcomes = offer.get("outcomes") or []
        if len(outcomes) != 2:
            continue
        over = next(
            (o for o in outcomes if (o.get("label") or "").lower().startswith("o")),
            None,
        )
        under = next(
            (o for o in outcomes if (o.get("label") or "").lower().startswith("u")),
            None,
        )
        if not over or not under:
            continue
        line = over.get("line") or under.get("line")
        player = over.get("participant") or offer.get("label")
        if not player or line is None:
            continue
        rows.append(
            {
                "market": market,
                "player": player,
                "event_id": offer.get("eventId"),
                "line": float(line),
                "over_odds": over.get("oddsAmerican"),
                "under_odds": under.get("oddsAmerican"),
            }
        )
    return rows


def _extract_moneylines(category_payload: dict) -> list[dict]:
    """Game Lines category contains moneyline subcategory with home/away outcomes per offer."""
    rows = []
    for sub_desc, _sub, offer in dk.iter_offers(category_payload):
        sub_name = (sub_desc.get("name") or "").strip().lower()
        if sub_name not in {"moneyline", "money line", "ml"}:
            continue
        outcomes = offer.get("outcomes") or []
        if len(outcomes) != 2:
            continue
        a, b = outcomes
        rows.append(
            {
                "market": "moneyline",
                "event_id": offer.get("eventId"),
                "team_a": a.get("label"),
                "team_a_odds": a.get("oddsAmerican"),
                "team_b": b.get("label"),
                "team_b_odds": b.get("oddsAmerican"),
            }
        )
    return rows


def fetch_all() -> list[dict]:
    eg = dk.fetch_eventgroup("mlb")
    events = _events_index(eg)
    captured = dt.datetime.utcnow().isoformat(timespec="seconds") + "Z"
    rows: list[dict] = []

    # Hits
    cat = dk.find_category_id(eg, CATEGORY_ALIASES["hits"])
    if cat:
        try:
            rows.extend(_extract_ou(dk.fetch_category("mlb", cat), "player_hits"))
        except Exception as e:
            print(f"[mlb] hits failed: {e}", file=sys.stderr)
    else:
        print("[mlb] no hits category found", file=sys.stderr)

    # Strikeouts
    cat = dk.find_category_id(eg, CATEGORY_ALIASES["strikeouts"])
    if cat:
        try:
            rows.extend(_extract_ou(dk.fetch_category("mlb", cat), "pitcher_strikeouts"))
        except Exception as e:
            print(f"[mlb] strikeouts failed: {e}", file=sys.stderr)
    else:
        print("[mlb] no strikeouts category found", file=sys.stderr)

    # Moneylines from game lines
    cat = dk.find_category_id(eg, CATEGORY_ALIASES["game_lines"])
    if cat:
        try:
            rows.extend(_extract_moneylines(dk.fetch_category("mlb", cat)))
        except Exception as e:
            print(f"[mlb] game lines failed: {e}", file=sys.stderr)

    for r in rows:
        ev = events.get(r.get("event_id")) or {}
        r["event_name"] = ev.get("name")
        r["start_time"] = ev.get("startDate")
        r["captured_at"] = captured
        r["book"] = "draftkings"
        if "over_odds" in r:
            r["over_prob"] = dk.american_to_prob(r["over_odds"])
            r["under_prob"] = dk.american_to_prob(r["under_odds"])
        if "team_a_odds" in r:
            r["team_a_prob"] = dk.american_to_prob(r["team_a_odds"])
            r["team_b_prob"] = dk.american_to_prob(r["team_b_odds"])

    return rows


def main() -> int:
    rows = fetch_all()
    today = dt.date.today().isoformat()
    out_dir = pathlib.Path(__file__).resolve().parents[1] / "data" / "odds"
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"mlb_{today}.json"
    out.write_text(json.dumps(rows, indent=2))
    print(f"[mlb] wrote {len(rows)} offers -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
