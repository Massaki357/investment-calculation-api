"""Spot curve bootstrapping and forward rates (effective annual rates)."""

from collections.abc import Sequence
from dataclasses import dataclass

from app.core.exceptions import InvalidInputError, NonFiniteResultError
from app.services.fixed_income.bonds import whole_periods
from app.utils.validation import ensure_finite


@dataclass(frozen=True, slots=True)
class CurveInstrument:
    maturity_years: float
    coupon_rate: float
    price: float
    face_value: float


@dataclass(frozen=True, slots=True)
class SpotPoint:
    maturity_years: float
    discount_factor: float
    spot_rate: float


def bootstrap_spot_curve(
    instruments: Sequence[CurveInstrument], coupon_frequency: int
) -> list[SpotPoint]:
    """Bootstrap discount factors and effective annual spot rates from coupon bonds.

    Instruments must mature on consecutive coupon dates 1/m, 2/m, ..., n/m (one per date).
    For the bond maturing at period k with coupon c = face × coupon_rate / m:
        d_k = (price − c × Σ_{j<k} d_j) / (c + face)
        spot_k = d_k ^ (−1 / t_k) − 1, with t_k = k / m years
    """
    if not instruments:
        raise InvalidInputError("instruments must contain at least one bond")

    by_period: dict[int, CurveInstrument] = {}
    for instrument in instruments:
        period = whole_periods(instrument.maturity_years, coupon_frequency, name="maturity_years")
        if period in by_period:
            raise InvalidInputError(f"more than one instrument matures at period {period}")
        by_period[period] = instrument

    expected = list(range(1, len(instruments) + 1))
    if sorted(by_period) != expected:
        raise InvalidInputError(
            "instruments must mature on consecutive coupon dates starting at 1 / coupon_frequency"
        )

    points: list[SpotPoint] = []
    cumulative_factors = 0.0
    for period in expected:
        bond = by_period[period]
        coupon = bond.face_value * bond.coupon_rate / coupon_frequency
        factor = (bond.price - coupon * cumulative_factors) / (coupon + bond.face_value)
        if factor <= 0:
            raise InvalidInputError(
                f"prices imply a non-positive discount factor at period {period} "
                "(inconsistent or arbitrage prices)"
            )
        cumulative_factors += factor
        years = period / coupon_frequency
        try:
            spot = factor ** (-1 / years) - 1
        except OverflowError as exc:
            raise NonFiniteResultError("spot rate is too large to be represented") from exc
        points.append(
            SpotPoint(
                maturity_years=years,
                discount_factor=factor,
                spot_rate=ensure_finite(spot, "spot rate"),
            )
        )
    return points


def forward_rate(
    short_spot_rate: float, short_maturity: float, long_spot_rate: float, long_maturity: float
) -> float:
    """f(t1, t2) = [(1 + s2)^t2 / (1 + s1)^t1] ^ (1 / (t2 − t1)) − 1 (effective annual)."""
    if long_maturity <= short_maturity:
        raise InvalidInputError("long_maturity must be greater than short_maturity")
    if short_spot_rate <= -1 or long_spot_rate <= -1:
        raise InvalidInputError("spot rates must be greater than -1")
    try:
        growth = (1 + long_spot_rate) ** long_maturity / (1 + short_spot_rate) ** short_maturity
        result = growth ** (1 / (long_maturity - short_maturity)) - 1
    except OverflowError as exc:
        raise NonFiniteResultError("forward rate is too large to be represented") from exc
    return ensure_finite(result, "forward rate")
