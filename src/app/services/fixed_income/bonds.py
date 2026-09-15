"""Fixed-rate bullet bonds priced on coupon dates."""

import math
from dataclasses import dataclass

from app.core.exceptions import InvalidInputError, NonFiniteResultError
from app.utils.math import safe_divide
from app.utils.solvers import solve_rate_for_decreasing_value
from app.utils.validation import ensure_finite

_PERIOD_TOLERANCE = 1e-9


@dataclass(frozen=True, slots=True)
class BondTerms:
    face_value: float
    coupon_rate: float
    years: float
    frequency: int

    @property
    def coupon_payment(self) -> float:
        return self.face_value * self.coupon_rate / self.frequency

    @property
    def periods(self) -> int:
        return whole_periods(self.years, self.frequency, name="years_to_maturity")


def whole_periods(years: float, frequency: int, *, name: str) -> int:
    """Number of coupon periods; must be a whole number because v1 prices on coupon dates."""
    if frequency < 1:
        raise InvalidInputError("coupon_frequency must be at least 1")
    exact = years * frequency
    periods = round(exact)
    if periods < 1 or abs(exact - periods) > _PERIOD_TOLERANCE:
        raise InvalidInputError(
            f"{name} × coupon_frequency must be a whole number of periods ≥ 1 "
            "(bonds are priced on coupon dates)"
        )
    return periods


@dataclass(frozen=True, slots=True)
class BondCashFlow:
    period: int
    time_years: float
    cash_flow: float
    discount_factor: float
    present_value: float


@dataclass(frozen=True, slots=True)
class BondValuation:
    price: float
    periodic_yield: float
    cash_flows: list[BondCashFlow]


def _discount_factor(periodic_yield: float, period: int) -> float:
    if periodic_yield <= -1:
        raise InvalidInputError("yield / coupon_frequency must be greater than -1")
    try:
        return (1 + periodic_yield) ** -period
    except OverflowError as exc:
        raise NonFiniteResultError("discount factor is too large to be represented") from exc


def value_bond(
    terms: BondTerms,
    annual_yield: float,
    *,
    redemption_value: float | None = None,
    periods: int | None = None,
) -> BondValuation:
    """Price = Σ C / (1 + y/m)^k + redemption / (1 + y/m)^n, k = 1..n.

    `redemption_value` and `periods` default to the face value and the periods to maturity;
    they are overridden to value the bond to a call date.
    """
    n = terms.periods if periods is None else periods
    redemption = terms.face_value if redemption_value is None else redemption_value
    periodic_yield = annual_yield / terms.frequency
    coupon = terms.coupon_payment

    flows: list[BondCashFlow] = []
    for period in range(1, n + 1):
        amount = coupon + (redemption if period == n else 0.0)
        factor = _discount_factor(periodic_yield, period)
        flows.append(
            BondCashFlow(
                period=period,
                time_years=period / terms.frequency,
                cash_flow=amount,
                discount_factor=factor,
                present_value=amount * factor,
            )
        )
    price = ensure_finite(math.fsum(flow.present_value for flow in flows), "bond price")
    return BondValuation(price=price, periodic_yield=periodic_yield, cash_flows=flows)


@dataclass(frozen=True, slots=True)
class YieldResult:
    annual_yield: float
    periodic_yield: float
    effective_annual_yield: float


def _yield_from_price(
    terms: BondTerms, price: float, *, redemption_value: float, periods: int, name: str
) -> YieldResult:
    if price <= 0:
        raise InvalidInputError("price must be greater than zero")
    if terms.coupon_payment < 0 or redemption_value <= 0:
        raise InvalidInputError("coupons must be ≥ 0 and the redemption value > 0")

    def price_at(periodic_yield: float) -> float:
        return value_bond(
            terms,
            periodic_yield * terms.frequency,
            redemption_value=redemption_value,
            periods=periods,
        ).price

    periodic = solve_rate_for_decreasing_value(price_at, price, target_name=name)
    return YieldResult(
        annual_yield=periodic * terms.frequency,
        periodic_yield=periodic,
        effective_annual_yield=(1 + periodic) ** terms.frequency - 1,
    )


def yield_to_maturity(terms: BondTerms, price: float) -> YieldResult:
    """Solve y such that value_bond(terms, y).price = price (bond-equivalent annual yield)."""
    return _yield_from_price(
        terms, price, redemption_value=terms.face_value, periods=terms.periods, name="price"
    )


def yield_to_call(
    terms: BondTerms, price: float, call_price: float, years_to_call: float
) -> YieldResult:
    """Solve y with cash flows up to the call date and call_price as the redemption value."""
    call_periods = whole_periods(years_to_call, terms.frequency, name="years_to_call")
    if call_periods > terms.periods:
        raise InvalidInputError("years_to_call cannot exceed years_to_maturity")
    return _yield_from_price(
        terms, price, redemption_value=call_price, periods=call_periods, name="price"
    )


def current_yield(annual_coupon: float, price: float) -> float:
    """Current Yield = annual coupon payment / price."""
    return safe_divide(annual_coupon, price, denominator_name="price")


@dataclass(frozen=True, slots=True)
class DurationResult:
    price: float
    macaulay_duration: float
    modified_duration: float
    convexity: float


def duration_and_convexity(terms: BondTerms, annual_yield: float) -> DurationResult:
    """Macaulay, modified duration and convexity, in years and years².

    Macaulay  = Σ t_k × PV_k / P, with t_k = k / m
    Modified  = Macaulay / (1 + y/m)
    Convexity = Σ PV_k × (t_k² + t_k / m) / [P × (1 + y/m)²]
    """
    valuation = value_bond(terms, annual_yield)
    price = valuation.price
    if price <= 0:
        raise InvalidInputError("duration requires a positive bond price")
    m = terms.frequency
    one_plus = 1 + valuation.periodic_yield

    macaulay = math.fsum(f.time_years * f.present_value for f in valuation.cash_flows) / price
    convexity_sum = math.fsum(
        f.present_value * (f.time_years**2 + f.time_years / m) for f in valuation.cash_flows
    )
    return DurationResult(
        price=price,
        macaulay_duration=macaulay,
        modified_duration=macaulay / one_plus,
        convexity=ensure_finite(convexity_sum / (price * one_plus**2), "convexity"),
    )


def yield_spread(bond_yield: float, benchmark_yield: float) -> float:
    """Spread = bond_yield − benchmark_yield (decimal; × 10,000 for basis points)."""
    return bond_yield - benchmark_yield
