"""Statistics routes: /api/v1/statistics/*."""

from dataclasses import asdict

from fastapi import APIRouter

from app.api.endpoint_specs import (
    CalculationEndpoint,
    MetricEndpoint,
    add_calculation_endpoints,
    add_metric_endpoints,
)
from app.schemas.common import Unit
from app.schemas.statistics import (
    ConfidenceIntervalRequest,
    ConfidenceIntervalResponse,
    CovarianceRequest,
    DispersionRequest,
    KurtosisRequest,
    LinearRegressionResponse,
    PairedRequest,
    PercentilesRequest,
    PercentilesResponse,
    PercentileValue,
    QuartilesRequest,
    QuartilesResponse,
    SkewnessRequest,
    ValuesRequest,
    ZScoreRequest,
    ZScoresResponse,
)
from app.services.statistics import descriptive, relationships

router = APIRouter(prefix="/statistics")
descriptive_router = APIRouter(tags=["Statistics · Descriptive"])
relationships_router = APIRouter(tags=["Statistics · Relationships"])

SAMPLE = [12.0, 15.0, 9.0, 20.0, 17.0, 11.0, 14.0, 18.0]
X_SAMPLE = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]
Y_SAMPLE = [2.1, 3.9, 6.2, 7.8, 10.1, 12.2]
SAMPLE_NOTE = "Sample statistic (ddof = 1) unless population is true."


def _percentiles(r: PercentilesRequest) -> PercentilesResponse:
    values = descriptive.percentiles(r.values, r.percentiles, r.method)
    return PercentilesResponse(
        method=r.method,
        percentiles=[
            PercentileValue(percentile=rank, value=value)
            for rank, value in zip(r.percentiles, values, strict=True)
        ],
    )


def _quartiles(r: QuartilesRequest) -> QuartilesResponse:
    result = descriptive.quartiles(r.values, r.method)
    return QuartilesResponse(
        method=r.method,
        q1=result.q1,
        q2=result.q2,
        q3=result.q3,
        interquartile_range=result.interquartile_range,
    )


def _z_scores(r: ZScoreRequest) -> ZScoresResponse:
    return ZScoresResponse(
        **asdict(descriptive.z_scores(r.values, r.observation, population=r.population))
    )


def _regression(r: PairedRequest) -> LinearRegressionResponse:
    return LinearRegressionResponse(**asdict(relationships.linear_regression(r.x, r.y)))


def _confidence_interval(r: ConfidenceIntervalRequest) -> ConfidenceIntervalResponse:
    result = descriptive.confidence_interval_mean(r.values, r.confidence)
    return ConfidenceIntervalResponse(confidence=r.confidence, **asdict(result))


DESCRIPTIVE_METRICS = (
    MetricEndpoint(
        path="/mean",
        metric="Mean",
        unit=Unit.NUMBER,
        summary="Arithmetic mean (média)",
        formula="mean = Σ x / n",
        request_model=ValuesRequest,
        compute=lambda r: descriptive.mean(r.values),
        example={"values": SAMPLE},
    ),
    MetricEndpoint(
        path="/median",
        metric="Median",
        unit=Unit.NUMBER,
        summary="Median (mediana)",
        formula="middle value of the sorted sample (average of the two middle values if n is even)",
        request_model=ValuesRequest,
        compute=lambda r: descriptive.median(r.values),
        example={"values": SAMPLE},
    ),
    MetricEndpoint(
        path="/variance",
        metric="Variance",
        unit=Unit.NUMBER,
        summary="Variance (variância)",
        formula="s² = Σ (x − x̄)² / (n − ddof)",
        request_model=DispersionRequest,
        compute=lambda r: descriptive.variance(r.values, population=r.population),
        example={"values": SAMPLE},
        notes=(SAMPLE_NOTE, "The sample variance requires at least 2 values."),
    ),
    MetricEndpoint(
        path="/standard-deviation",
        metric="Standard Deviation",
        unit=Unit.NUMBER,
        summary="Standard deviation (desvio padrão)",
        formula="s = √(Σ (x − x̄)² / (n − ddof))",
        request_model=DispersionRequest,
        compute=lambda r: descriptive.standard_deviation(r.values, population=r.population),
        example={"values": SAMPLE},
        notes=(SAMPLE_NOTE,),
    ),
    MetricEndpoint(
        path="/skewness",
        metric="Skewness",
        unit=Unit.NUMBER,
        summary="Skewness (assimetria)",
        formula="g1 = m3 / m2^(3/2); G1 = g1 × √(n (n − 1)) / (n − 2)",
        request_model=SkewnessRequest,
        compute=lambda r: descriptive.skewness(r.values, bias_corrected=r.bias_corrected),
        example={"values": SAMPLE},
        notes=(
            "m_k are population central moments. Default: bias-corrected G1 (n ≥ 3).",
            "Zero variance returns DIVISION_BY_ZERO.",
        ),
    ),
    MetricEndpoint(
        path="/kurtosis",
        metric="Kurtosis",
        unit=Unit.NUMBER,
        summary="Kurtosis (curtose)",
        formula="g2 = m4 / m2² − 3; G2 = [(n + 1) g2 + 6] × (n − 1) / ((n − 2)(n − 3))",
        request_model=KurtosisRequest,
        compute=lambda r: descriptive.kurtosis(
            r.values, excess=r.excess, bias_corrected=r.bias_corrected
        ),
        example={"values": SAMPLE},
        notes=(
            "Default: bias-corrected excess kurtosis G2 (normal = 0, n ≥ 4).",
            "excess = false adds 3 (Pearson kurtosis).",
        ),
    ),
)

DESCRIPTIVE_CALCULATIONS = (
    CalculationEndpoint(
        path="/percentiles",
        title="Percentiles",
        summary="Percentiles of a sample (percentis)",
        formulas=("linear: x_(k) + (h − k) × (x_(k+1) − x_(k)), h = (n − 1) × p / 100",),
        request_model=PercentilesRequest,
        response_model=PercentilesResponse,
        compute=_percentiles,
        examples={"deciles": {"values": SAMPLE, "percentiles": [10, 50, 90]}},
        notes=(
            "method: linear (default), lower, higher, midpoint or nearest (NumPy definitions).",
        ),
    ),
    CalculationEndpoint(
        path="/quartiles",
        title="Quartiles",
        summary="Quartiles and interquartile range (quartis)",
        formulas=("Q1 = P25, Q2 = P50, Q3 = P75", "IQR = Q3 − Q1"),
        request_model=QuartilesRequest,
        response_model=QuartilesResponse,
        compute=_quartiles,
        examples={"sample": {"values": SAMPLE}},
        notes=("Percentiles use the selected interpolation method (default linear).",),
    ),
    CalculationEndpoint(
        path="/z-score",
        title="Z-Score",
        summary="Standard scores of a sample and of an optional observation",
        formulas=("z = (x − mean) / standard deviation",),
        request_model=ZScoreRequest,
        response_model=ZScoresResponse,
        compute=_z_scores,
        examples={"with_observation": {"values": SAMPLE, "observation": 22.0}},
        notes=(SAMPLE_NOTE, "Zero standard deviation returns DIVISION_BY_ZERO."),
    ),
    CalculationEndpoint(
        path="/confidence-interval",
        title="Confidence Interval",
        summary="Confidence interval of the mean (intervalo de confiança)",
        formulas=("mean ± t_((1+c)/2, n−1) × s / √n",),
        request_model=ConfidenceIntervalRequest,
        response_model=ConfidenceIntervalResponse,
        compute=_confidence_interval,
        examples={"ninety_five": {"values": SAMPLE, "confidence": 0.95}},
        notes=("Student's t distribution with the sample standard deviation.",),
    ),
)

RELATIONSHIP_METRICS = (
    MetricEndpoint(
        path="/covariance",
        metric="Covariance",
        unit=Unit.NUMBER,
        summary="Covariance of two paired samples (covariância)",
        formula="cov = Σ (x − x̄)(y − ȳ) / (n − ddof)",
        request_model=CovarianceRequest,
        compute=lambda r: relationships.covariance(r.x, r.y, population=r.population),
        example={"x": X_SAMPLE, "y": Y_SAMPLE},
        notes=(SAMPLE_NOTE, "x and y must have the same length."),
    ),
    MetricEndpoint(
        path="/correlation",
        metric="Correlation",
        unit=Unit.NUMBER,
        summary="Pearson correlation (correlação)",
        formula="r = Σ (x − x̄)(y − ȳ) / √(Σ (x − x̄)² × Σ (y − ȳ)²)",
        request_model=PairedRequest,
        compute=lambda r: relationships.correlation(r.x, r.y),
        example={"x": X_SAMPLE, "y": Y_SAMPLE},
        notes=("Result in [−1, 1]; a constant series returns DIVISION_BY_ZERO.",),
    ),
    MetricEndpoint(
        path="/r-squared",
        metric="R²",
        unit=Unit.NUMBER,
        summary="Coefficient of determination of a simple linear regression",
        formula="R² = r(x, y)²",
        request_model=PairedRequest,
        compute=lambda r: relationships.r_squared(r.x, r.y),
        example={"x": X_SAMPLE, "y": Y_SAMPLE},
    ),
)

RELATIONSHIP_CALCULATIONS = (
    CalculationEndpoint(
        path="/linear-regression",
        title="Linear Regression",
        summary="Simple linear regression by ordinary least squares (regressão linear)",
        formulas=(
            "slope = Σ (x − x̄)(y − ȳ) / Σ (x − x̄)², intercept = ȳ − slope × x̄",
            "s² = Σ residual² / (n − 2); SE(slope) = √(s² / Σ (x − x̄)²)",
            "t = slope / SE(slope); two-sided p-value with n − 2 degrees of freedom",
        ),
        request_model=PairedRequest,
        response_model=LinearRegressionResponse,
        compute=_regression,
        examples={"trend": {"x": X_SAMPLE, "y": Y_SAMPLE}},
        notes=(
            "Requires at least 3 observations; x or y with zero variance returns DIVISION_BY_ZERO.",
            "slope_t_statistic is null for a perfect fit.",
        ),
    ),
)

add_metric_endpoints(descriptive_router, DESCRIPTIVE_METRICS)
add_calculation_endpoints(descriptive_router, DESCRIPTIVE_CALCULATIONS)
add_metric_endpoints(relationships_router, RELATIONSHIP_METRICS)
add_calculation_endpoints(relationships_router, RELATIONSHIP_CALCULATIONS)
router.include_router(descriptive_router)
router.include_router(relationships_router)

METRIC_ENDPOINTS = (*DESCRIPTIVE_METRICS, *RELATIONSHIP_METRICS)
CALCULATION_ENDPOINTS = (*DESCRIPTIVE_CALCULATIONS, *RELATIONSHIP_CALCULATIONS)
