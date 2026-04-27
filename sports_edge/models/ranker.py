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
        # Filter to positive-EV, then rank by EV desc.
        rows = [r for r in rows if (r.get("ev") or 0) > 0]
        rows.sort(key=lambda r: r.get("ev") or 0, reverse=True)
        for r in rows:
            r["confidence"] = _confidence_band(r.get("model_prob") or 0.5, r.get("n_games"))
        out[market] = rows[:n]
    return out
