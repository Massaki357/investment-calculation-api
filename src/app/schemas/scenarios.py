"""Request and response models for scenario analysis, stress testing and Monte Carlo."""

from typing import Annotated, Any, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.common import BaseRequest, MonetaryRequest

ModelId = Annotated[
    str,
    Field(
        min_length=3,
        max_length=100,
        pattern=r"^[a-z][a-z_\-]*(/[a-z0-9_\-]+)+$",
        description="Registered calculation, e.g. valuation/dcf/fcff "
        "(see GET /api/v1/scenarios/models).",
    ),
]
OutputPath = Annotated[
    str,
    Field(
        min_length=1,
        max_length=100,
        pattern=r"^[A-Za-z0-9_\-]+(\.[A-Za-z0-9_\-]+)*$",
        description="Dotted path to a numeric field of the model response, e.g. value, "
        "enterprise_value, components.0.value.",
    ),
]
InputPath = Annotated[
    str,
    Field(
        min_length=1,
        max_length=100,
        pattern=r"^[A-Za-z0-9_\-]+(\.[A-Za-z0-9_\-]+)*$",
        description="Dotted path of the model input to change, e.g. discount_rate or "
        "terminal.growth_rate.",
    ),
]
Name = Annotated[str, Field(min_length=1, max_length=60)]


def _unique(names: list[str], what: str) -> None:
    if len(set(names)) != len(names):
        raise ValueError(f"{what} names must be unique")


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


# --- Sensitivity -------------------------------------------------------------------------------


class SensitivityVariable(_Strict):
    name: InputPath
    values: list[float] = Field(min_length=1, max_length=100, description="Values to test.")


class SensitivityRequest(BaseRequest):
    model: ModelId
    output: OutputPath
    base_inputs: dict[str, Any] = Field(description="Complete request body of the model.")
    variables: list[SensitivityVariable] = Field(
        min_length=1, max_length=2, description="One variable (line) or two variables (grid)."
    )

    @model_validator(mode="after")
    def _distinct_variables(self) -> Self:
        _unique([variable.name for variable in self.variables], "variable")
        return self


class CellError(BaseModel):
    code: str
    message: str


class SensitivityPoint(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)

    inputs: dict[str, float]
    output: float | None
    error: CellError | None = Field(description="Why output is null for this combination.")


class SensitivityResponse(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)

    metric: str = "Sensitivity Analysis"
    model: str
    output: str
    base_output: float | None
    variables: list[SensitivityVariable]
    points: list[SensitivityPoint]
    table: list[list[float | None]] | None = Field(
        description="Two variables only: rows follow variables[0].values, columns variables[1]."
    )


# --- Scenario analysis -------------------------------------------------------------------------


class ScenarioDefinition(_Strict):
    name: Name
    overrides: dict[str, Any] = Field(
        default_factory=dict, description="Dotted input paths and their values for this scenario."
    )
    probability: float | None = Field(default=None, ge=0, le=1)


class ScenarioAnalysisRequest(BaseRequest):
    model: ModelId
    output: OutputPath
    base_inputs: dict[str, Any]
    scenarios: list[ScenarioDefinition] = Field(min_length=1, max_length=20)

    @model_validator(mode="after")
    def _consistent_scenarios(self) -> Self:
        _unique([scenario.name for scenario in self.scenarios], "scenario")
        given = [scenario.probability is not None for scenario in self.scenarios]
        if any(given) and not all(given):
            raise ValueError("send a probability for every scenario or for none")
        return self


class ScenarioOutcome(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)

    name: str
    probability: float | None
    output: float | None
    difference_from_base: float | None = Field(
        description="output − output of the scenario named 'base' (null without one)."
    )
    error: CellError | None


class ScenarioAnalysisResponse(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)

    metric: str = "Scenario Analysis"
    model: str
    output: str
    scenarios: list[ScenarioOutcome]
    probability_weighted_output: float | None = Field(
        description="Σ p × output; null without probabilities or if a scenario failed."
    )
    minimum_output: float | None
    maximum_output: float | None


# --- Stress testing ----------------------------------------------------------------------------


class StressPosition(_Strict):
    name: Name
    exposure: float = Field(description="Current value of the position (negative for shorts).")
    sensitivities: dict[str, float] | None = Field(
        default=None,
        description="Factor → sensitivity (e.g. {'equity': 1.2, 'rates': -6.5}). Defaults to "
        "{name: 1}: the position moves one-for-one with a shock named like it.",
    )


class StressScenario(_Strict):
    name: Name
    shocks: dict[str, float] = Field(
        min_length=1, description="Factor → shock in decimal form (−0.30 = −30%)."
    )


class StressTestRequest(MonetaryRequest):
    positions: list[StressPosition] = Field(min_length=1, max_length=500)
    scenarios: list[StressScenario] = Field(min_length=1, max_length=50)

    @model_validator(mode="after")
    def _unique_names(self) -> Self:
        _unique([position.name for position in self.positions], "position")
        _unique([scenario.name for scenario in self.scenarios], "scenario")
        return self


class StressPositionResult(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)

    name: str
    exposure: float
    shock_return: float
    pnl: float


class StressScenarioResult(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)

    scenario: str
    total_exposure: float
    total_pnl: float
    value_after: float
    return_on_gross_exposure: float | None
    positions: list[StressPositionResult]


class StressTestResponse(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)

    metric: str = "Stress Test"
    scenarios: list[StressScenarioResult]
    worst_scenario: str
    worst_pnl: float
    currency: str | None = None


# --- Monte Carlo -------------------------------------------------------------------------------


class MonteCarloRequest(MonetaryRequest):
    initial_value: float = Field(gt=0, description="Starting value (amount).")
    expected_return: float = Field(
        ge=-1, le=10, description="Annual drift μ in decimal form (0.10 = 10%)."
    )
    volatility: float = Field(ge=0, le=5, description="Annual volatility σ in decimal form.")
    periods: int = Field(ge=1, le=10_000, description="Number of simulated periods.")
    simulations: int = Field(ge=1, le=1_000_000, description="Number of simulated paths.")
    periods_per_year: int = Field(default=252, ge=1, le=366, description="Δt = 1 / ppy.")
    seed: int | None = Field(
        default=None,
        ge=0,
        le=2**63 - 1,
        description="Random seed; the same seed reproduces the same result. When omitted a seed "
        "is generated and returned in seed_used.",
    )
    confidence: float = Field(default=0.95, gt=0.5, lt=1, description="Confidence for VaR/ES.")
    percentiles: list[Annotated[float, Field(ge=0, le=100)]] = Field(
        default_factory=lambda: [5.0, 25.0, 50.0, 75.0, 95.0], max_length=21
    )
    sample_paths: int = Field(
        default=0, ge=0, le=10, description="Number of simulated paths to return (for charts)."
    )


class PercentileValue(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)

    percentile: float
    value: float


class DistributionStats(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)

    mean: float
    standard_deviation: float
    minimum: float
    maximum: float
    percentiles: list[PercentileValue]


class LossMeasure(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)

    amount: float = Field(description="Loss versus initial_value (positive = loss).")
    decimal: float = Field(description="amount / initial_value.")


class MonteCarloResponse(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)

    metric: str = "Monte Carlo Simulation (GBM)"
    seed_used: int
    simulations: int
    periods: int
    horizon_years: float
    final_value: DistributionStats
    simulated_mean_return: float = Field(description="mean(final value) / initial_value − 1.")
    probability_of_loss: float = Field(description="Share of paths ending below initial_value.")
    confidence: float
    value_at_risk: LossMeasure
    expected_shortfall: LossMeasure
    max_drawdown: DistributionStats = Field(description="Per-path maximum drawdown (≤ 0).")
    theoretical_mean_final_value: float = Field(description="S_0 × e^(μT).")
    theoretical_median_final_value: float = Field(description="S_0 × e^((μ − σ²/2) T).")
    sample_paths: list[list[float]] = Field(
        description="First sample_paths simulated paths, periods + 1 points each."
    )
    currency: str | None = None
