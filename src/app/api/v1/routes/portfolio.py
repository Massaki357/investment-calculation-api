"""Portfolio routes: /api/v1/portfolio/*."""

from typing import cast

import numpy as np
from fastapi import APIRouter

from app.api.endpoint_specs import (
    CalculationEndpoint,
    MetricEndpoint,
    add_calculation_endpoints,
    add_metric_endpoints,
)
from app.schemas.common import MetricBreakdownResponse, MetricValue, Unit
from app.schemas.portfolio import (
    AssetWeight,
    ConcentrationRequest,
    ConcentrationResponse,
    CorrelationMatrixRequest,
    CovarianceMatrixRequest,
    EfficientFrontierRequest,
    EfficientFrontierResponse,
    ExpectedReturnRequest,
    FrontierPoint,
    InverseVolatilityRequest,
    MatrixResponse,
    MaximumSharpeRequest,
    MinimumVarianceRequest,
    OptimizedPortfolioResponse,
    PortfolioAlphaRequest,
    PortfolioBetaRequest,
    PortfolioReturnRequest,
    PortfolioReturnResponse,
    PortfolioRiskRequest,
    RiskContributionItem,
    RiskContributionResponse,
    RiskParityRequest,
    TrackingErrorMethod,
    TrackingErrorRequest,
    TurnoverRequest,
    _CovarianceInput,
    _MarketInput,
)
from app.services.portfolio import analytics, optimization
from app.services.portfolio.inputs import (
    MarketInputs,
    as_covariance,
    as_returns_matrix,
    as_weights,
    asset_labels,
    market_from_covariance,
    market_from_returns,
)
from app.services.portfolio.optimization import PortfolioPoint
from app.services.risk import performance
from app.services.risk.returns import ReturnType, annualized_return, cumulative_return
from app.services.statistics.descriptive import FloatArray
from app.services.statistics.relationships import correlation_from_covariance, covariance_matrix

router = APIRouter(prefix="/portfolio")
analytics_router = APIRouter(tags=["Portfolio · Analytics"])
optimization_router = APIRouter(tags=["Portfolio · Construction"])

NAMES = ["stocks", "bonds", "real_estate"]
COV = [[0.04, 0.006, 0.002], [0.006, 0.09, 0.018], [0.002, 0.018, 0.0225]]
MU = [0.08, 0.14, 0.06]
WEIGHTS = [0.5, 0.3, 0.2]
RETURNS = [
    [0.012, 0.004, 0.006],
    [-0.008, 0.002, -0.003],
    [0.015, -0.001, 0.009],
    [-0.021, 0.006, -0.012],
    [0.009, 0.001, 0.004],
    [0.004, -0.002, 0.002],
]
BENCHMARK = [0.010, -0.005, 0.011, -0.015, 0.007, 0.003]

MARKET_NOTE = (
    "Send covariance_matrix (used as-is, results in its period) or a returns matrix "
    "(annualized: μ = mean × ppy, Σ = sample covariance × ppy)."
)
WEIGHTS_NOTE = "weights must sum to 1 (tolerance 1e-6); negative weights (shorts) are allowed."
BOUNDS_NOTE = (
    "min_weight / max_weight bound every asset (default long-only 0 to 1); infeasible bounds "
    "return INVALID_INPUT."
)
SIMPLE_RETURNS_NOTE = "Returns matrices hold simple returns (rows = periods, columns = assets)."


def _covariance_market(r: _CovarianceInput) -> MarketInputs:
    # The request validator guarantees exactly one of covariance_matrix / returns.
    if r.returns is not None:
        return market_from_returns(r.returns, r.periods_per_year)
    return market_from_covariance(cast(list[list[float]], r.covariance_matrix), None)


def _full_market(r: _MarketInput) -> MarketInputs:
    if r.returns is not None:
        return market_from_returns(r.returns, r.periods_per_year)
    return market_from_covariance(cast(list[list[float]], r.covariance_matrix), r.expected_returns)


def _weights_for(r: PortfolioRiskRequest) -> tuple[MarketInputs, FloatArray]:
    market = _covariance_market(r)
    return market, as_weights(r.weights, n_assets=market.n_assets)


def _series(weights: list[float], returns: list[list[float]]) -> list[float]:
    matrix = as_returns_matrix(returns)
    return analytics.portfolio_returns(as_weights(weights, n_assets=matrix.shape[1]), returns)


def _asset_weights(labels: list[str], weights: FloatArray) -> list[AssetWeight]:
    return [
        AssetWeight(asset=label, weight=float(w)) for label, w in zip(labels, weights, strict=True)
    ]


def _contribution_items(
    labels: list[str], weights: FloatArray, covariance: FloatArray
) -> tuple[float, list[RiskContributionItem]]:
    sigma, contributions = analytics.risk_contributions(weights, covariance)
    return sigma, [
        RiskContributionItem(
            asset=label,
            weight=item.weight,
            marginal_contribution=item.marginal_contribution,
            risk_contribution=item.risk_contribution,
            percent_contribution=item.percent_contribution,
        )
        for label, item in zip(labels, contributions, strict=True)
    ]


# --- Analytics compute functions ---------------------------------------------------------------


def _expected_return(r: ExpectedReturnRequest) -> float:
    if r.returns is not None:
        mu = market_from_returns(r.returns, r.periods_per_year).expected_returns
    else:
        mu = np.asarray(r.expected_returns, dtype=np.float64)
    mu = cast(FloatArray, mu)
    return analytics.expected_return(as_weights(r.weights, n_assets=mu.size), mu)


def _variance(r: PortfolioRiskRequest) -> float:
    market, weights = _weights_for(r)
    return analytics.variance(weights, market.covariance)


def _volatility(r: PortfolioRiskRequest) -> float:
    market, weights = _weights_for(r)
    return analytics.volatility(weights, market.covariance)


def _portfolio_return(r: PortfolioReturnRequest) -> PortfolioReturnResponse:
    series = _series(r.weights, r.returns)
    return PortfolioReturnResponse(
        periods=len(series),
        cumulative_return=cumulative_return(series, ReturnType.SIMPLE),
        annualized_return=annualized_return(series, ReturnType.SIMPLE, r.periods_per_year),
        portfolio_returns=series,
    )


def _covariance(r: CovarianceMatrixRequest) -> MatrixResponse:
    matrix = covariance_matrix(as_returns_matrix(r.returns).tolist(), population=r.population)
    if r.periods_per_year is not None:
        matrix = matrix * r.periods_per_year
    labels = asset_labels(r.asset_names, matrix.shape[0])
    return MatrixResponse(metric="Covariance Matrix", assets=labels, matrix=matrix.tolist())


def _correlation(r: CorrelationMatrixRequest) -> MatrixResponse:
    if r.returns is not None:
        matrix = covariance_matrix(as_returns_matrix(r.returns).tolist())
    else:
        matrix = as_covariance(cast(list[list[float]], r.covariance_matrix))
    correlation = correlation_from_covariance(matrix)
    labels = asset_labels(r.asset_names, correlation.shape[0])
    return MatrixResponse(metric="Correlation Matrix", assets=labels, matrix=correlation.tolist())


def _beta(r: PortfolioBetaRequest) -> float:
    if r.asset_betas is not None:
        weights = as_weights(r.weights, n_assets=len(r.asset_betas))
        return analytics.weighted_beta(weights, r.asset_betas)
    series = _series(r.weights, cast(list[list[float]], r.returns))
    return performance.beta(series, cast(list[float], r.benchmark_returns))


def _alpha(r: PortfolioAlphaRequest) -> MetricBreakdownResponse:
    series = _series(r.weights, r.returns)
    result = performance.jensens_alpha(
        series, r.benchmark_returns, r.risk_free_rate, r.periods_per_year, ReturnType.SIMPLE
    )
    return MetricBreakdownResponse(
        metric="Portfolio Alpha",
        value=result.alpha,
        unit=Unit.DECIMAL,
        components=[
            MetricValue(metric="Portfolio Beta", value=result.beta, unit=Unit.NUMBER),
            MetricValue(
                metric="Portfolio Annualized Return", value=result.asset_return, unit=Unit.DECIMAL
            ),
            MetricValue(
                metric="Benchmark Annualized Return",
                value=result.benchmark_return,
                unit=Unit.DECIMAL,
            ),
        ],
    )


def _tracking_error(r: TrackingErrorRequest) -> float:
    # The request validator guarantees the fields of the chosen method.
    if r.method is TrackingErrorMethod.EX_ANTE:
        covariance = as_covariance(cast(list[list[float]], r.covariance_matrix))
        n = covariance.shape[0]
        return analytics.ex_ante_tracking_error(
            as_weights(r.weights, n_assets=n),
            as_weights(
                cast(list[float], r.benchmark_weights), name="benchmark_weights", n_assets=n
            ),
            covariance,
        )
    series = _series(r.weights, cast(list[list[float]], r.returns))
    return performance.information_ratio(
        series, cast(list[float], r.benchmark_returns), r.periods_per_year, ReturnType.SIMPLE
    ).tracking_error


def _risk_contribution(r: PortfolioRiskRequest) -> RiskContributionResponse:
    market, weights = _weights_for(r)
    labels = asset_labels(r.asset_names, market.n_assets)
    sigma, items = _contribution_items(labels, weights, market.covariance)
    return RiskContributionResponse(volatility=sigma, contributions=items)


def _concentration(r: ConcentrationRequest) -> ConcentrationResponse:
    asset_labels(r.asset_names, len(r.weights))
    result = analytics.concentration(r.weights)
    return ConcentrationResponse(
        hhi=result.hhi,
        normalized_hhi=result.normalized_hhi,
        effective_number_of_assets=result.effective_number_of_assets,
        max_weight=result.max_weight,
        number_of_assets=result.number_of_assets,
    )


# --- Construction compute functions ------------------------------------------------------------


def _optimized(
    metric: str,
    labels: list[str],
    point: PortfolioPoint,
    covariance: FloatArray | None = None,
) -> OptimizedPortfolioResponse:
    contributions = None
    if covariance is not None:
        _, contributions = _contribution_items(labels, point.weights, covariance)
    return OptimizedPortfolioResponse(
        metric=metric,
        weights=_asset_weights(labels, point.weights),
        expected_return=point.expected_return,
        volatility=point.volatility,
        variance=point.variance,
        sharpe_ratio=point.sharpe_ratio,
        risk_contributions=contributions,
    )


def _minimum_variance(r: MinimumVarianceRequest) -> OptimizedPortfolioResponse:
    market = _full_market(r)
    labels = asset_labels(r.asset_names, market.n_assets)
    weights = optimization.minimum_variance(market, r.min_weight, r.max_weight)
    return _optimized("Minimum Variance Portfolio", labels, optimization.describe(weights, market))


def _maximum_sharpe(r: MaximumSharpeRequest) -> OptimizedPortfolioResponse:
    market = _full_market(r)
    labels = asset_labels(r.asset_names, market.n_assets)
    weights = optimization.maximum_sharpe(market, r.risk_free_rate, r.min_weight, r.max_weight)
    point = optimization.describe(weights, market, r.risk_free_rate)
    return _optimized("Maximum Sharpe Portfolio", labels, point)


def _efficient_frontier(r: EfficientFrontierRequest) -> EfficientFrontierResponse:
    market = _full_market(r)
    labels = asset_labels(r.asset_names, market.n_assets)
    frontier = optimization.efficient_frontier(
        market, r.points, r.min_weight, r.max_weight, r.risk_free_rate
    )
    return EfficientFrontierResponse(
        points=[
            FrontierPoint(
                expected_return=cast(float, point.expected_return),
                volatility=point.volatility,
                sharpe_ratio=point.sharpe_ratio,
                weights=_asset_weights(labels, point.weights),
            )
            for point in frontier
        ]
    )


def _risk_parity(r: RiskParityRequest) -> OptimizedPortfolioResponse:
    market = _full_market(r)
    labels = asset_labels(r.asset_names, market.n_assets)
    weights = optimization.risk_parity(market)
    point = optimization.describe(weights, market)
    return _optimized("Risk Parity Portfolio", labels, point, market.covariance)


def _inverse_volatility(r: InverseVolatilityRequest) -> OptimizedPortfolioResponse:
    market = _full_market(r)
    labels = asset_labels(r.asset_names, market.n_assets)
    weights = optimization.inverse_volatility(market)
    point = optimization.describe(weights, market)
    return _optimized("Inverse Volatility Portfolio", labels, point, market.covariance)


# --- Endpoint specifications -------------------------------------------------------------------

ANALYTICS_METRICS = (
    MetricEndpoint(
        path="/expected-return",
        metric="Portfolio Expected Return",
        unit=Unit.DECIMAL,
        summary="Expected return of a portfolio (retorno esperado)",
        formula="E(R_p) = Σ w_i × E(R_i)",
        request_model=ExpectedReturnRequest,
        compute=_expected_return,
        example={"weights": WEIGHTS, "expected_returns": MU},
        notes=(
            WEIGHTS_NOTE,
            "Send expected_returns, or a returns matrix (annualized arithmetic mean × ppy).",
        ),
    ),
    MetricEndpoint(
        path="/variance",
        metric="Portfolio Variance",
        unit=Unit.NUMBER,
        summary="Portfolio variance (variância)",
        formula="σ²_p = wᵀ Σ w",
        request_model=PortfolioRiskRequest,
        compute=_variance,
        example={"weights": WEIGHTS, "covariance_matrix": COV},
        notes=(WEIGHTS_NOTE, MARKET_NOTE),
    ),
    MetricEndpoint(
        path="/volatility",
        metric="Portfolio Volatility",
        unit=Unit.DECIMAL,
        summary="Portfolio volatility (volatilidade)",
        formula="σ_p = √(wᵀ Σ w)",
        request_model=PortfolioRiskRequest,
        compute=_volatility,
        example={"weights": WEIGHTS, "covariance_matrix": COV},
        notes=(WEIGHTS_NOTE, MARKET_NOTE),
    ),
    MetricEndpoint(
        path="/beta",
        metric="Portfolio Beta",
        unit=Unit.NUMBER,
        summary="Portfolio beta",
        formula="asset_betas: β_p = Σ w_i β_i · returns: β_p = cov(r_p, r_b) / var(r_b)",
        request_model=PortfolioBetaRequest,
        compute=_beta,
        example={"weights": WEIGHTS, "asset_betas": [1.1, 0.2, 0.8]},
        notes=(
            WEIGHTS_NOTE,
            "With returns, r_p,t = Σ w_i r_i,t (constant weights) is regressed on "
            "benchmark_returns.",
            SIMPLE_RETURNS_NOTE,
        ),
    ),
    MetricEndpoint(
        path="/tracking-error",
        metric="Tracking Error",
        unit=Unit.DECIMAL,
        summary="Tracking error against a benchmark",
        formula="ex_post: σ(r_p − r_b) × √ppy · ex_ante: √((w − w_b)ᵀ Σ (w − w_b))",
        request_model=TrackingErrorRequest,
        compute=_tracking_error,
        example={"weights": WEIGHTS, "returns": RETURNS, "benchmark_returns": BENCHMARK},
        notes=(
            "ex_post (default) is annualized with periods_per_year; ex_ante is in the covariance "
            "matrix period.",
            WEIGHTS_NOTE,
            SIMPLE_RETURNS_NOTE,
        ),
    ),
    MetricEndpoint(
        path="/turnover",
        metric="Turnover",
        unit=Unit.DECIMAL,
        summary="One-way portfolio turnover",
        formula="Turnover = Σ |w_target − w_current| / 2",
        request_model=TurnoverRequest,
        compute=lambda r: analytics.turnover(r.current_weights, r.target_weights),
        example={"current_weights": [0.5, 0.3, 0.2], "target_weights": [0.4, 0.4, 0.2]},
        notes=("One-way: the fraction of the portfolio bought (equal to the fraction sold).",),
    ),
)

ANALYTICS_CALCULATIONS = (
    CalculationEndpoint(
        path="/return",
        title="Portfolio Return",
        summary="Realized portfolio return (retorno da carteira)",
        formulas=(
            "r_p,t = Σ w_i r_i,t",
            "cumulative = Π(1 + r_p,t) − 1, annualized = (1 + cumulative)^(ppy / T) − 1",
        ),
        request_model=PortfolioReturnRequest,
        response_model=PortfolioReturnResponse,
        compute=_portfolio_return,
        examples={"daily": {"weights": WEIGHTS, "returns": RETURNS}},
        notes=("Constant weights rebalanced every period.", WEIGHTS_NOTE, SIMPLE_RETURNS_NOTE),
    ),
    CalculationEndpoint(
        path="/covariance",
        title="Covariance Matrix",
        summary="Covariance matrix of asset returns (covariância)",
        formulas=("Σ_ij = Σ_t (r_ti − r̄_i)(r_tj − r̄_j) / (T − ddof)",),
        request_model=CovarianceMatrixRequest,
        response_model=MatrixResponse,
        compute=_covariance,
        examples={
            "annualized": {"returns": RETURNS, "periods_per_year": 252, "asset_names": NAMES}
        },
        notes=("Sample covariance unless population; periods_per_year annualizes (× ppy).",),
    ),
    CalculationEndpoint(
        path="/correlation",
        title="Correlation Matrix",
        summary="Correlation matrix of assets (correlação)",
        formulas=("ρ_ij = Σ_ij / (σ_i σ_j)",),
        request_model=CorrelationMatrixRequest,
        response_model=MatrixResponse,
        compute=_correlation,
        examples={
            "from_covariance": {"covariance_matrix": COV, "asset_names": NAMES},
            "from_returns": {"returns": RETURNS},
        },
        notes=("A zero-variance asset returns DIVISION_BY_ZERO.",),
    ),
    CalculationEndpoint(
        path="/alpha",
        title="Portfolio Alpha",
        summary="Jensen's alpha of the portfolio",
        formulas=("r_p,t = Σ w_i r_i,t", "α = R_p − [rf + β_p × (R_b − rf)]"),
        request_model=PortfolioAlphaRequest,
        response_model=MetricBreakdownResponse,
        compute=_alpha,
        examples={
            "daily": {
                "weights": WEIGHTS,
                "returns": RETURNS,
                "benchmark_returns": BENCHMARK,
                "risk_free_rate": 0.05,
            }
        },
        notes=(
            "R_p and R_b are geometric annualized returns; risk_free_rate is annual.",
            WEIGHTS_NOTE,
            SIMPLE_RETURNS_NOTE,
        ),
    ),
    CalculationEndpoint(
        path="/risk-contribution",
        title="Risk Contribution",
        summary="Contribution of each asset to portfolio volatility",
        formulas=(
            "MRC_i = (Σ w)_i / σ_p",
            "RC_i = w_i × MRC_i (Σ RC_i = σ_p)",
            "%RC_i = RC_i / σ_p",
        ),
        request_model=PortfolioRiskRequest,
        response_model=RiskContributionResponse,
        compute=_risk_contribution,
        examples={
            "three_assets": {"weights": WEIGHTS, "covariance_matrix": COV, "asset_names": NAMES}
        },
        notes=("Euler decomposition of volatility.", WEIGHTS_NOTE, MARKET_NOTE),
    ),
    CalculationEndpoint(
        path="/concentration",
        title="Concentration",
        summary="Portfolio concentration (concentração)",
        formulas=(
            "HHI = Σ w_i²",
            "effective N = 1 / HHI",
            "normalized HHI = (HHI − 1/N) / (1 − 1/N)",
        ),
        request_model=ConcentrationRequest,
        response_model=ConcentrationResponse,
        compute=_concentration,
        examples={"three_assets": {"weights": WEIGHTS}},
        notes=("Requires long-only weights that sum to 1.",),
    ),
)

CONSTRUCTION_CALCULATIONS = (
    CalculationEndpoint(
        path="/minimum-variance",
        title="Minimum Variance Portfolio",
        summary="Global minimum variance portfolio",
        formulas=("min wᵀΣw  s.t.  Σ w_i = 1, min_weight ≤ w_i ≤ max_weight",),
        request_model=MinimumVarianceRequest,
        response_model=OptimizedPortfolioResponse,
        compute=_minimum_variance,
        examples={
            "long_only": {"covariance_matrix": COV, "expected_returns": MU, "asset_names": NAMES}
        },
        notes=(
            MARKET_NOTE,
            BOUNDS_NOTE,
            "expected_returns are optional and only used to report expected_return.",
            "Solved with SLSQP; weights may deviate from the bounds by ≤ 1e-8.",
        ),
    ),
    CalculationEndpoint(
        path="/maximum-sharpe",
        title="Maximum Sharpe Portfolio",
        summary="Tangency portfolio with the highest Sharpe ratio",
        formulas=("max (wᵀμ − rf) / √(wᵀΣw)  s.t.  Σ w_i = 1, min_weight ≤ w_i ≤ max_weight",),
        request_model=MaximumSharpeRequest,
        response_model=OptimizedPortfolioResponse,
        compute=_maximum_sharpe,
        examples={
            "long_only": {
                "covariance_matrix": COV,
                "expected_returns": MU,
                "risk_free_rate": 0.02,
                "asset_names": NAMES,
            }
        },
        notes=(
            MARKET_NOTE,
            BOUNDS_NOTE,
            "risk_free_rate must be in the same period as expected returns.",
            "If no portfolio beats the risk-free rate the result maximizes a non-positive Sharpe.",
        ),
    ),
    CalculationEndpoint(
        path="/efficient-frontier",
        title="Efficient Frontier",
        summary="Efficient frontier of minimum-variance portfolios",
        formulas=(
            "for target μ* evenly spaced from μ(minimum variance) to max attainable μ:",
            "min wᵀΣw  s.t.  wᵀμ = μ*, Σ w_i = 1, min_weight ≤ w_i ≤ max_weight",
        ),
        request_model=EfficientFrontierRequest,
        response_model=EfficientFrontierResponse,
        compute=_efficient_frontier,
        examples={
            "five_points": {
                "covariance_matrix": COV,
                "expected_returns": MU,
                "points": 5,
                "risk_free_rate": 0.02,
                "asset_names": NAMES,
            }
        },
        notes=(
            MARKET_NOTE,
            BOUNDS_NOTE,
            "The last point is the maximum-return portfolio under the bounds. If every portfolio "
            "has the same expected return a single point is returned.",
        ),
    ),
    CalculationEndpoint(
        path="/risk-parity",
        title="Risk Parity Portfolio",
        summary="Equal risk contribution portfolio",
        formulas=(
            "min ½ yᵀΣy − (1/N) Σ ln y_i, y > 0;  w = y / Σ y",
            "at the optimum RC_i = σ_p / N for every asset",
        ),
        request_model=RiskParityRequest,
        response_model=OptimizedPortfolioResponse,
        compute=_risk_parity,
        examples={"three_assets": {"covariance_matrix": COV, "asset_names": NAMES}},
        notes=(
            MARKET_NOTE,
            "Long-only by construction; every asset needs positive variance.",
            "Convex formulation (Spinu, 2013); equal contributions verified to 1e-6.",
        ),
    ),
    CalculationEndpoint(
        path="/inverse-volatility",
        title="Inverse Volatility Portfolio",
        summary="Inverse volatility weighting",
        formulas=("w_i = (1 / σ_i) / Σ_j (1 / σ_j)",),
        request_model=InverseVolatilityRequest,
        response_model=OptimizedPortfolioResponse,
        compute=_inverse_volatility,
        examples={"three_assets": {"covariance_matrix": COV, "asset_names": NAMES}},
        notes=(
            MARKET_NOTE,
            "Uses only the diagonal (correlations ignored); risk contributions are reported.",
        ),
    ),
)

add_metric_endpoints(analytics_router, ANALYTICS_METRICS)
add_calculation_endpoints(analytics_router, ANALYTICS_CALCULATIONS)
add_calculation_endpoints(optimization_router, CONSTRUCTION_CALCULATIONS)
router.include_router(analytics_router)
router.include_router(optimization_router)

METRIC_ENDPOINTS = ANALYTICS_METRICS
CALCULATION_ENDPOINTS = (*ANALYTICS_CALCULATIONS, *CONSTRUCTION_CALCULATIONS)
