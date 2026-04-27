"""Pull NBA odds from DraftKings: player points, rebounds, threes, team totals.

Outputs JSON to sports_edge/data/odds/nba_YYYY-MM-DD.json with one row per
prop offering: { market, player, team, opponent, event_id, line,
over_odds, under_odds, over_prob, under_prob, captured_at }.
"""

from __future__ import annotations

import datetime as dt
import json
import pathlib
import sys

from . import dk_client as dk

# Category labels DraftKings uses on the NBA eventgroup. We try every known
# alias because DK has been inconsistent across seasons.
CATEGORY_ALIASES = {
    "points": ["Points", "Player Points", "Player Combos"],
    "rebounds": ["Rebounds", "Player Rebounds"],
    "threes": ["Threes", "Three Pointers", "Player Threes"],
    "team_total": ["Game Lines", "Game"],
}

# Subcategory label -> our market key
SUB_LABEL_TO_MARKET = {
    "points": "player_points",
    "player points o/u": "player_points",
    "rebounds": "player_rebounds",
    "player rebounds o/u": "player_rebounds",
    "threes": "player_threes",
    "3-pointers made": "player_threes",
    "player threes o/u": "player_threes",
    "total": "team_total",
    "team total": "team_total",
}


def _events_index(eventgroup: dict) -> dict[int, dict]:
    out = {}
    for ev in dk.list_events(eventgroup):
        out[ev.get("eventId")] = ev
    return out


def _extract_player_prop_offers(category_payload: dict, market: str) -> list[dict]:
    rows = []
    for sub_desc, _sub, offer in dk.iter_offers(category_payload):
        sub_name = (sub_desc.get("name") or "").strip().lower()
        if SUB_LABEL_TO_MARKET.get(sub_name) != market:
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


def _extract_team_total_offers(category_payload: dict) -> list[dict]:
    rows = []
    for sub_desc, _sub, offer in dk.iter_offers(category_payload):
        sub_name = (sub_desc.get("name") or "").strip().lower()
        if "total" not in sub_name:
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
        if line is None:
            continue
        rows.append(
            {
                "market": "game_total",
                "event_id": offer.get("eventId"),
                "line": float(line),
                "over_odds": over.get("oddsAmerican"),
                "under_odds": under.get("oddsAmerican"),
            }
        )
    return rows


def fetch_all() -> list[dict]:
    eg = dk.fetch_eventgroup("nba")
    events = _events_index(eg)

    captured = dt.datetime.utcnow().isoformat(timespec="seconds") + "Z"
    rows: list[dict] = []

    for market, aliases in CATEGORY_ALIASES.items():
        cat_id = dk.find_category_id(eg, aliases)
        if not cat_id:
            print(f"[nba] no DK category for {market} (tried {aliases})", file=sys.stderr)
            continue
        try:
            payload = dk.fetch_category("nba", cat_id)
        except Exception as e:
            print(f"[nba] failed category {market}: {e}", file=sys.stderr)
            continue

        if market == "team_total":
            offers = _extract_team_total_offers(payload)
        else:
            offers = _extract_player_prop_offers(payload, "player_" + market if market != "team_total" else market)
            # naming alignment: player_points/player_rebounds/player_threes
            if market == "points":
                offers = _extract_player_prop_offers(payload, "player_points")
            elif market == "rebounds":
                offers = _extract_player_prop_offers(payload, "player_rebounds")
            elif market == "threes":
                offers = _extract_player_prop_offers(payload, "player_threes")

        for r in offers:
            ev = events.get(r.get("event_id")) or {}
            r["event_name"] = ev.get("name")
            r["start_time"] = ev.get("startDate")
            r["home_team"] = ev.get("nameIdentifier") or ev.get("eventStatus", {}).get("homeCompetitor")
            r["away_team"] = ev.get("eventStatus", {}).get("awayCompetitor")
            r["over_prob"] = dk.american_to_prob(r.get("over_odds"))
            r["under_prob"] = dk.american_to_prob(r.get("under_odds"))
            r["captured_at"] = captured
            r["book"] = "draftkings"
        rows.extend(offers)

    return rows


def main() -> int:
    rows = fetch_all()
    today = dt.date.today().isoformat()
    out_dir = pathlib.Path(__file__).resolve().parents[1] / "data" / "odds"
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"nba_{today}.json"
    out.write_text(json.dumps(rows, indent=2))
    print(f"[nba] wrote {len(rows)} offers -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
