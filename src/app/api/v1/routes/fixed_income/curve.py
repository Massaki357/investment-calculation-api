from dataclasses import asdict

from fastapi import APIRouter

from app.api.endpoint_specs import (
    CalculationEndpoint,
    MetricEndpoint,
    add_calculation_endpoints,
    add_metric_endpoints,
)
from app.schemas.common import MetricBreakdownResponse, MetricValue, Unit
from app.schemas.fixed_income import curve as schemas
from app.schemas.fixed_income.cash_flows import IrrRequest
from app.schemas.fixed_income.curve import SpotCurveRequest, SpotCurveResponse, SpotPointItem
from app.services.fixed_income import cash_flows, curve, rates

router = APIRouter(tags=["Fixed Income · Yield curve and cash flows"])


def _spot_curve(r: SpotCurveRequest) -> SpotCurveResponse:
    instruments = [
        curve.CurveInstrument(
            maturity_years=item.maturity_years,
            coupon_rate=item.coupon_rate,
            price=item.price,
            face_value=item.face_value,
        )
        for item in r.instruments
    ]
    points = curve.bootstrap_spot_curve(instruments, r.coupon_frequency)
    return SpotCurveResponse(points=[SpotPointItem(**asdict(point)) for point in points])


def _irr(r: IrrRequest) -> MetricBreakdownResponse:
    irr = cash_flows.internal_rate_of_return(r.cash_flows)
    components = []
    if r.periods_per_year is not None:
        components.append(
            MetricValue(
                metric="Effective Annual IRR",
                value=rates.convert_effective_rate(irr, 1 / r.periods_per_year, 1.0),
                unit=Unit.DECIMAL,
            )
        )
    return MetricBreakdownResponse(
        metric="IRR", value=irr, unit=Unit.DECIMAL, components=components
    )


METRIC_ENDPOINTS = (
    MetricEndpoint(
        path="/forward-rate",
        metric="Forward Rate",
        unit=Unit.DECIMAL,
        summary="Implied forward rate between two maturities (Forward Rate)",
        formula="f = [(1 + long_spot_rate)^long_maturity / (1 + short_spot_rate)^short_maturity]"
        "^(1 / (long_maturity − short_maturity)) − 1",
        request_model=schemas.ForwardRateRequest,
        compute=lambda r: curve.forward_rate(
            r.short_spot_rate, r.short_maturity, r.long_spot_rate, r.long_maturity
        ),
        example={
            "short_spot_rate": 0.05,
            "short_maturity": 1,
            "long_spot_rate": 0.06,
            "long_maturity": 2,
        },
        notes=(
            "Spot and forward rates are effective annual rates; maturities in years.",
            "long_maturity ≤ short_maturity returns INVALID_INPUT.",
        ),
    ),
)

CALCULATION_ENDPOINTS = (
    CalculationEndpoint(
        path="/spot-rates",
        title="Spot Curve",
        summary="Spot rates bootstrapped from coupon bond prices (Spot Rate)",
        formulas=(
            "d_k = (price_k − c_k × Σ_{j<k} d_j) / (c_k + face_value_k)",
            "spot_k = d_k^(−1 / t_k) − 1, t_k = k / coupon_frequency",
        ),
        request_model=SpotCurveRequest,
        response_model=SpotCurveResponse,
        compute=_spot_curve,
        examples={
            "annual_par_bonds": {
                "coupon_frequency": 1,
                "instruments": [
                    {"maturity_years": 1, "coupon_rate": 0.05, "price": 100.0},
                    {"maturity_years": 2, "coupon_rate": 0.06, "price": 100.0},
                    {"maturity_years": 3, "coupon_rate": 0.07, "price": 100.0},
                ],
            }
        },
        notes=(
            "Exactly one instrument per coupon date 1/m, 2/m, ..., n/m (any order).",
            "Spot rates are effective annual rates. Prices implying a non-positive discount "
            "factor return INVALID_INPUT.",
        ),
    ),
    CalculationEndpoint(
        path="/irr",
        title="IRR",
        summary="Internal rate of return (TIR)",
        formulas=(
            "Solve r: Σ CF_t / (1 + r)^t = 0, t = 0..n",
            "effective annual IRR = (1 + r)^periods_per_year − 1",
        ),
        request_model=IrrRequest,
        response_model=MetricBreakdownResponse,
        compute=_irr,
        examples={
            "project": {"cash_flows": [-1000.0, 300.0, 400.0, 500.0]},
            "monthly_flows": {
                "cash_flows": [-1000.0, 200.0, 200.0, 200.0, 200.0, 250.0],
                "periods_per_year": 12,
            },
        },
        notes=(
            "value is the IRR per period of the cash flow series.",
            "Exactly one sign change guarantees a unique IRR. With several sign changes all real "
            "roots are computed; if more than one exists the request returns INVALID_INPUT with "
            "details.irr_candidates.",
            "Cash flows without both positive and negative values return INVALID_INPUT.",
        ),
    ),
)

add_metric_endpoints(router, METRIC_ENDPOINTS)
add_calculation_endpoints(router, CALCULATION_ENDPOINTS)
