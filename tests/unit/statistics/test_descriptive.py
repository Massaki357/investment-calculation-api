import math

import numpy as np
import pytest
from scipy import stats

from app.core.exceptions import DivisionByZeroError, InsufficientDataError, InvalidInputError
from app.services.statistics import descriptive as d
from app.services.statistics.descriptive import PercentileMethod

CLASSIC = [2.0, 4.0, 4.0, 4.0, 5.0, 5.0, 7.0, 9.0]  # mean 5, population σ 2
SKEWED = [1.0, 2.0, 2.0, 3.0, 3.0, 3.0, 4.0, 9.0, 15.0]


class TestCentralTendency:
    def test_mean(self) -> None:
        assert d.mean(CLASSIC) == 5.0

    def test_single_value_mean(self) -> None:
        assert d.mean([7.5]) == 7.5

    def test_median_even_and_odd(self) -> None:
        assert d.median(CLASSIC) == 4.5
        assert d.median([3.0, 1.0, 2.0]) == 2.0

    def test_empty_is_insufficient(self) -> None:
        with pytest.raises(InsufficientDataError):
            d.mean([])


class TestDispersion:
    def test_population_variance_and_std(self) -> None:
        assert d.variance(CLASSIC, population=True) == pytest.approx(4.0)
        assert d.standard_deviation(CLASSIC, population=True) == pytest.approx(2.0)

    def test_sample_variance(self) -> None:
        assert d.variance(CLASSIC) == pytest.approx(32 / 7)
        assert d.standard_deviation(CLASSIC) == pytest.approx(np.std(CLASSIC, ddof=1))

    def test_single_value_population_variance_is_zero(self) -> None:
        assert d.variance([5.0], population=True) == 0

    def test_single_value_sample_variance_is_insufficient(self) -> None:
        with pytest.raises(InsufficientDataError, match="at least 2"):
            d.variance([5.0])


class TestPercentiles:
    def test_linear_matches_numpy(self) -> None:
        ranks = [0, 10, 25, 50, 90, 100]
        assert d.percentiles(SKEWED, ranks) == pytest.approx(np.percentile(SKEWED, ranks))

    @pytest.mark.parametrize("method", list(PercentileMethod))
    def test_all_methods_match_numpy(self, method: PercentileMethod) -> None:
        expected = np.percentile(SKEWED, [33], method=method.value)
        assert d.percentiles(SKEWED, [33], method) == pytest.approx(expected)

    def test_quartiles(self) -> None:
        result = d.quartiles([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0])
        assert (result.q1, result.q2, result.q3, result.interquartile_range) == (3, 5, 7, 4)

    def test_invalid_rank(self) -> None:
        with pytest.raises(InvalidInputError):
            d.percentiles(SKEWED, [101])


class TestZScores:
    def test_population_z_scores(self) -> None:
        result = d.z_scores(CLASSIC, observation=11.0, population=True)
        assert result.z_scores[-1] == pytest.approx(2.0)
        assert result.observation_z_score == pytest.approx(3.0)

    def test_sample_z_scores_match_scipy(self) -> None:
        assert d.z_scores(SKEWED).z_scores == pytest.approx(stats.zscore(SKEWED, ddof=1))

    def test_constant_sample(self) -> None:
        with pytest.raises(DivisionByZeroError):
            d.z_scores([3.0, 3.0, 3.0])


class TestShape:
    @pytest.mark.parametrize("bias_corrected", [True, False])
    def test_skewness_matches_scipy(self, bias_corrected: bool) -> None:
        expected = stats.skew(SKEWED, bias=not bias_corrected)
        assert d.skewness(SKEWED, bias_corrected=bias_corrected) == pytest.approx(expected)

    @pytest.mark.parametrize("bias_corrected", [True, False])
    @pytest.mark.parametrize("excess", [True, False])
    def test_kurtosis_matches_scipy(self, bias_corrected: bool, excess: bool) -> None:
        expected = stats.kurtosis(SKEWED, fisher=excess, bias=not bias_corrected)
        result = d.kurtosis(SKEWED, excess=excess, bias_corrected=bias_corrected)
        assert result == pytest.approx(expected)

    def test_symmetric_sample_has_zero_skewness(self) -> None:
        assert d.skewness([1.0, 2.0, 3.0, 4.0, 5.0]) == pytest.approx(0.0, abs=1e-15)

    def test_bias_corrected_minimum_sizes(self) -> None:
        with pytest.raises(InsufficientDataError, match="3 observations"):
            d.skewness([1.0, 2.0])
        with pytest.raises(InsufficientDataError, match="4 observations"):
            d.kurtosis([1.0, 2.0, 4.0])

    def test_constant_sample_shape_is_undefined(self) -> None:
        with pytest.raises(DivisionByZeroError):
            d.kurtosis([2.0, 2.0, 2.0, 2.0])


class TestConfidenceInterval:
    def test_matches_scipy_t_interval(self) -> None:
        result = d.confidence_interval_mean(SKEWED, 0.95)
        sem = np.std(SKEWED, ddof=1) / math.sqrt(len(SKEWED))
        lower, upper = stats.t.interval(0.95, len(SKEWED) - 1, loc=np.mean(SKEWED), scale=sem)

        assert result.lower == pytest.approx(lower)
        assert result.upper == pytest.approx(upper)
        assert result.degrees_of_freedom == 8
        assert result.standard_error == pytest.approx(sem)

    def test_higher_confidence_is_wider(self) -> None:
        narrow = d.confidence_interval_mean(SKEWED, 0.90)
        wide = d.confidence_interval_mean(SKEWED, 0.99)
        assert wide.margin_of_error > narrow.margin_of_error

    def test_invalid_confidence(self) -> None:
        with pytest.raises(InvalidInputError):
            d.confidence_interval_mean(SKEWED, 1.0)
