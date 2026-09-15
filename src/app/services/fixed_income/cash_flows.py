"""Internal rate of return of a periodic cash flow series."""

import math
from collections.abc import Sequence
from itertools import pairwise

import numpy as np
from numpy.polynomial import polynomial

from app.core.exceptions import InvalidInputError
from app.utils.solvers import find_sign_change_root

_ROOT_DEDUP_TOLERANCE = 1e-7


def net_present_value(rate: float, cash_flows: Sequence[float]) -> float:
    """NPV = Σ CF_t / (1 + rate)^t for t = 0..n."""
    return math.fsum(cf * (1 + rate) ** -t for t, cf in enumerate(cash_flows))


def _sign_changes(cash_flows: Sequence[float]) -> int:
    signs = [cf > 0 for cf in cash_flows if cf != 0]
    return sum(1 for previous, current in pairwise(signs) if previous != current)


def _unique_root(cash_flows: Sequence[float]) -> float:
    """Exactly one sign change → exactly one IRR in (−1, ∞) (Descartes' rule of signs).

    As r → +∞ the earliest non-zero flow dominates the NPV; as r → −1 the latest one does.
    """
    nonzero = [cf for cf in cash_flows if cf != 0]
    return find_sign_change_root(
        lambda rate: net_present_value(rate, cash_flows),
        sign_near_minus_one=math.copysign(1.0, nonzero[-1]),
        sign_at_infinity=math.copysign(1.0, nonzero[0]),
        too_close_to_minus_one="the internal rate of return is too close to -100%",
        too_large="the internal rate of return is too large to be computed",
    )


def _all_real_roots(cash_flows: Sequence[float]) -> list[float]:
    """IRR candidates as roots of Σ CF_t x^t with x = 1 / (1 + r) > 0, verified on the NPV."""
    roots = polynomial.polyroots(np.asarray(cash_flows, dtype=float))
    scale = math.fsum(abs(cf) for cf in cash_flows)
    candidates: list[float] = []
    for root in roots:
        if abs(root.imag) > 1e-9 * max(1.0, abs(root.real)) or root.real <= 0:
            continue
        rate = float(1 / root.real - 1)
        try:
            residual = net_present_value(rate, cash_flows)
        except OverflowError:
            continue
        if abs(residual) > 1e-7 * scale:
            continue
        if all(abs(rate - known) > _ROOT_DEDUP_TOLERANCE for known in candidates):
            candidates.append(rate)
    return sorted(candidates)


def internal_rate_of_return(cash_flows: Sequence[float]) -> float:
    """IRR: the periodic rate r > −1 such that Σ CF_t / (1 + r)^t = 0, t = 0..n.

    One sign change guarantees a unique IRR (solved with Brent's method). With more sign changes
    every real root is computed; if more than one exists the IRR is ambiguous and rejected.
    """
    if len(cash_flows) < 2:
        raise InvalidInputError("cash_flows must contain at least two values")
    if not any(cf > 0 for cf in cash_flows) or not any(cf < 0 for cf in cash_flows):
        raise InvalidInputError(
            "cash_flows must contain at least one positive and one negative value"
        )

    if _sign_changes(cash_flows) == 1:
        return _unique_root(cash_flows)

    roots = _all_real_roots(cash_flows)
    if not roots:
        raise InvalidInputError("these cash flows have no real internal rate of return")
    if len(roots) > 1:
        raise InvalidInputError(
            "these cash flows have multiple internal rates of return; IRR is ambiguous",
            details={"irr_candidates": roots},
        )
    return roots[0]
