"""Scenario routes: /api/v1/scenarios/*."""

import itertools
import math

from fastapi import APIRouter
from pydantic import BaseModel

from app.api.endpoint_specs import CalculationEndpoint, add_calculation_endpoints
from app.api.model_registry import Evaluation, ModelRegistry, with_overrides
from app.api.v1.routes import (
    fixed_income,
    fundamentals,
    portfolio,
    risk,
    statistics,
    technical,
    valuation,
)
from app.core.config import current_settings
from app.core.exceptions import InvalidInputError, LimitExceededError
from app.schemas.scenarios import (
    CellError,
    DistributionStats,
    LossMeasure,
    MonteCarloRequest,
    MonteCarloResponse,
    PercentileValue,
    ScenarioAnalysisRequest,
    ScenarioAnalysisResponse,
    ScenarioOutcome,
    SensitivityPoint,
    SensitivityRequest,
    SensitivityResponse,
    StressPositionResult,
    StressScenarioResult,
    StressTestRequest,
    StressTestResponse,
)
from app.services.scenarios import analysis, monte_carlo
from app.services.scenarios.monte_carlo import DistributionSummary

MAX_GRID_POINTS = 2_500

registry = ModelRegistry()
for _domain, _module in (
    ("fundamentals", fundamentals),
    ("valuation", valuation),
    ("fixed-income", fixed_income),
    ("risk", risk),
    ("statistics", statistics),
    ("portfolio", portfolio),
    ("technical", technical),
):
    registry.register_domain(_domain, (*_module.METRIC_ENDPOINTS, *_module.CALCULATION_ENDPOINTS))

router = APIRouter(prefix="/scenarios", tags=["Scenarios"])


class RegisteredModelInfo(BaseModel):
    model: str
    title: str


@router.get(
    "/models",
    response_model=list[RegisteredModelInfo],
    summary="Registered models",
    description="Calculations that sensitivity and scenario analysis can evaluate. Use the model "
    "id in `model`, and the same request body as the original endpoint in `base_inputs`.",
)
def list_models() -> list[RegisteredModelInfo]:
    return [RegisteredModelInfo(model=m.model_id, title=m.title) for m in registry.models]


def _cell_error(evaluation: Evaluation) -> CellError | None:
    if evaluation.error_code is None:
        return None
    return CellError(code=evaluation.error_code, message=evaluation.error_message or "")


def _require_base(model: str, base_inputs: dict, output: str) -> Evaluation:
    base = registry.evaluate(model, base_inputs, output)
    if base.error_code is not None:
        raise InvalidInputError(
            f"base_inputs are not valid for model '{model}': {base.error_message}",
            details={"code": base.error_code},
        )
    return base


# --- Sensitivity -------------------------------------------------------------------------------


def _sensitivity(r: SensitivityRequest) -> SensitivityResponse:
    grid_size = math.prod(len(variable.values) for variable in r.variables)
    if grid_size > MAX_GRID_POINTS:
        raise LimitExceededError(f"the grid has {grid_size} points; the limit is {MAX_GRID_POINTS}")
    base = _require_base(r.model, r.base_inputs, r.output)

    points: list[SensitivityPoint] = []
    for combination in itertools.product(*(variable.values for variable in r.variables)):
        overrides = {
            variable.name: value for variable, value in zip(r.variables, combination, strict=True)
        }
        evaluation = registry.evaluate(r.model, with_overrides(r.base_inputs, overrides), r.output)
        points.append(
            SensitivityPoint(
                inputs=overrides, output=evaluation.output, error=_cell_error(evaluation)
            )
        )

    table = None
    if len(r.variables) == 2:
        columns = len(r.variables[1].values)
        outputs = [point.output for point in points]
        table = [
            outputs[row * columns : (row + 1) * columns]
            for row in range(len(r.variables[0].values))
        ]
    return SensitivityResponse(
        model=r.model,
        output=r.output,
        base_output=base.output,
        variables=r.variables,
        points=points,
        table=table,
    )


# --- Scenario analysis -------------------------------------------------------------------------


def _scenario_analysis(r: ScenarioAnalysisRequest) -> ScenarioAnalysisResponse:
    _require_base(r.model, r.base_inputs, r.output)
    evaluations = [
        registry.evaluate(r.model, with_overrides(r.base_inputs, scenario.overrides), r.output)
        for scenario in r.scenarios
    ]
    outputs = [evaluation.output for evaluation in evaluations]
    base_output = next(
        (
            out
            for scenario, out in zip(r.scenarios, outputs, strict=True)
            if scenario.name == "base"
        ),
        None,
    )

    weighted = None
    probabilities = [scenario.probability for scenario in r.scenarios]
    if all(p is not None for p in probabilities) and all(out is not None for out in outputs):
        weighted = analysis.probability_weighted_value(
            [float(out) for out in outputs if out is not None],
            [float(p) for p in probabilities if p is not None],
        )

    valid = [out for out in outputs if out is not None]
    return ScenarioAnalysisResponse(
        model=r.model,
        output=r.output,
        scenarios=[
            ScenarioOutcome(
                name=scenario.name,
                probability=scenario.probability,
                output=evaluation.output,
                difference_from_base=None
                if evaluation.output is None or base_output is None
                else evaluation.output - base_output,
                error=_cell_error(evaluation),
            )
            for scenario, evaluation in zip(r.scenarios, evaluations, strict=True)
        ],
        probability_weighted_output=weighted,
        minimum_output=min(valid) if valid else None,
        maximum_output=max(valid) if valid else None,
    )


# --- Stress testing ----------------------------------------------------------------------------


def _stress_test(r: StressTestRequest) -> StressTestResponse:
    positions = [
        analysis.Position(
            name=position.name,
            exposure=position.exposure,
            sensitivities=position.sensitivities
            if position.sensitivities is not None
            else {position.name: 1.0},
        )
        for position in r.positions
    ]
    results = [analysis.stress_test(positions, s.name, s.shocks) for s in r.scenarios]
    worst = min(results, key=lambda result: result.total_pnl)
    return StressTestResponse(
        scenarios=[
            StressScenarioResult(
                scenario=result.scenario,
                total_exposure=result.total_exposure,
                total_pnl=result.total_pnl,
                value_after=result.value_after,
                return_on_gross_exposure=result.return_on_gross_exposure,
                positions=[
                    StressPositionResult(
                        name=item.name,
                        exposure=item.exposure,
                        shock_return=item.shock_return,
                        pnl=item.pnl,
                    )
                    for item in result.positions
                ],
            )
            for result in results
        ],
        worst_scenario=worst.scenario,
        worst_pnl=worst.total_pnl,
        currency=r.currency,
    )


# --- Monte Carlo -------------------------------------------------------------------------------


def _stats(summary: DistributionSummary) -> DistributionStats:
    return DistributionStats(
        mean=summary.mean,
        standard_deviation=summary.standard_deviation,
        minimum=summary.minimum,
        maximum=summary.maximum,
        percentiles=[
            PercentileValue(percentile=rank, value=value) for rank, value in summary.percentiles
        ],
    )


def _monte_carlo(r: MonteCarloRequest) -> MonteCarloResponse:
    result = monte_carlo.simulate_gbm(
        r.initial_value,
        r.expected_return,
        r.volatility,
        r.periods,
        r.simulations,
        periods_per_year=r.periods_per_year,
        seed=r.seed,
        max_cells=current_settings().max_monte_carlo_cells,
        sample_paths=r.sample_paths,
    )
    finals = result.final_values
    losses = monte_carlo.tail_loss(finals, r.initial_value, r.confidence)
    return MonteCarloResponse(
        seed_used=result.seed_used,
        simulations=r.simulations,
        periods=r.periods,
        horizon_years=result.horizon_years,
        final_value=_stats(monte_carlo.summarize(finals, r.percentiles)),
        simulated_mean_return=float(finals.mean()) / r.initial_value - 1,
        probability_of_loss=float((finals < r.initial_value).mean()),
        confidence=r.confidence,
        value_at_risk=LossMeasure(
            amount=losses.value_at_risk, decimal=losses.value_at_risk / r.initial_value
        ),
        expected_shortfall=LossMeasure(
            amount=losses.expected_shortfall, decimal=losses.expected_shortfall / r.initial_value
        ),
        max_drawdown=_stats(monte_carlo.summarize(result.max_drawdowns, r.percentiles)),
        theoretical_mean_final_value=result.theoretical_mean_final_value,
        theoretical_median_final_value=result.theoretical_median_final_value,
        sample_paths=result.sample_paths,
        currency=r.currency,
    )


# --- Endpoint specifications -------------------------------------------------------------------

GORDON_BASE = {"current_dividend": 2.0, "cost_of_equity": 0.10, "growth_rate": 0.05}
DCF_BASE = {
    "cash_flows": [100.0, 110.0, 121.0],
    "discount_rate": 0.10,
    "terminal": {"method": "perpetuity_growth", "growth_rate": 0.02},
    "net_debt": 300.0,
    "shares_outstanding": 100.0,
}
SAFETY_NOTE = (
    "Only calculations registered in this API can be evaluated (GET /api/v1/scenarios/models); "
    "no formula or code is accepted."
)
CELL_NOTE = (
    "A combination that is invalid for the model (e.g. growth ≥ discount rate) has a null output "
    "and an error code instead of failing the whole request; invalid base_inputs return 400."
)

CALCULATION_ENDPOINTS = (
    CalculationEndpoint(
        path="/sensitivity-analysis",
        title="Sensitivity Analysis",
        summary="One- or two-variable sensitivity of a registered model (análise de sensibilidade)",
        formulas=(
            "output(v1) for each value of one variable, or output(v1, v2) over the grid of two",
            "all other inputs fixed at base_inputs",
        ),
        request_model=SensitivityRequest,
        response_model=SensitivityResponse,
        compute=_sensitivity,
        examples={
            "gordon_grid": {
                "model": "valuation/gordon-growth",
                "output": "value",
                "base_inputs": GORDON_BASE,
                "variables": [
                    {"name": "cost_of_equity", "values": [0.08, 0.09, 0.10, 0.11, 0.12]},
                    {"name": "growth_rate", "values": [0.03, 0.04, 0.05]},
                ],
            },
            "dcf_terminal_growth": {
                "model": "valuation/dcf/fcff",
                "output": "value_per_share",
                "base_inputs": DCF_BASE,
                "variables": [{"name": "terminal.growth_rate", "values": [0.01, 0.02, 0.03]}],
            },
        },
        notes=(
            SAFETY_NOTE,
            CELL_NOTE,
            f"At most {MAX_GRID_POINTS} grid points. Variable names are dotted input paths.",
        ),
    ),
    CalculationEndpoint(
        path="/scenario-analysis",
        title="Scenario Analysis",
        summary="Bear, base and bull cases of a registered model (Bear/Base/Bull Case)",
        formulas=(
            "inputs_s = base_inputs with the scenario overrides applied",
            "probability-weighted output = Σ p_s × output_s",
        ),
        request_model=ScenarioAnalysisRequest,
        response_model=ScenarioAnalysisResponse,
        compute=_scenario_analysis,
        examples={
            "dcf_bear_base_bull": {
                "model": "valuation/dcf/fcff",
                "output": "value_per_share",
                "base_inputs": DCF_BASE,
                "scenarios": [
                    {
                        "name": "bear",
                        "probability": 0.25,
                        "overrides": {
                            "cash_flows": [90.0, 95.0, 100.0],
                            "discount_rate": 0.12,
                            "terminal.growth_rate": 0.01,
                        },
                    },
                    {"name": "base", "probability": 0.5},
                    {
                        "name": "bull",
                        "probability": 0.25,
                        "overrides": {"discount_rate": 0.09, "terminal.growth_rate": 0.03},
                    },
                ],
            }
        },
        notes=(
            SAFETY_NOTE,
            CELL_NOTE,
            "Probabilities are optional but must be given for all scenarios and sum to 1.",
            "difference_from_base uses the scenario named 'base', when present.",
        ),
    ),
    CalculationEndpoint(
        path="/stress-test",
        title="Stress Test",
        summary="Linear factor stress test of a portfolio (stress testing)",
        formulas=(
            "shock return_i = Σ_f sensitivity_(i,f) × shock_f",
            "P&L_i = exposure_i × shock return_i; total P&L = Σ P&L_i",
        ),
        request_model=StressTestRequest,
        response_model=StressTestResponse,
        compute=_stress_test,
        examples={
            "multi_asset": {
                "positions": [
                    {"name": "equities", "exposure": 600000.0, "sensitivities": {"equity": 1.1}},
                    {"name": "bonds", "exposure": 300000.0, "sensitivities": {"rates": -6.5}},
                    {"name": "gold", "exposure": 100000.0},
                ],
                "scenarios": [
                    {
                        "name": "equity_crash",
                        "shocks": {"equity": -0.30, "rates": -0.01, "gold": 0.08},
                    },
                    {"name": "rate_spike", "shocks": {"equity": -0.08, "rates": 0.02}},
                ],
                "currency": "BRL",
            }
        },
        notes=(
            "Linear (first-order) approximation; factors missing from a scenario have zero shock.",
            "Without sensitivities a position moves one-for-one with the shock named like it.",
            "Rate sensitivities can be expressed as −modified duration (shock in decimal yield).",
            "No historical scenarios are embedded: shocks are supplied by the caller.",
        ),
    ),
    CalculationEndpoint(
        path="/monte-carlo",
        title="Monte Carlo Simulation",
        summary="Monte Carlo simulation with geometric Brownian motion",
        formulas=(
            "S_t = S_(t−1) × exp((μ − σ²/2) Δt + σ √Δt Z_t), Z_t ~ N(0, 1), Δt = 1 / ppy",
            "VaR = S_0 − q_(1−c)(S_T); ES = S_0 − mean(S_T | S_T ≤ q_(1−c))",
        ),
        request_model=MonteCarloRequest,
        response_model=MonteCarloResponse,
        compute=_monte_carlo,
        examples={
            "one_year_daily": {
                "initial_value": 100000,
                "expected_return": 0.10,
                "volatility": 0.20,
                "periods": 252,
                "simulations": 10000,
                "seed": 42,
            }
        },
        notes=(
            "μ and σ are annual; horizon T = periods / periods_per_year.",
            "The same seed always reproduces the same result (NumPy PCG64 generator).",
            "Without a seed one is generated and returned in seed_used.",
            "simulations × periods is limited by MAX_MONTE_CARLO_CELLS (LIMIT_EXCEEDED).",
            "Full paths are not returned; use sample_paths (≤ 10) for charts.",
        ),
    ),
)

add_calculation_endpoints(router, CALCULATION_ENDPOINTS)
METRIC_ENDPOINTS = ()
