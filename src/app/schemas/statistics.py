"""Request and response models for descriptive statistics and relationships."""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import BaseRequest
from app.services.statistics.descriptive import PercentileMethod

Values = Annotated[list[float], Field(min_length=1, description="Sample values.")]
PairedValues = Annotated[
    list[float], Field(min_length=2, description="Paired sample; same length as the other series.")
]
Population = Annotated[
    bool, Field(description="Population statistic (ddof = 0) instead of sample (ddof = 1).")
]


class ValuesRequest(BaseRequest):
    values: Values


class DispersionRequest(BaseRequest):
    values: Values
    population: Population = False


class PercentilesRequest(BaseRequest):
    values: Values
    percentiles: list[Annotated[float, Field(ge=0, le=100)]] = Field(
        min_length=1, max_length=101, description="Percentile ranks between 0 and 100."
    )
    method: PercentileMethod = Field(
        default=PercentileMethod.LINEAR, description="Interpolation method (default linear)."
    )


class QuartilesRequest(BaseRequest):
    values: Values
    method: PercentileMethod = PercentileMethod.LINEAR


class ZScoreRequest(BaseRequest):
    values: Annotated[list[float], Field(min_length=2)]
    observation: float | None = Field(
        default=None, description="Optional value to standardize against the sample."
    )
    population: Population = False


class PairedRequest(BaseRequest):
    x: PairedValues
    y: PairedValues


class CovarianceRequest(PairedRequest):
    population: Population = False


class SkewnessRequest(BaseRequest):
    values: Values
    bias_corrected: bool = Field(
        default=True, description="Adjusted Fisher-Pearson G1 (default) instead of g1."
    )


class KurtosisRequest(BaseRequest):
    values: Values
    excess: bool = Field(default=True, description="Excess kurtosis (normal = 0) by default.")
    bias_corrected: bool = Field(default=True, description="Bias-corrected G2 by default.")


class ConfidenceIntervalRequest(BaseRequest):
    values: Annotated[list[float], Field(min_length=2)]
    confidence: float = Field(default=0.95, gt=0, lt=1, description="Confidence level in (0, 1).")


class PercentileValue(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)

    percentile: float
    value: float


class PercentilesResponse(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)

    metric: str = "Percentiles"
    method: PercentileMethod
    percentiles: list[PercentileValue]


class QuartilesResponse(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)

    metric: str = "Quartiles"
    method: PercentileMethod
    q1: float
    q2: float
    q3: float
    interquartile_range: float


class ZScoresResponse(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)

    metric: str = "Z-Score"
    mean: float
    standard_deviation: float
    z_scores: list[float] = Field(description="z for each value, in input order.")
    observation_z_score: float | None


class LinearRegressionResponse(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)

    metric: str = "Linear Regression"
    slope: float
    intercept: float
    correlation: float
    r_squared: float
    residual_standard_error: float
    slope_standard_error: float
    intercept_standard_error: float
    slope_t_statistic: float | None = Field(description="Null for a perfect fit (zero error).")
    slope_p_value: float = Field(description="Two-sided p-value for slope = 0.")
    observations: int


class ConfidenceIntervalResponse(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)

    metric: str = "Confidence Interval of the Mean"
    confidence: float
    mean: float
    lower: float
    upper: float
    margin_of_error: float
    standard_error: float
    critical_value: float = Field(description="Student's t critical value.")
    degrees_of_freedom: int
