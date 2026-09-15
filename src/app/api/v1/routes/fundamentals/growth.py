from fastapi import APIRouter

from app.api.metric_endpoint import MetricEndpoint, add_metric_endpoints
from app.schemas.common import Unit
from app.schemas.fundamentals import growth as schemas
from app.services.fundamentals import growth as calc

router = APIRouter(tags=["Fundamentals · Growth"])

GROWTH_NOTES = (
    "Uses |previous_value| as the base so the sign stays meaningful for negative bases: "
    "from −100 to −50 is +0.50.",
    "previous_value = 0 returns DIVISION_BY_ZERO.",
)


def _growth_endpoint(
    path: str, metric: str, summary: str, current: float, previous: float
) -> MetricEndpoint[schemas.GrowthRequest]:
    return MetricEndpoint(
        path=path,
        metric=metric,
        unit=Unit.DECIMAL,
        summary=summary,
        formula="growth = (current_value − previous_value) / |previous_value|",
        request_model=schemas.GrowthRequest,
        compute=lambda r: calc.growth_rate(r.current_value, r.previous_value),
        example={"current_value": current, "previous_value": previous},
        notes=GROWTH_NOTES,
    )


ENDPOINTS = (
    _growth_endpoint(
        "/revenue-growth",
        "Revenue Growth",
        "Revenue growth (crescimento da receita)",
        1100.0,
        1000.0,
    ),
    _growth_endpoint(
        "/ebitda-growth", "EBITDA Growth", "EBITDA growth (crescimento do EBITDA)", 270.0, 250.0
    ),
    _growth_endpoint(
        "/ebit-growth", "EBIT Growth", "EBIT growth (crescimento do EBIT)", 198.0, 180.0
    ),
    _growth_endpoint(
        "/net-income-growth",
        "Net Income Growth",
        "Net income growth (crescimento do lucro)",
        150.0,
        120.0,
    ),
    _growth_endpoint("/eps-growth", "EPS Growth", "EPS growth (crescimento do EPS)", 4.62, 4.20),
    _growth_endpoint(
        "/fcf-growth", "FCF Growth", "Free cash flow growth (crescimento do FCF)", 81.0, 90.0
    ),
    MetricEndpoint(
        path="/cagr",
        metric="CAGR",
        unit=Unit.DECIMAL,
        summary="Compound annual growth rate",
        formula="CAGR = (ending_value / beginning_value) ^ (1 / years) − 1",
        request_model=schemas.CagrRequest,
        compute=lambda r: calc.cagr(r.beginning_value, r.ending_value, r.years),
        example={"beginning_value": 100.0, "ending_value": 200.0, "years": 5},
        notes=(
            "beginning_value and ending_value must be > 0 (INVALID_INPUT otherwise): the "
            "real-valued root is undefined across a sign change.",
            "years accepts fractions (e.g. 2.5).",
        ),
    ),
    MetricEndpoint(
        path="/sustainable-growth-rate",
        metric="Sustainable Growth Rate",
        unit=Unit.DECIMAL,
        summary="Sustainable growth rate",
        formula="SGR = return_on_equity × retention_ratio",
        request_model=schemas.SustainableGrowthRequest,
        compute=lambda r: calc.sustainable_growth_rate(r.return_on_equity, r.retention_ratio),
        example={"return_on_equity": 0.18, "retention_ratio": 0.60},
        notes=("Assumes constant ROE, payout and capital structure.",),
    ),
    MetricEndpoint(
        path="/retention-ratio",
        metric="Retention Ratio",
        unit=Unit.DECIMAL,
        summary="Earnings retention ratio",
        formula="Retention = (net_income − dividends_paid) / net_income",
        request_model=schemas.RetentionRatioRequest,
        compute=lambda r: calc.retention_ratio(r.net_income, r.dividends_paid),
        example={"net_income": 200.0, "dividends_paid": 50.0},
        notes=("Equals 1 − dividend payout ratio.",),
    ),
    MetricEndpoint(
        path="/reinvestment-rate",
        metric="Reinvestment Rate",
        unit=Unit.DECIMAL,
        summary="Reinvestment rate",
        formula="Reinvestment Rate = (capex − D&A + ΔNWC) / (ebit × (1 − tax_rate))",
        request_model=schemas.ReinvestmentRateRequest,
        compute=lambda r: calc.reinvestment_rate(
            r.capital_expenditures,
            r.depreciation_amortization,
            r.change_in_working_capital,
            r.ebit,
            r.tax_rate,
        ),
        example={
            "capital_expenditures": 150.0,
            "depreciation_amortization": 50.0,
            "change_in_working_capital": 20.0,
            "ebit": 300.0,
            "tax_rate": 0.34,
        },
        notes=("Damodaran definition: net capex plus working capital investment over NOPAT.",),
    ),
)

add_metric_endpoints(router, ENDPOINTS)
