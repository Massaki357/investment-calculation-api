from dataclasses import asdict

from fastapi import APIRouter

from app.api.endpoint_specs import (
    CalculationEndpoint,
    MetricEndpoint,
    add_calculation_endpoints,
    add_metric_endpoints,
)
from app.schemas.common import MetricBreakdownResponse, MetricValue, Unit
from app.schemas.fixed_income import bonds as schemas
from app.schemas.fixed_income.bonds import (
    BondCashFlowItem,
    BondPriceRequest,
    BondPriceResponse,
    CreditSpreadRequest,
    DurationResponse,
    YieldToCallRequest,
    YieldToMaturityRequest,
)
from app.schemas.fixed_income.common import BondTermsRequest
from app.services.fixed_income import bonds as calc
from app.services.fixed_income.bonds import BondTerms, YieldResult

router = APIRouter(tags=["Fixed Income · Bonds"])

COUPON_DATE_NOTE = (
    "Priced on a coupon date: years × coupon_frequency must be a whole number "
    "(no accrued interest or day count in v1)."
)
YIELD_NOTE = (
    "Yields are annual, compounded at coupon_frequency (bond-equivalent): periodic yield = "
    "yield / coupon_frequency."
)

BOND_EXAMPLE = {
    "face_value": 1000.0,
    "coupon_rate": 0.06,
    "years_to_maturity": 5,
    "coupon_frequency": 2,
}


def _terms(r: BondTermsRequest) -> BondTerms:
    return BondTerms(
        face_value=r.face_value,
        coupon_rate=r.coupon_rate,
        years=r.years_to_maturity,
        frequency=r.coupon_frequency,
    )


def _bond_price(r: BondPriceRequest) -> BondPriceResponse:
    terms = _terms(r)
    valuation = calc.value_bond(terms, r.yield_to_maturity)
    return BondPriceResponse(
        price=valuation.price,
        price_to_face=valuation.price / terms.face_value,
        coupon_payment=terms.coupon_payment,
        number_of_periods=terms.periods,
        periodic_yield=valuation.periodic_yield,
        cash_flows=[BondCashFlowItem(**asdict(flow)) for flow in valuation.cash_flows],
        currency=r.currency,
    )


def _yield_response(metric: str, result: YieldResult) -> MetricBreakdownResponse:
    return MetricBreakdownResponse(
        metric=metric,
        value=result.annual_yield,
        unit=Unit.DECIMAL,
        components=[
            MetricValue(metric="Periodic Yield", value=result.periodic_yield, unit=Unit.DECIMAL),
            MetricValue(
                metric="Effective Annual Yield",
                value=result.effective_annual_yield,
                unit=Unit.DECIMAL,
            ),
        ],
    )


def _ytm(r: YieldToMaturityRequest) -> MetricBreakdownResponse:
    return _yield_response("Yield to Maturity", calc.yield_to_maturity(_terms(r), r.price))


def _ytc(r: YieldToCallRequest) -> MetricBreakdownResponse:
    result = calc.yield_to_call(_terms(r), r.price, r.call_price, r.years_to_call)
    return _yield_response("Yield to Call", result)


def _duration(r: BondPriceRequest) -> DurationResponse:
    result = calc.duration_and_convexity(_terms(r), r.yield_to_maturity)
    return DurationResponse(
        price=result.price,
        macaulay_duration=result.macaulay_duration,
        modified_duration=result.modified_duration,
        convexity=result.convexity,
        currency=r.currency,
    )


def _credit_spread(r: CreditSpreadRequest) -> MetricBreakdownResponse:
    bond_yield = calc.yield_to_maturity(_terms(r), r.price).annual_yield
    return MetricBreakdownResponse(
        metric="Credit Spread",
        value=calc.yield_spread(bond_yield, r.risk_free_yield),
        unit=Unit.DECIMAL,
        components=[
            MetricValue(metric="Bond Yield to Maturity", value=bond_yield, unit=Unit.DECIMAL),
            MetricValue(metric="Risk-free Yield", value=r.risk_free_yield, unit=Unit.DECIMAL),
        ],
    )


METRIC_ENDPOINTS = (
    MetricEndpoint(
        path="/current-yield",
        metric="Current Yield",
        unit=Unit.DECIMAL,
        summary="Current yield",
        formula="Current Yield = face_value × coupon_rate / price",
        request_model=schemas.CurrentYieldRequest,
        compute=lambda r: calc.current_yield(r.face_value * r.coupon_rate, r.price),
        example={"face_value": 1000.0, "coupon_rate": 0.06, "price": 918.89},
        notes=("Ignores the pull to par; see /ytm for the full yield.",),
    ),
    MetricEndpoint(
        path="/macaulay-duration",
        metric="Macaulay Duration",
        unit=Unit.YEARS,
        summary="Macaulay duration",
        formula="D_mac = Σ t_k × PV(CF_k) / price, t_k = k / coupon_frequency",
        request_model=BondPriceRequest,
        compute=lambda r: (
            calc.duration_and_convexity(_terms(r), r.yield_to_maturity).macaulay_duration
        ),
        example={**BOND_EXAMPLE, "yield_to_maturity": 0.08},
        notes=(COUPON_DATE_NOTE, YIELD_NOTE),
    ),
    MetricEndpoint(
        path="/modified-duration",
        metric="Modified Duration",
        unit=Unit.YEARS,
        summary="Modified duration",
        formula="D_mod = D_mac / (1 + yield_to_maturity / coupon_frequency)",
        request_model=BondPriceRequest,
        compute=lambda r: (
            calc.duration_and_convexity(_terms(r), r.yield_to_maturity).modified_duration
        ),
        example={**BOND_EXAMPLE, "yield_to_maturity": 0.08},
        notes=("Approximate % price change ≈ −D_mod × Δyield.", COUPON_DATE_NOTE, YIELD_NOTE),
    ),
    MetricEndpoint(
        path="/convexity",
        metric="Convexity",
        unit=Unit.NUMBER,
        summary="Convexity (in years²)",
        formula="C = Σ PV(CF_k) × (t_k² + t_k / m) / [price × (1 + y/m)²]",
        request_model=BondPriceRequest,
        compute=lambda r: calc.duration_and_convexity(_terms(r), r.yield_to_maturity).convexity,
        example={**BOND_EXAMPLE, "yield_to_maturity": 0.08},
        notes=(
            "Expressed in years²; Δprice/price ≈ −D_mod × Δy + ½ × C × Δy².",
            COUPON_DATE_NOTE,
            YIELD_NOTE,
        ),
    ),
    MetricEndpoint(
        path="/spread",
        metric="Yield Spread",
        unit=Unit.DECIMAL,
        summary="Yield spread over a benchmark (Spread)",
        formula="Spread = bond_yield − benchmark_yield",
        request_model=schemas.SpreadRequest,
        compute=lambda r: calc.yield_spread(r.bond_yield, r.benchmark_yield),
        example={"bond_yield": 0.0825, "benchmark_yield": 0.0640},
        notes=(
            "Decimal form: multiply by 10,000 for basis points.",
            "Both yields must use the same compounding convention and maturity.",
        ),
    ),
)

CALCULATION_ENDPOINTS = (
    CalculationEndpoint(
        path="/bond-price",
        title="Bond Price",
        summary="Price of a fixed-rate bullet bond (Preço de títulos)",
        formulas=(
            "Price = Σ C / (1 + y/m)^k + face_value / (1 + y/m)^n, k = 1..n",
            "C = face_value × coupon_rate / m, n = years_to_maturity × m",
        ),
        request_model=BondPriceRequest,
        response_model=BondPriceResponse,
        compute=_bond_price,
        examples={
            "semiannual": {**BOND_EXAMPLE, "yield_to_maturity": 0.08},
            "zero_coupon": {
                "face_value": 1000.0,
                "coupon_rate": 0.0,
                "years_to_maturity": 3,
                "coupon_frequency": 1,
                "yield_to_maturity": 0.10,
            },
        },
        notes=(COUPON_DATE_NOTE, YIELD_NOTE),
    ),
    CalculationEndpoint(
        path="/ytm",
        title="Yield to Maturity",
        summary="Yield to maturity (YTM)",
        formulas=(
            "Solve y: price = Σ C / (1 + y/m)^k + face_value / (1 + y/m)^n",
            "effective annual yield = (1 + y/m)^m − 1",
        ),
        request_model=YieldToMaturityRequest,
        response_model=MetricBreakdownResponse,
        compute=_ytm,
        examples={"discount_bond": {**BOND_EXAMPLE, "price": 918.8910422064494}},
        notes=(
            "value is the bond-equivalent annual yield (periodic yield × coupon_frequency).",
            "Solved numerically with Brent's method; the price function is monotonic, so the "
            "yield is unique.",
            COUPON_DATE_NOTE,
        ),
    ),
    CalculationEndpoint(
        path="/ytc",
        title="Yield to Call",
        summary="Yield to call (YTC)",
        formulas=(
            "Solve y: price = Σ C / (1 + y/m)^k + call_price / (1 + y/m)^n_call",
            "n_call = years_to_call × m",
        ),
        request_model=YieldToCallRequest,
        response_model=MetricBreakdownResponse,
        compute=_ytc,
        examples={
            "premium_callable": {
                "face_value": 1000.0,
                "coupon_rate": 0.08,
                "years_to_maturity": 10,
                "coupon_frequency": 2,
                "price": 1100.0,
                "call_price": 1040.0,
                "years_to_call": 5,
            }
        },
        notes=(
            "years_to_call cannot exceed years_to_maturity and must fall on a coupon date.",
            YIELD_NOTE,
        ),
    ),
    CalculationEndpoint(
        path="/duration",
        title="Duration and Convexity",
        summary="Macaulay duration, modified duration and convexity in one call",
        formulas=(
            "D_mac = Σ t_k × PV(CF_k) / price",
            "D_mod = D_mac / (1 + y/m)",
            "C = Σ PV(CF_k) × (t_k² + t_k / m) / [price × (1 + y/m)²]",
        ),
        request_model=BondPriceRequest,
        response_model=DurationResponse,
        compute=_duration,
        examples={"semiannual": {**BOND_EXAMPLE, "yield_to_maturity": 0.08}},
        notes=("Durations in years, convexity in years².", COUPON_DATE_NOTE, YIELD_NOTE),
    ),
    CalculationEndpoint(
        path="/credit-spread",
        title="Credit Spread",
        summary="Credit spread of a bond over the risk-free yield",
        formulas=("Credit Spread = YTM(bond price) − risk_free_yield",),
        request_model=CreditSpreadRequest,
        response_model=MetricBreakdownResponse,
        compute=_credit_spread,
        examples={
            "corporate_bond": {**BOND_EXAMPLE, "price": 918.8910422064494, "risk_free_yield": 0.05}
        },
        notes=(
            "The bond YTM is solved from its price; risk_free_yield must be a government yield "
            "for the same maturity and compounding convention.",
            "Yield spread, not a Z-spread or option-adjusted spread.",
        ),
    ),
)

add_metric_endpoints(router, METRIC_ENDPOINTS)
add_calculation_endpoints(router, CALCULATION_ENDPOINTS)
