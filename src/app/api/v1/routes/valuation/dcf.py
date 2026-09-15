from dataclasses import asdict

from fastapi import APIRouter

from app.api.endpoint_specs import (
    CalculationEndpoint,
    MetricEndpoint,
    add_calculation_endpoints,
    add_metric_endpoints,
)
from app.schemas.common import Unit
from app.schemas.valuation import dcf as schemas
from app.schemas.valuation.dcf import (
    DiscountedCashFlowItem,
    FcfeDcfRequest,
    FcfeDcfResponse,
    FcffDcfRequest,
    FcffDcfResponse,
    PerpetuityGrowthTerminal,
    PresentValueRequest,
    PresentValueResponse,
    TerminalAssumption,
)
from app.services.valuation import dcf as calc
from app.services.valuation import time_value as tv
from app.services.valuation.time_value import DiscountedCashFlow

router = APIRouter(tags=["Valuation · DCF"])

TIMING_NOTE = (
    "Cash flow i occurs at the end of period i (or at i − 0.5 with mid_year_convention); "
    "the terminal value is discounted from the end of the last period."
)
PER_SHARE_NOTE = (
    "value_per_share requires shares_outstanding; margin_of_safety also requires share_price and "
    "is null when value_per_share ≤ 0."
)


def _items(discounted: list[DiscountedCashFlow]) -> list[DiscountedCashFlowItem]:
    return [DiscountedCashFlowItem(**asdict(item)) for item in discounted]


def _present_value(r: PresentValueRequest) -> PresentValueResponse:
    discounted = tv.discount_cash_flows(
        r.cash_flows, r.discount_rate, r.periods, mid_year_convention=r.mid_year_convention
    )
    return PresentValueResponse(
        present_value=sum(item.present_value for item in discounted),
        discounted_cash_flows=_items(discounted),
        currency=r.currency,
    )


def _terminal_value(terminal: TerminalAssumption, final_cash_flow: float, rate: float) -> float:
    if isinstance(terminal, PerpetuityGrowthTerminal):
        return calc.perpetuity_growth_terminal_value(final_cash_flow, rate, terminal.growth_rate)
    return calc.exit_multiple_terminal_value(terminal.terminal_metric, terminal.multiple)


def _per_share(
    equity_value: float, shares: float | None, price: float | None
) -> tuple[float | None, float | None]:
    if shares is None:
        return None, None
    per_share = calc.value_per_share(equity_value, shares)
    if price is None or per_share <= 0:
        return per_share, None
    return per_share, calc.margin_of_safety(per_share, price)


def _fcff_dcf(r: FcffDcfRequest) -> FcffDcfResponse:
    terminal = _terminal_value(r.terminal, r.cash_flows[-1], r.discount_rate)
    result = calc.discounted_valuation(
        r.cash_flows, r.discount_rate, terminal, mid_year_convention=r.mid_year_convention
    )
    enterprise = calc.enterprise_value(
        result.present_value_of_cash_flows, result.present_value_of_terminal_value
    )
    equity = calc.equity_value(enterprise, r.net_debt, r.minority_interest, r.non_operating_assets)
    per_share, safety = _per_share(equity, r.shares_outstanding, r.share_price)
    return FcffDcfResponse(
        enterprise_value=enterprise,
        equity_value=equity,
        present_value_of_cash_flows=result.present_value_of_cash_flows,
        terminal_value=result.terminal_value,
        present_value_of_terminal_value=result.present_value_of_terminal_value,
        terminal_value_percentage=result.terminal_value_percentage,
        value_per_share=per_share,
        margin_of_safety=safety,
        discounted_cash_flows=_items(result.discounted_cash_flows),
        currency=r.currency,
    )


def _fcfe_dcf(r: FcfeDcfRequest) -> FcfeDcfResponse:
    terminal = _terminal_value(r.terminal, r.cash_flows[-1], r.cost_of_equity)
    result = calc.discounted_valuation(
        r.cash_flows, r.cost_of_equity, terminal, mid_year_convention=r.mid_year_convention
    )
    per_share, safety = _per_share(result.total_value, r.shares_outstanding, r.share_price)
    return FcfeDcfResponse(
        equity_value=result.total_value,
        present_value_of_cash_flows=result.present_value_of_cash_flows,
        terminal_value=result.terminal_value,
        present_value_of_terminal_value=result.present_value_of_terminal_value,
        terminal_value_percentage=result.terminal_value_percentage,
        value_per_share=per_share,
        margin_of_safety=safety,
        discounted_cash_flows=_items(result.discounted_cash_flows),
        currency=r.currency,
    )


METRIC_ENDPOINTS = (
    MetricEndpoint(
        path="/future-value",
        metric="Future Value",
        unit=Unit.AMOUNT,
        summary="Future value of a present amount (Valor Futuro)",
        formula="FV = present_value × (1 + rate) ^ periods",
        request_model=schemas.FutureValueRequest,
        compute=lambda r: tv.future_value(r.present_value, r.rate, r.periods),
        example={"present_value": 1000.0, "rate": 0.05, "periods": 10},
        notes=("Discrete compounding once per period; periods may be fractional.",),
    ),
    MetricEndpoint(
        path="/terminal-value/perpetuity-growth",
        metric="Terminal Value (Perpetuity Growth)",
        unit=Unit.AMOUNT,
        summary="Terminal value by the perpetuity growth (Gordon) method",
        formula="TV = final_cash_flow × (1 + growth_rate) / (discount_rate − growth_rate)",
        request_model=schemas.PerpetuityGrowthTerminalValueRequest,
        compute=lambda r: calc.perpetuity_growth_terminal_value(
            r.final_cash_flow, r.discount_rate, r.growth_rate
        ),
        example={"final_cash_flow": 121.0, "discount_rate": 0.10, "growth_rate": 0.02},
        notes=(
            "Value at the end of period n (undiscounted).",
            "discount_rate ≤ growth_rate returns INVALID_INPUT.",
        ),
    ),
    MetricEndpoint(
        path="/terminal-value/exit-multiple",
        metric="Terminal Value (Exit Multiple)",
        unit=Unit.AMOUNT,
        summary="Terminal value by the exit multiple method",
        formula="TV = terminal_metric × multiple",
        request_model=schemas.ExitMultipleTerminalValueRequest,
        compute=lambda r: calc.exit_multiple_terminal_value(r.terminal_metric, r.multiple),
        example={"terminal_metric": 250.0, "multiple": 8.0},
        notes=("Value at the end of period n (undiscounted), e.g. EBITDA_n × EV/EBITDA.",),
    ),
    MetricEndpoint(
        path="/enterprise-value",
        metric="Enterprise Value",
        unit=Unit.AMOUNT,
        summary="Enterprise value from discounted components",
        formula="EV = present_value_of_cash_flows + present_value_of_terminal_value",
        request_model=schemas.EnterpriseValueRequest,
        compute=lambda r: calc.enterprise_value(
            r.present_value_of_cash_flows, r.present_value_of_terminal_value
        ),
        example={
            "present_value_of_cash_flows": 272.73,
            "present_value_of_terminal_value": 1159.09,
        },
        notes=("DCF definition: both inputs must already be present values of FCFF.",),
    ),
    MetricEndpoint(
        path="/equity-value",
        metric="Equity Value",
        unit=Unit.AMOUNT,
        summary="Equity value bridge from enterprise value",
        formula="Equity = enterprise_value − net_debt − minority_interest + non_operating_assets",
        request_model=schemas.EquityValueRequest,
        compute=lambda r: calc.equity_value(
            r.enterprise_value, r.net_debt, r.minority_interest, r.non_operating_assets
        ),
        example={
            "enterprise_value": 1431.82,
            "net_debt": 300.0,
            "minority_interest": 50.0,
            "non_operating_assets": 20.0,
        },
        notes=("minority_interest and non_operating_assets default to 0.",),
    ),
    MetricEndpoint(
        path="/value-per-share",
        metric="Intrinsic Value per Share",
        unit=Unit.AMOUNT,
        summary="Intrinsic value per share (Valor intrínseco por ação)",
        formula="Value per Share = equity_value / shares_outstanding",
        request_model=schemas.ValuePerShareRequest,
        compute=lambda r: calc.value_per_share(r.equity_value, r.shares_outstanding),
        example={"equity_value": 1101.82, "shares_outstanding": 100.0},
        notes=("Use diluted shares for consistency with equity claims.",),
    ),
    MetricEndpoint(
        path="/margin-of-safety",
        metric="Margin of Safety",
        unit=Unit.DECIMAL,
        summary="Margin of safety (Margem de Segurança)",
        formula="MoS = (intrinsic_value − market_price) / intrinsic_value",
        request_model=schemas.MarginOfSafetyRequest,
        compute=lambda r: calc.margin_of_safety(r.intrinsic_value, r.market_price),
        example={"intrinsic_value": 50.0, "market_price": 35.0},
        notes=(
            "Relative to intrinsic value. Negative when the price exceeds the intrinsic value.",
            "intrinsic_value ≤ 0 returns INVALID_INPUT (the ratio would flip sign).",
        ),
    ),
)

DCF_CASH_FLOWS = [100.0, 110.0, 121.0]

CALCULATION_ENDPOINTS = (
    CalculationEndpoint(
        path="/present-value",
        title="Present Value",
        summary="Present value of a series of cash flows (Valor Presente)",
        formulas=("PV = Σ CF_i / (1 + discount_rate) ^ t_i",),
        request_model=PresentValueRequest,
        response_model=PresentValueResponse,
        compute=_present_value,
        examples={
            "end_of_period": {"cash_flows": DCF_CASH_FLOWS, "discount_rate": 0.10},
            "custom_timing": {"cash_flows": [1000.0], "discount_rate": 0.08, "periods": [2.5]},
        },
        notes=(
            "t_i defaults to i (1, 2, ..., n); use periods for custom or fractional timing.",
            "mid_year_convention uses t_i = i − 0.5 and cannot be combined with periods.",
        ),
    ),
    CalculationEndpoint(
        path="/dcf/fcff",
        title="DCF (FCFF)",
        summary="Discounted cash flow valuation of the firm using FCFF and WACC",
        formulas=(
            "EV = Σ FCFF_t / (1 + WACC)^t + TV / (1 + WACC)^n",
            "TV (perpetuity_growth) = FCFF_n × (1 + g) / (WACC − g)",
            "TV (exit_multiple) = terminal_metric × multiple",
            "Equity = EV − net_debt − minority_interest + non_operating_assets",
            "Value per share = Equity / shares_outstanding",
            "Margin of safety = (value_per_share − share_price) / value_per_share",
        ),
        request_model=FcffDcfRequest,
        response_model=FcffDcfResponse,
        compute=_fcff_dcf,
        examples={
            "perpetuity_growth": {
                "cash_flows": DCF_CASH_FLOWS,
                "discount_rate": 0.10,
                "terminal": {"method": "perpetuity_growth", "growth_rate": 0.02},
                "net_debt": 300.0,
                "shares_outstanding": 100.0,
                "share_price": 9.0,
            },
            "exit_multiple_mid_year": {
                "cash_flows": DCF_CASH_FLOWS,
                "discount_rate": 0.10,
                "terminal": {"method": "exit_multiple", "terminal_metric": 250.0, "multiple": 8.0},
                "mid_year_convention": True,
                "net_debt": 300.0,
            },
        },
        notes=(
            "cash_flows are projected FCFF for periods 1..n; discount_rate is the WACC.",
            TIMING_NOTE,
            "terminal_value_percentage = PV(TV) / EV (null when EV is 0).",
            PER_SHARE_NOTE,
        ),
    ),
    CalculationEndpoint(
        path="/dcf/fcfe",
        title="DCF (FCFE)",
        summary="Discounted cash flow valuation of equity using FCFE and the cost of equity",
        formulas=(
            "Equity = Σ FCFE_t / (1 + Ke)^t + TV / (1 + Ke)^n",
            "TV (perpetuity_growth) = FCFE_n × (1 + g) / (Ke − g)",
            "TV (exit_multiple) = terminal_metric × multiple",
            "Value per share = Equity / shares_outstanding",
        ),
        request_model=FcfeDcfRequest,
        response_model=FcfeDcfResponse,
        compute=_fcfe_dcf,
        examples={
            "perpetuity_growth": {
                "cash_flows": [80.0, 88.0, 96.8],
                "cost_of_equity": 0.12,
                "terminal": {"method": "perpetuity_growth", "growth_rate": 0.03},
                "shares_outstanding": 100.0,
                "share_price": 8.0,
            },
        },
        notes=(
            "cash_flows are projected FCFE for periods 1..n; no net debt adjustment is applied "
            "because FCFE is already after debt holders.",
            TIMING_NOTE,
            "terminal_value_percentage = PV(TV) / equity value (null when equity value is 0).",
            PER_SHARE_NOTE,
        ),
    ),
)

add_metric_endpoints(router, METRIC_ENDPOINTS)
add_calculation_endpoints(router, CALCULATION_ENDPOINTS)
