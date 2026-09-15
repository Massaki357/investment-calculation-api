"""Numerical root finding shared by calculation services."""

import math
from collections.abc import Callable
from typing import cast

from scipy.optimize import brentq

from app.core.exceptions import ConvergenceError, InvalidInputError

_MAX_LOW_STEPS = 60  # (low − 1) / 2 per step: after 60 steps 1 + low ≈ 1e-18
_MAX_RATE = 1e12


def _brent(function: Callable[[float], float], low: float, high: float) -> float:
    try:
        # Without full_output, brentq returns only the root.
        root = cast(float, brentq(function, low, high, xtol=1e-15, maxiter=500))
    except (RuntimeError, ValueError) as exc:
        raise ConvergenceError("the rate solver did not converge") from exc
    return float(root)


def find_sign_change_root(
    function: Callable[[float], float],
    *,
    sign_near_minus_one: float,
    sign_at_infinity: float,
    too_close_to_minus_one: str,
    too_large: str,
) -> float:
    """Root of a continuous function of a per-period rate r in (−1, +∞) with a single crossing.

    The caller states the sign of the function on each side of the root. The bracket starts at
    [0, 1], moves `low` towards −1 and `high` towards +∞ until the signs match, then Brent's
    method refines the root.
    """

    def evaluate(rate: float, message: str) -> float:
        try:
            value = function(rate)
        except OverflowError as exc:
            raise InvalidInputError(message) from exc
        if not math.isfinite(value):
            raise InvalidInputError(message)
        return value

    high = 1.0
    f_high = evaluate(high, too_large)
    while f_high != 0 and math.copysign(1.0, f_high) != sign_at_infinity:
        if high >= _MAX_RATE:
            raise ConvergenceError(too_large)
        high *= 10
        f_high = evaluate(high, too_large)
    if f_high == 0:
        return high

    low = 0.0
    f_low = evaluate(low, too_close_to_minus_one)
    for _ in range(_MAX_LOW_STEPS):
        if f_low == 0 or math.copysign(1.0, f_low) == sign_near_minus_one:
            break
        low = (low - 1) / 2
        f_low = evaluate(low, too_close_to_minus_one)
    else:
        raise InvalidInputError(too_close_to_minus_one)
    if f_low == 0:
        return low

    return _brent(function, low, high)


def solve_rate_for_decreasing_value(
    value_at: Callable[[float], float], target: float, *, target_name: str
) -> float:
    """Per-period rate r > −1 where a strictly decreasing value function equals `target`.

    Used for yields: a bond price falls as the yield rises, so value − target is positive
    near −1 and negative as r → +∞.
    """
    return find_sign_change_root(
        lambda rate: value_at(rate) - target,
        sign_near_minus_one=1.0,
        sign_at_infinity=-1.0,
        too_close_to_minus_one=f"{target_name} is too high: it implies a rate too close to -100%",
        too_large=f"{target_name} is too low: no finite rate reproduces it",
    )
