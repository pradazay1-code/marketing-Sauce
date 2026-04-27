"""Terminal viewer for today's picks. Prints a formatted dashboard to stdout.

Usage:
    python -m sports_edge.view              # show today's picks (local file)
    python -m sports_edge.view --remote     # fetch from GitHub branch (live)
    python -m sports_edge.view --market player_points

Designed to render cleanly inside Claude Code or any terminal.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
import urllib.request
from typing import Any

REPO = "pradazay1-code/marketing-Sauce"
BRANCH = "claude/add-sports-betting-odds-4TIbZ"
RAW = f"https://raw.githubusercontent.com/{REPO}/{BRANCH}/sports_edge/data/public"

CATEGORY_LABELS = {
    "player_points": "NBA Points",
    "player_rebounds": "NBA Rebounds",
    "player_threes": "NBA 3-Pointers",
    "game_total": "NBA Team Total",
    "player_hits": "MLB Hits",
    "pitcher_strikeouts": "MLB Strikeouts",
    "moneyline": "MLB Moneyline",
}
ORDER = list(CATEGORY_LABELS)

DIM = "\033[2m"; BOLD = "\033[1m"; GREEN = "\033[92m"; RED = "\033[91m"
YELLOW = "\033[93m"; CYAN = "\033[96m"; GRAY = "\033[90m"; RESET = "\033[0m"


def _color_for_kind(k: str | None) -> str:
    return {"value": GREEN, "watch": YELLOW, "fade": GRAY}.get(k or "", "")


def _fmt_pct(v: float | None, signed: bool = False) -> str:
    if v is None:
        return "—"
    s = f"{v*100:+.1f}%" if signed else f"{v*100:.1f}%"
    return s


def _fmt_odds(v: int | float | None) -> str:
    if v is None:
        return "—"
    v = int(v)
    return f"+{v}" if v > 0 else str(v)


def _load(remote: bool) -> dict:
    if remote:
        url = f"{RAW}/today.json?_={int(__import__('time').time())}"
        with urllib.request.urlopen(url, timeout=15) as r:
            return json.loads(r.read())
    p = pathlib.Path(__file__).resolve().parent / "data" / "public" / "today.json"
    return json.loads(p.read_text())


def _load_calibration(remote: bool) -> dict | None:
    try:
        if remote:
            with urllib.request.urlopen(f"{RAW}/calibration.json", timeout=15) as r:
                return json.loads(r.read())
        p = pathlib.Path(__file__).resolve().parent / "data" / "public" / "calibration.json"
        return json.loads(p.read_text())
    except Exception:
        return None


def render_header(today: dict, cal: dict | None) -> None:
    date = today.get("date", "?")
    gen = today.get("generated_at", "?")
    print(f"{BOLD}{CYAN}Sports Edge — {date}{RESET}  {DIM}generated {gen}{RESET}")

    if cal:
        o = cal.get("overall") or {}
        hr = o.get("hit_rate"); roi = o.get("roi"); n = o.get("n", 0)
        bits = []
        if n:
            bits.append(f"hit rate {GREEN}{(hr*100):.1f}%{RESET}" if hr is not None else "")
            roi_s = f"{roi:+.3f}u" if roi is not None else "—"
            bits.append(f"roi {roi_s}")
            bits.append(f"{n} graded")
        if bits:
            print("  " + DIM + " · ".join(b for b in bits if b) + RESET)


def render_status(today: dict) -> None:
    status = today.get("status") or {}
    counts = today.get("raw_pick_counts") or {}
    live = today.get("live_lines") or {}
    live_n = sum(len(v or []) for v in live.values())

    print()
    print(f"{BOLD}Status{RESET}")
    print(f"  Live games tracked: {live_n} (NBA: {len(live.get('nba') or [])}, MLB: {len(live.get('mlb') or [])})")
    print(f"  Raw model picks:    NBA {counts.get('nba_total', 0)}, MLB {counts.get('mlb_total', 0)}")
    if status:
        for k, v in sorted(status.items()):
            ok = v.get("ok")
            color = GREEN if ok else RED
            note = v.get("error") if not ok else f"n={v.get('n')}"
            print(f"  {color}{'OK' if ok else 'FAIL'}{RESET}  {k:<25} {DIM}{note}{RESET}")


def render_market(today: dict, market: str, limit: int) -> None:
    rows = ((today.get("categories") or {}).get(market) or [])[:limit]
    label = CATEGORY_LABELS.get(market, market)
    print(f"\n{BOLD}{label}{RESET}  {DIM}({len(rows)}){RESET}")
    if not rows:
        print(f"  {DIM}no picks{RESET}")
        return

    if market == "moneyline":
        print(f"  {DIM}#  GAME                                           PICK                MODEL%   ODDS    EDGE     EV      KIND{RESET}")
        for i, r in enumerate(rows, 1):
            kind = r.get("pick_kind") or ""
            kc = _color_for_kind(kind)
            print(f"  {i:>2} {(r.get('event_name') or '')[:46]:<46}  "
                  f"{(r.get('pick') or '')[:18]:<18}  "
                  f"{_fmt_pct(r.get('model_prob')):>6}  "
                  f"{_fmt_odds(r.get('odds')):>5}  "
                  f"{_fmt_pct(r.get('edge'), signed=True):>7}  "
                  f"{_fmt_pct(r.get('ev'), signed=True):>7}  "
                  f"{kc}{kind}{RESET}")
        return

    if market == "game_total":
        print(f"  {DIM}#  GAME                                           SIDE   LINE   PROJ   MODEL%  ODDS    EDGE     EV      KIND{RESET}")
        for i, r in enumerate(rows, 1):
            kind = r.get("pick_kind") or ""; kc = _color_for_kind(kind)
            print(f"  {i:>2} {(r.get('event_name') or '')[:46]:<46}  "
                  f"{(r.get('side') or ''):<5}  "
                  f"{r.get('line', '—'):>5}  "
                  f"{r.get('model_mu', '—'):>5}  "
                  f"{_fmt_pct(r.get('model_prob')):>6}  "
                  f"{_fmt_odds(r.get('odds')):>5}  "
                  f"{_fmt_pct(r.get('edge'), signed=True):>7}  "
                  f"{_fmt_pct(r.get('ev'), signed=True):>7}  "
                  f"{kc}{kind}{RESET}")
        return

    # player props
    print(f"  {DIM}#  PLAYER                MATCHUP                          SIDE   LINE   PROJ   MODEL%  ODDS    EDGE     EV      KIND{RESET}")
    for i, r in enumerate(rows, 1):
        kind = r.get("pick_kind") or ""; kc = _color_for_kind(kind)
        player = (r.get("player") or "")[:21]
        ev_n = (r.get("event_name") or "")[:32]
        print(f"  {i:>2} {player:<21}  {ev_n:<32}  "
              f"{(r.get('side') or ''):<5}  "
              f"{r.get('line', '—'):>5}  "
              f"{r.get('model_mu', '—'):>5}  "
              f"{_fmt_pct(r.get('model_prob')):>6}  "
              f"{_fmt_odds(r.get('odds')):>5}  "
              f"{_fmt_pct(r.get('edge'), signed=True):>7}  "
              f"{_fmt_pct(r.get('ev'), signed=True):>7}  "
              f"{kc}{kind}{RESET}")


def render_live_lines(today: dict, league_filter: str | None) -> None:
    live = today.get("live_lines") or {}
    print(f"\n{BOLD}Live Lines{RESET}")
    for league, games in live.items():
        if league_filter and league != league_filter:
            continue
        if not games:
            print(f"  {DIM}{league.upper()}: no games today{RESET}"); continue
        print(f"\n  {BOLD}{league.upper()}{RESET}  {DIM}({len(games)} games){RESET}")
        print(f"  {DIM}TIME           STATUS                  GAME                                     SPREAD          O/U     SCORE{RESET}")
        for g in games:
            t = (g.get("start_time") or "")[11:16]
            status = (g.get("status") or "")[:22]
            game = f"{(g.get('away_team') or '?')[:18]} @ {(g.get('home_team') or '?')[:18]}"
            spread = g.get("spread") or "—"
            ou = g.get("over_under")
            ou_s = f"{ou}" if ou is not None else "—"
            ah, ah2 = g.get("away_score"), g.get("home_score")
            score = f"{ah}-{ah2}" if (ah is not None and ah2 is not None and (str(ah)!='0' or str(ah2)!='0')) else ""
            print(f"  {t:<14} {status:<23} {game:<40}  {str(spread)[:14]:<14}  {ou_s:>5}   {score}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--remote", action="store_true",
                    help="fetch live data from GitHub instead of local file")
    ap.add_argument("--market", default=None, choices=ORDER + ["live"],
                    help="show only one market")
    ap.add_argument("--limit", type=int, default=15)
    ap.add_argument("--no-status", action="store_true")
    args = ap.parse_args()

    today = _load(args.remote)
    cal = _load_calibration(args.remote)
    render_header(today, cal)
    if not args.no_status:
        render_status(today)

    if args.market == "live":
        render_live_lines(today, None)
        return 0
    if args.market:
        render_market(today, args.market, args.limit)
        return 0

    for m in ORDER:
        render_market(today, m, args.limit)
    render_live_lines(today, None)
    return 0


if __name__ == "__main__":
    sys.exit(main())
