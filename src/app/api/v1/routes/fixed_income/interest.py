from typing import cast

from fastapi import APIRouter

from app.api.endpoint_specs import (
    CalculationEndpoint,
    MetricEndpoint,
    add_calculation_endpoints,
    add_metric_endpoints,
)
from app.schemas.common import Unit
from app.schemas.fixed_income import interest as schemas
from app.schemas.fixed_income.interest import (
    Compounding,
    CompoundInterestRequest,
    InterestResponse,
    RateCompounding,
    RateConversionRequest,
    RatePeriod,
    RealRateMethod,
    SimpleInterestRequest,
)
from app.services.fixed_income import interest as calc
from app.services.fixed_income import rates

router = APIRouter(tags=["Fixed Income · Interest and rates"])

RATE_NOTE = "rate is an annual decimal rate; years may be fractional."


def growth_factor(compounding: Compounding, rate: float, years: float, frequency: int) -> float:
    if compounding is Compounding.SIMPLE:
        return calc.simple_growth_factor(rate, years)
    if compounding is Compounding.CONTINUOUS:
        return calc.continuous_growth_factor(rate, years)
    return calc.periodic_growth_factor(rate, years, frequency)


def _simple_interest(r: SimpleInterestRequest) -> InterestResponse:
    interest, future = calc.interest_amount(r.principal, calc.simple_growth_factor(r.rate, r.years))
    return InterestResponse(
        metric="Simple Interest",
        principal=r.principal,
        interest=interest,
        future_value=future,
        currency=r.currency,
    )


def _compound_interest(r: CompoundInterestRequest) -> InterestResponse:
    if r.compounding is RateCompounding.CONTINUOUS:
        factor = calc.continuous_growth_factor(r.rate, r.years)
    else:
        factor = calc.periodic_growth_factor(r.rate, r.years, r.compounding_frequency)
    interest, future = calc.interest_amount(r.principal, factor)
    return InterestResponse(
        metric="Compound Interest",
        principal=r.principal,
        interest=interest,
        future_value=future,
        currency=r.currency,
    )


def _effective_rate(r: schemas.EffectiveRateRequest) -> float:
    if r.compounding is RateCompounding.CONTINUOUS:
        return rates.effective_from_continuous(r.nominal_rate)
    # The request validator requires compounding_frequency for periodic compounding.
    return rates.effective_from_nominal(r.nominal_rate, cast(int, r.compounding_frequency))


def _real_rate(r: schemas.RealRateRequest) -> float:
    if r.method is RealRateMethod.APPROXIMATE:
        return rates.real_rate_approximate(r.nominal_rate, r.inflation_rate)
    return rates.real_rate_exact(r.nominal_rate, r.inflation_rate)


def _period_in_years(period: RatePeriod, r: RateConversionRequest) -> float:
    return {
        RatePeriod.DAY: 1 / r.days_per_year,
        RatePeriod.BUSINESS_DAY: 1 / r.business_days_per_year,
        RatePeriod.MONTH: 1 / 12,
        RatePeriod.QUARTER: 1 / 4,
        RatePeriod.SEMESTER: 1 / 2,
        RatePeriod.YEAR: 1.0,
    }[period]


def _convert_rate(r: RateConversionRequest) -> float:
    return rates.convert_effective_rate(
        r.rate, _period_in_years(r.from_period, r), _period_in_years(r.to_period, r)
    )


METRIC_ENDPOINTS = (
    MetricEndpoint(
        path="/future-value",
        metric="Future Value",
        unit=Unit.AMOUNT,
        summary="Future value with simple, periodic or continuous compounding (Valor Futuro)",
        formula="FV = present_value × growth_factor(compounding, rate, years)",
        request_model=schemas.FutureValueRequest,
        compute=lambda r: (
            r.present_value * growth_factor(r.compounding, r.rate, r.years, r.compounding_frequency)
        ),
        example={
            "present_value": 1000.0,
            "rate": 0.12,
            "years": 1,
            "compounding": "periodic",
            "compounding_frequency": 12,
        },
        notes=(RATE_NOTE, schemas.COMPOUNDING_DESCRIPTION),
    ),
    MetricEndpoint(
        path="/present-value",
        metric="Present Value",
        unit=Unit.AMOUNT,
        summary="Present value with simple, periodic or continuous compounding (Valor Presente)",
        formula="PV = future_value / growth_factor(compounding, rate, years)",
        request_model=schemas.PresentValueRequest,
        compute=lambda r: calc.discount(
            r.future_value, growth_factor(r.compounding, r.rate, r.years, r.compounding_frequency)
        ),
        example={
            "future_value": 1126.825030131969,
            "rate": 0.12,
            "years": 1,
            "compounding": "periodic",
            "compounding_frequency": 12,
        },
        notes=(RATE_NOTE, schemas.COMPOUNDING_DESCRIPTION),
    ),
    MetricEndpoint(
        path="/nominal-rate",
        metric="Nominal Annual Rate",
        unit=Unit.DECIMAL,
        summary="Nominal annual rate equivalent to an effective annual rate (Taxa Nominal)",
        formula="nominal = m × [(1 + effective_rate)^(1/m) − 1]",
        request_model=schemas.NominalRateRequest,
        compute=lambda r: rates.nominal_from_effective(r.effective_rate, r.compounding_frequency),
        example={"effective_rate": 0.12682503013196977, "compounding_frequency": 12},
        notes=("m = compounding_frequency (periods per year).",),
    ),
    MetricEndpoint(
        path="/effective-rate",
        metric="Effective Annual Rate",
        unit=Unit.DECIMAL,
        summary="Effective annual rate from a nominal rate (Taxa Efetiva)",
        formula="periodic: (1 + nominal / m)^m − 1 · continuous: e^nominal − 1",
        request_model=schemas.EffectiveRateRequest,
        compute=_effective_rate,
        example={"nominal_rate": 0.12, "compounding": "periodic", "compounding_frequency": 12},
        notes=("compounding_frequency is required for periodic and rejected for continuous.",),
    ),
    MetricEndpoint(
        path="/real-rate",
        metric="Real Rate",
        unit=Unit.DECIMAL,
        summary="Real interest rate (Taxa Real, Fisher equation)",
        formula="exact: (1 + nominal_rate) / (1 + inflation_rate) − 1 · "
        "approximate: nominal_rate − inflation_rate",
        request_model=schemas.RealRateRequest,
        compute=_real_rate,
        example={"nominal_rate": 0.10, "inflation_rate": 0.04},
        notes=("Both rates must refer to the same period. Default method: exact.",),
    ),
    MetricEndpoint(
        path="/rate-conversion",
        metric="Equivalent Rate",
        unit=Unit.DECIMAL,
        summary="Equivalent compound rate between periods (Conversão de taxas)",
        formula="rate_to = (1 + rate)^(to_period_years / from_period_years) − 1",
        request_model=RateConversionRequest,
        compute=_convert_rate,
        example={"rate": 0.1365, "from_period": "year", "to_period": "business_day"},
        notes=(
            "Period lengths in years: day = 1/days_per_year (365 or 360), "
            "business_day = 1/business_days_per_year (252), month = 1/12, quarter = 1/4, "
            "semester = 1/2, year = 1.",
            "rate must be effective for from_period (compound equivalence).",
        ),
    ),
)

CALCULATION_ENDPOINTS = (
    CalculationEndpoint(
        path="/simple-interest",
        title="Simple Interest",
        summary="Simple interest (Juros Simples)",
        formulas=("interest = principal × rate × years", "FV = principal + interest"),
        request_model=SimpleInterestRequest,
        response_model=InterestResponse,
        compute=_simple_interest,
        examples={"simple": {"principal": 1000.0, "rate": 0.12, "years": 2}},
        notes=(RATE_NOTE,),
    ),
    CalculationEndpoint(
        path="/compound-interest",
        title="Compound Interest",
        summary="Compound interest (Juros Compostos)",
        formulas=(
            "periodic: FV = principal × (1 + rate / m)^(m × years)",
            "continuous: FV = principal × e^(rate × years)",
            "interest = FV − principal",
        ),
        request_model=CompoundInterestRequest,
        response_model=InterestResponse,
        compute=_compound_interest,
        examples={
            "monthly": {
                "principal": 1000.0,
                "rate": 0.12,
                "years": 1,
                "compounding_frequency": 12,
            },
            "continuous": {
                "principal": 1000.0,
                "rate": 0.12,
                "years": 1,
                "compounding": "continuous",
            },
        },
        notes=(RATE_NOTE, "compounding_frequency defaults to 1 and is ignored for continuous."),
    ),
)

add_metric_endpoints(router, METRIC_ENDPOINTS)
add_calculation_endpoints(router, CALCULATION_ENDPOINTS)
