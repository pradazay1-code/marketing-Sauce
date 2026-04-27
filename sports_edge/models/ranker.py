"""Rank model picks by EV and pick the top N per category.

Categories surfaced on the dashboard:
  NBA: player_points, player_rebounds, player_threes, game_total
  MLB: player_hits, pitcher_strikeouts, moneyline
"""

from __future__ import annotations

NBA_CATEGORIES = ("player_points", "player_rebounds", "player_threes", "game_total")
MLB_CATEGORIES = ("player_hits", "pitcher_strikeouts", "moneyline")


def _confidence_band(model_prob: float, n_games: int | None) -> str:
    if n_games is not None and n_games < 8:
        return "low"
    if model_prob >= 0.62 or model_prob <= 0.38:
        return "high"
    if model_prob >= 0.55 or model_prob <= 0.45:
        return "medium"
    return "low"


def top_n(picks: list[dict], n: int = 15) -> dict[str, list[dict]]:
    by_market: dict[str, list[dict]] = {}
    for p in picks:
        m = p.get("market")
        if not m:
            continue
        by_market.setdefault(m, []).append(p)

    out: dict[str, list[dict]] = {}
    for market, rows in by_market.items():
        # Filter to positive-EV. Drop rows with absurd EV / odds — those are
        # almost always parsing artifacts (alt-line markets, partial-game lines,
        # stale specials), not real edges. A real prop edge of >50% EV does not
        # exist on a regulated market.
        cleaned = []
        for r in rows:
            ev = r.get("ev") or 0
            odds = r.get("odds")
            mp = r.get("model_prob")
            if ev <= 0 or ev > 0.50:
                continue
            if odds is not None and (odds > 1000 or odds < -1000):
                continue
            if mp is not None and (mp <= 0.02 or mp >= 0.98):
                continue
            cleaned.append(r)
        cleaned.sort(key=lambda r: r.get("ev") or 0, reverse=True)
        for r in cleaned:
            r["confidence"] = _confidence_band(r.get("model_prob") or 0.5, r.get("n_games"))
        out[market] = cleaned[:n]
    return out
