from typing import cast

from fastapi import APIRouter

from app.api.endpoint_specs import (
    CalculationEndpoint,
    MetricEndpoint,
    add_calculation_endpoints,
    add_metric_endpoints,
)
from app.schemas.common import MetricValue, Unit
from app.schemas.valuation import cost_of_capital as schemas
from app.schemas.valuation.cost_of_capital import CostOfDebtMethod, WaccRequest, WaccResponse
from app.services.valuation import cost_of_capital as calc

router = APIRouter(tags=["Valuation · Cost of capital"])

PREMIUM_NOTE = (
    "Send market_risk_premium, or expected_market_return (premium = expected_market_return − "
    "risk_free_rate), not both."
)
HAMADA_NOTE = "Hamada relationship: assumes debt beta of zero and a constant D/E."


def _premium(r: schemas.CapmRequest | schemas.CostOfEquityRequest) -> float:
    # The request validator guarantees exactly one premium source is present.
    if r.market_risk_premium is not None:
        return r.market_risk_premium
    return calc.market_risk_premium(cast(float, r.expected_market_return), r.risk_free_rate)


def _cost_of_debt(r: schemas.CostOfDebtRequest) -> float:
    # The request validator guarantees the fields of the chosen method are present.
    if r.method is CostOfDebtMethod.INTEREST_OVER_DEBT:
        return calc.cost_of_debt_from_interest(
            cast(float, r.interest_expense), cast(float, r.total_debt)
        )
    return calc.cost_of_debt_from_spread(
        cast(float, r.risk_free_rate), cast(float, r.credit_spread)
    )


def _wacc(r: WaccRequest) -> WaccResponse:
    result = calc.wacc(
        r.equity_value, r.debt_value, r.cost_of_equity, r.pre_tax_cost_of_debt, r.tax_rate
    )
    return WaccResponse(
        metric="WACC",
        value=result.wacc,
        unit=Unit.DECIMAL,
        components=[
            MetricValue(metric="Equity Weight", value=result.equity_weight, unit=Unit.DECIMAL),
            MetricValue(metric="Debt Weight", value=result.debt_weight, unit=Unit.DECIMAL),
            MetricValue(metric="Cost of Equity", value=r.cost_of_equity, unit=Unit.DECIMAL),
            MetricValue(
                metric="After-tax Cost of Debt",
                value=result.after_tax_cost_of_debt,
                unit=Unit.DECIMAL,
            ),
        ],
    )


METRIC_ENDPOINTS = (
    MetricEndpoint(
        path="/capm",
        metric="CAPM Expected Return",
        unit=Unit.DECIMAL,
        summary="Capital asset pricing model",
        formula="E(R) = risk_free_rate + beta × market_risk_premium",
        request_model=schemas.CapmRequest,
        compute=lambda r: calc.capm(r.risk_free_rate, r.beta, _premium(r)),
        example={"risk_free_rate": 0.04, "beta": 1.2, "market_risk_premium": 0.055},
        notes=(PREMIUM_NOTE,),
    ),
    MetricEndpoint(
        path="/levered-beta",
        metric="Levered Beta",
        unit=Unit.NUMBER,
        summary="Levered beta (Beta alavancado)",
        formula="βL = βU × [1 + (1 − tax_rate) × debt_to_equity]",
        request_model=schemas.LeveredBetaRequest,
        compute=lambda r: calc.levered_beta(r.unlevered_beta, r.tax_rate, r.debt_to_equity),
        example={"unlevered_beta": 0.8, "tax_rate": 0.34, "debt_to_equity": 0.5},
        notes=(HAMADA_NOTE,),
    ),
    MetricEndpoint(
        path="/unlevered-beta",
        metric="Unlevered Beta",
        unit=Unit.NUMBER,
        summary="Unlevered beta (Beta desalavancado)",
        formula="βU = βL / [1 + (1 − tax_rate) × debt_to_equity]",
        request_model=schemas.UnleveredBetaRequest,
        compute=lambda r: calc.unlevered_beta(r.levered_beta, r.tax_rate, r.debt_to_equity),
        example={"levered_beta": 1.064, "tax_rate": 0.34, "debt_to_equity": 0.5},
        notes=(HAMADA_NOTE,),
    ),
    MetricEndpoint(
        path="/cost-of-equity",
        metric="Cost of Equity",
        unit=Unit.DECIMAL,
        summary="Cost of equity (CAPM build-up)",
        formula="Ke = risk_free_rate + beta × market_risk_premium + country_risk_premium "
        "+ size_premium + specific_risk_premium",
        request_model=schemas.CostOfEquityRequest,
        compute=lambda r: calc.cost_of_equity(
            r.risk_free_rate,
            r.beta,
            _premium(r),
            r.country_risk_premium,
            r.size_premium,
            r.specific_risk_premium,
        ),
        example={
            "risk_free_rate": 0.04,
            "beta": 1.2,
            "market_risk_premium": 0.055,
            "country_risk_premium": 0.02,
            "size_premium": 0.01,
        },
        notes=(PREMIUM_NOTE, "Additional premia default to 0, reducing Ke to the plain CAPM."),
    ),
    MetricEndpoint(
        path="/cost-of-debt",
        metric="Cost of Debt",
        unit=Unit.DECIMAL,
        summary="Pre-tax cost of debt",
        formula="risk_free_plus_spread: Kd = risk_free_rate + credit_spread · "
        "interest_over_debt: Kd = interest_expense / total_debt",
        request_model=schemas.CostOfDebtRequest,
        compute=_cost_of_debt,
        example={"risk_free_rate": 0.04, "credit_spread": 0.02},
        notes=(
            "Default method is risk_free_plus_spread (market-based).",
            "interest_over_debt is an accounting approximation; prefer average debt.",
        ),
    ),
    MetricEndpoint(
        path="/after-tax-cost-of-debt",
        metric="After-tax Cost of Debt",
        unit=Unit.DECIMAL,
        summary="After-tax cost of debt",
        formula="Kd after tax = pre_tax_cost_of_debt × (1 − tax_rate)",
        request_model=schemas.AfterTaxCostOfDebtRequest,
        compute=lambda r: calc.after_tax_cost_of_debt(r.pre_tax_cost_of_debt, r.tax_rate),
        example={"pre_tax_cost_of_debt": 0.08, "tax_rate": 0.34},
        notes=("Assumes interest is fully tax deductible.",),
    ),
)

CALCULATION_ENDPOINTS = (
    CalculationEndpoint(
        path="/wacc",
        title="WACC",
        summary="Weighted average cost of capital",
        formulas=(
            "WACC = E / (D + E) × cost_of_equity + D / (D + E) × pre_tax_cost_of_debt "
            "× (1 − tax_rate)",
        ),
        request_model=WaccRequest,
        response_model=WaccResponse,
        compute=_wacc,
        examples={
            "wacc": {
                "equity_value": 600.0,
                "debt_value": 400.0,
                "cost_of_equity": 0.12,
                "pre_tax_cost_of_debt": 0.08,
                "tax_rate": 0.34,
            }
        },
        notes=(
            "Use market values of equity and debt for the weights.",
            "equity_value + debt_value = 0 returns DIVISION_BY_ZERO.",
        ),
    ),
)

add_metric_endpoints(router, METRIC_ENDPOINTS)
add_calculation_endpoints(router, CALCULATION_ENDPOINTS)
