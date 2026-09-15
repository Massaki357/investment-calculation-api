"""Request and response models for portfolio analytics and optimization."""

from enum import StrEnum
from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.common import BaseRequest
from app.schemas.validators import require_exactly_one, require_fields

MAX_ASSETS = 500

Weights = Annotated[
    list[float],
    Field(
        min_length=1,
        max_length=MAX_ASSETS,
        description="Portfolio weights in decimal form, one per asset, summing to 1.",
    ),
]
AssetNames = Annotated[
    list[str] | None,
    Field(
        max_length=MAX_ASSETS,
        description="Optional unique labels, one per asset (defaults to asset_1, asset_2, ...).",
    ),
]
CovarianceMatrix = Annotated[
    list[list[float]],
    Field(
        min_length=1,
        max_length=MAX_ASSETS,
        description="Square, symmetric, positive semi-definite covariance matrix. Results are "
        "expressed in the same period as this matrix.",
    ),
]
ReturnsMatrix = Annotated[
    list[list[float]],
    Field(
        min_length=2,
        description="Simple returns matrix: one row per period, one column per asset (≥ 2 rows). "
        "Estimates are annualized with periods_per_year.",
    ),
]
ExpectedReturns = Annotated[
    list[float],
    Field(
        min_length=1,
        max_length=MAX_ASSETS,
        description="Expected return per asset (decimal), same period as the covariance matrix.",
    ),
]
PeriodsPerYear = Annotated[
    int, Field(ge=1, le=366, description="Return periods per year for a returns matrix (252).")
]
BenchmarkReturns = Annotated[
    list[float], Field(min_length=2, description="Benchmark simple returns, one per period.")
]
RiskFreeRate = Annotated[
    float, Field(description="Risk-free rate (decimal) for the same period as expected returns.")
]
MinWeight = Annotated[
    float, Field(ge=-1, le=1, description="Lower bound per asset (0 = long-only, default).")
]
MaxWeight = Annotated[float, Field(gt=0, le=1, description="Upper bound per asset (default 1).")]

MARKET_NOTE_FIELDS = "Send covariance_matrix (with expected_returns when needed) or returns."


class _CovarianceInput(BaseRequest):
    covariance_matrix: CovarianceMatrix | None = None
    returns: ReturnsMatrix | None = None
    periods_per_year: PeriodsPerYear = 252
    asset_names: AssetNames = None

    @model_validator(mode="after")
    def _one_market_source(self) -> Self:
        require_exactly_one(self, "covariance_matrix", "returns")
        return self


class _MarketInput(_CovarianceInput):
    expected_returns: ExpectedReturns | None = None

    @model_validator(mode="after")
    def _expected_returns_source(self) -> Self:
        if self.returns is not None and self.expected_returns is not None:
            raise ValueError("expected_returns are estimated from returns; do not send both")
        return self


class _RequiresExpectedReturns(_MarketInput):
    @model_validator(mode="after")
    def _needs_expected_returns(self) -> Self:
        if self.covariance_matrix is not None:
            require_fields(self, "covariance_matrix", "expected_returns")
        return self


# --- Analytics ---------------------------------------------------------------------------------


class ExpectedReturnRequest(BaseRequest):
    weights: Weights
    expected_returns: ExpectedReturns | None = None
    returns: ReturnsMatrix | None = None
    periods_per_year: PeriodsPerYear = 252

    @model_validator(mode="after")
    def _one_source(self) -> Self:
        require_exactly_one(self, "expected_returns", "returns")
        return self


class PortfolioRiskRequest(_CovarianceInput):
    weights: Weights


class PortfolioReturnRequest(BaseRequest):
    weights: Weights
    returns: Annotated[
        list[list[float]],
        Field(min_length=1, description="Simple returns matrix: rows = periods, columns = assets."),
    ]
    periods_per_year: PeriodsPerYear = 252


class CovarianceMatrixRequest(BaseRequest):
    returns: ReturnsMatrix
    periods_per_year: int | None = Field(
        default=None, ge=1, le=366, description="When sent, the matrix is annualized (× ppy)."
    )
    population: bool = Field(default=False, description="Population (ddof = 0) covariance.")
    asset_names: AssetNames = None


class CorrelationMatrixRequest(BaseRequest):
    covariance_matrix: CovarianceMatrix | None = None
    returns: ReturnsMatrix | None = None
    asset_names: AssetNames = None

    @model_validator(mode="after")
    def _one_source(self) -> Self:
        require_exactly_one(self, "covariance_matrix", "returns")
        return self


class PortfolioBetaRequest(BaseRequest):
    weights: Weights
    asset_betas: list[float] | None = Field(default=None, description="Beta of each asset.")
    returns: ReturnsMatrix | None = None
    benchmark_returns: BenchmarkReturns | None = None

    @model_validator(mode="after")
    def _one_method(self) -> Self:
        if self.asset_betas is not None:
            if self.returns is not None or self.benchmark_returns is not None:
                raise ValueError("send asset_betas, or returns with benchmark_returns, not both")
        else:
            require_fields(self, "beta from returns", "returns", "benchmark_returns")
        return self


class PortfolioAlphaRequest(BaseRequest):
    weights: Weights
    returns: ReturnsMatrix
    benchmark_returns: BenchmarkReturns
    risk_free_rate: float = Field(default=0, gt=-1, description="Annual risk-free rate.")
    periods_per_year: PeriodsPerYear = 252


class TrackingErrorMethod(StrEnum):
    EX_POST = "ex_post"
    EX_ANTE = "ex_ante"


class TrackingErrorRequest(BaseRequest):
    method: TrackingErrorMethod = Field(
        default=TrackingErrorMethod.EX_POST,
        description="ex_post (default): realized, from returns and benchmark_returns · "
        "ex_ante: from benchmark_weights and covariance_matrix.",
    )
    weights: Weights
    returns: ReturnsMatrix | None = None
    benchmark_returns: BenchmarkReturns | None = None
    periods_per_year: PeriodsPerYear = 252
    benchmark_weights: Weights | None = None
    covariance_matrix: CovarianceMatrix | None = None

    @model_validator(mode="after")
    def _method_fields(self) -> Self:
        if self.method is TrackingErrorMethod.EX_POST:
            require_fields(self, "method 'ex_post'", "returns", "benchmark_returns")
        else:
            require_fields(self, "method 'ex_ante'", "benchmark_weights", "covariance_matrix")
        return self


class ConcentrationRequest(BaseRequest):
    weights: Weights
    asset_names: AssetNames = None


class TurnoverRequest(BaseRequest):
    current_weights: Weights
    target_weights: Weights


# --- Optimization ------------------------------------------------------------------------------


class MinimumVarianceRequest(_MarketInput):
    min_weight: MinWeight = 0.0
    max_weight: MaxWeight = 1.0


class MaximumSharpeRequest(_RequiresExpectedReturns):
    risk_free_rate: RiskFreeRate = 0.0
    min_weight: MinWeight = 0.0
    max_weight: MaxWeight = 1.0


class EfficientFrontierRequest(_RequiresExpectedReturns):
    points: int = Field(default=20, ge=2, le=100, description="Number of frontier portfolios.")
    risk_free_rate: RiskFreeRate | None = None
    min_weight: MinWeight = 0.0
    max_weight: MaxWeight = 1.0


class RiskParityRequest(_MarketInput):
    pass


class InverseVolatilityRequest(_MarketInput):
    pass


# --- Responses ---------------------------------------------------------------------------------


class _Response(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)


class AssetWeight(_Response):
    asset: str
    weight: float


class PortfolioReturnResponse(_Response):
    metric: str = "Portfolio Return"
    periods: int
    cumulative_return: float
    annualized_return: float
    portfolio_returns: list[float] = Field(description="Σ w_i r_i,t for each period.")


class MatrixResponse(_Response):
    metric: str
    assets: list[str]
    matrix: list[list[float]] = Field(description="Rows and columns follow `assets`.")


class RiskContributionItem(_Response):
    asset: str
    weight: float
    marginal_contribution: float = Field(description="∂σ_p / ∂w_i = (Σw)_i / σ_p.")
    risk_contribution: float = Field(description="w_i × marginal contribution; sums to σ_p.")
    percent_contribution: float = Field(description="Share of portfolio volatility; sums to 1.")


class RiskContributionResponse(_Response):
    metric: str = "Risk Contribution"
    volatility: float
    contributions: list[RiskContributionItem]


class ConcentrationResponse(_Response):
    metric: str = "Concentration"
    hhi: float = Field(description="Herfindahl-Hirschman index Σ w² (1/N to 1).")
    normalized_hhi: float | None = Field(description="(HHI − 1/N) / (1 − 1/N); null for N = 1.")
    effective_number_of_assets: float = Field(description="1 / HHI.")
    max_weight: float
    number_of_assets: int


class OptimizedPortfolioResponse(_Response):
    metric: str
    weights: list[AssetWeight]
    expected_return: float | None = Field(description="Null when expected returns are unknown.")
    volatility: float
    variance: float
    sharpe_ratio: float | None = Field(description="Null without a risk-free rate.")
    risk_contributions: list[RiskContributionItem] | None = None


class FrontierPoint(_Response):
    expected_return: float
    volatility: float
    sharpe_ratio: float | None
    weights: list[AssetWeight]


class EfficientFrontierResponse(_Response):
    metric: str = "Efficient Frontier"
    points: list[FrontierPoint] = Field(
        description="Ordered from the minimum-variance portfolio to the maximum-return portfolio."
    )
