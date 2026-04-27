"""Lightweight stats helpers: normal CDF, Poisson tail probabilities.

We avoid scipy to keep the deploy footprint small (GitHub Actions startup time
dominates for short-running jobs).
"""

from __future__ import annotations

import math


def normal_cdf(x: float, mu: float, sigma: float) -> float:
    if sigma <= 0:
        return 1.0 if x >= mu else 0.0
    z = (x - mu) / sigma
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def prob_over_normal(line: float, mu: float, sigma: float) -> float:
    """P(X > line) for X ~ Normal(mu, sigma)."""
    if sigma <= 0:
        return 1.0 if mu > line else 0.0
    # Sportsbook lines are typically X.5; treat as continuous.
    return 1.0 - normal_cdf(line, mu, sigma)


def _poisson_cdf(k: int, lam: float) -> float:
    if lam <= 0:
        return 1.0
    s = 0.0
    term = math.exp(-lam)
    s = term
    for i in range(1, k + 1):
        term *= lam / i
        s += term
    return min(s, 1.0)


def prob_over_poisson(line: float, lam: float) -> float:
    """P(X > line) where X ~ Poisson(lam) and line is typically a half-integer."""
    if lam <= 0:
        return 0.0
    k = math.floor(line)
    return max(0.0, 1.0 - _poisson_cdf(k, lam))


def expected_value(prob_win: float, american_odds: float) -> float:
    """EV per $1 staked at given American odds."""
    if american_odds is None:
        return 0.0
    odds = float(american_odds)
    payout = (odds / 100.0) if odds > 0 else (100.0 / -odds)
    return prob_win * payout - (1.0 - prob_win)


def kelly_fraction(prob_win: float, american_odds: float) -> float:
    """Full-Kelly stake fraction. Use 1/4-Kelly in practice."""
    if american_odds is None:
        return 0.0
    odds = float(american_odds)
    b = (odds / 100.0) if odds > 0 else (100.0 / -odds)
    p = prob_win
    q = 1.0 - p
    if b <= 0:
        return 0.0
    f = (b * p - q) / b
    return max(0.0, f)
