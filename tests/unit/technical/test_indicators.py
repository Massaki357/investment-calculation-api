"""Indicator formulas: hand-computed values plus cross-checks against pandas."""

import math
from typing import Any

import numpy as np
import pandas as pd
import pytest

from app.core.exceptions import InsufficientDataError, InvalidInputError
from app.services.technical import averages, common, momentum, volatility, volume

CLOSES = [
    44.34, 44.09, 44.15, 43.61, 44.33, 44.83, 45.10, 45.42, 45.84, 46.08,
    45.89, 46.03, 45.61, 46.28, 46.28, 46.00, 46.03, 46.41, 46.22, 45.64,
]  # fmt: skip
HIGH = [11.0, 12.0, 13.0, 12.0, 14.0]
LOW = [9.0, 10.0, 11.0, 10.0, 12.0]
CLOSE = [10.0, 11.0, 12.0, 11.0, 13.0]


def pandas_series(values: Any) -> Any:
    """pandas stubs are imprecise for chained rolling/ewm calls; tests only need runtime values."""
    return pd.Series(values)


def defined(series: list[float | None]) -> list[float]:
    return [value for value in series if value is not None]


class TestMovingAverages:
    def test_sma_alignment_and_values(self) -> None:
        assert averages.sma([1, 2, 3, 4, 5], 3) == [None, None, 2.0, 3.0, 4.0]

    def test_sma_matches_pandas(self) -> None:
        expected = pandas_series(CLOSES).rolling(5).mean().dropna().tolist()
        assert defined(averages.sma(CLOSES, 5)) == pytest.approx(expected)

    def test_ema_on_linear_series_lags_by_half_window(self) -> None:
        # With an SMA seed, the EMA of P_t = t + 1 is exactly P_t − (N − 1) / 2.
        assert averages.ema([float(p) for p in range(1, 11)], 3) == [None, None] + [
            float(p) for p in range(2, 10)
        ]

    def test_ema_matches_pandas_with_sma_seed(self) -> None:
        period = 5
        seeded = pandas_series([np.mean(CLOSES[:period]), *CLOSES[period:]])
        expected = seeded.ewm(alpha=2 / (period + 1), adjust=False).mean().tolist()
        assert defined(averages.ema(CLOSES, period)) == pytest.approx(expected)

    def test_wma(self) -> None:
        assert averages.wma([1, 2, 3], 3) == [None, None, pytest.approx(14 / 6)]

    def test_vwma(self) -> None:
        assert averages.vwma([10, 11, 12], [100, 200, 100], 3)[-1] == pytest.approx(11)

    def test_vwma_zero_volume_window_is_null(self) -> None:
        assert averages.vwma([10, 11, 12], [0, 0, 5], 2) == [None, None, pytest.approx(12)]

    def test_period_one_returns_prices(self) -> None:
        assert averages.sma([3.0, 4.0], 1) == [3.0, 4.0]

    def test_insufficient_data(self) -> None:
        with pytest.raises(InsufficientDataError, match="at least 5"):
            averages.sma([1, 2, 3], 5)


class TestMomentum:
    def test_rsi_hand_computed_alternating_series(self) -> None:
        assert momentum.rsi([10, 11, 10, 11, 10], 2) == [None, None, 50.0, 75.0, 37.5]

    def test_rsi_first_value_from_exact_averages(self) -> None:
        # 14 changes: gains sum 3.34, losses sum 1.40 → RS = (3.34/14) / (1.40/14)
        first = momentum.rsi(CLOSES, 14)[14]
        assert first == pytest.approx(100 - 100 / (1 + 3.34 / 1.40))

    def test_rsi_matches_pandas_wilder_smoothing(self) -> None:
        period = 14
        changes = pandas_series(CLOSES).diff().dropna()
        gains, losses = changes.clip(lower=0), -changes.clip(upper=0)

        def wilder(values: Any) -> Any:
            seeded = pandas_series([values.iloc[:period].mean(), *values.iloc[period:]])
            return seeded.ewm(alpha=1 / period, adjust=False).mean()

        expected = (100 - 100 / (1 + wilder(gains) / wilder(losses))).tolist()
        assert defined(momentum.rsi(CLOSES, period)) == pytest.approx(expected)

    def test_rsi_extremes(self) -> None:
        assert momentum.rsi([1, 2, 3, 4], 2)[-1] == 100.0
        assert momentum.rsi([5, 5, 5], 2)[-1] == 50.0
        assert momentum.rsi([4, 3, 2, 1], 2)[-1] == pytest.approx(0.0)

    def test_macd_on_linear_series(self) -> None:
        result = momentum.macd([float(p) for p in range(1, 41)], 3, 5, 2)
        # EMA lags (N − 1) / 2 on a line: MACD = (5 − 1)/2 − (3 − 1)/2 = 1
        assert defined(result.macd) == pytest.approx([1.0] * 36)
        assert defined(result.histogram) == pytest.approx([0.0] * 35, abs=1e-12)
        assert result.signal[:5] == [None] * 5 and result.signal[5] is not None

    def test_macd_requires_fast_below_slow(self) -> None:
        with pytest.raises(InvalidInputError, match="fast_period"):
            momentum.macd(CLOSES, 10, 5, 3)

    def test_roc(self) -> None:
        assert momentum.roc([100, 110, 121], 1) == [None, pytest.approx(0.1), pytest.approx(0.1)]

    def test_stochastic_and_williams_identity(self) -> None:
        stoch = momentum.stochastic(HIGH, LOW, CLOSE, 3, 2)
        williams = momentum.williams_r(HIGH, LOW, CLOSE, 3)

        assert stoch.percent_k == [None, None, 75.0, pytest.approx(100 / 3), 75.0]
        assert stoch.percent_d == [None, None, None, pytest.approx(325 / 6), pytest.approx(325 / 6)]
        for k, r in zip(defined(stoch.percent_k), defined(williams), strict=True):
            assert r == pytest.approx(k - 100)

    def test_stochastic_zero_range_is_null(self) -> None:
        flat = [10.0, 10.0, 10.0]
        assert momentum.stochastic(flat, flat, flat, 2, 1).percent_k == [None, None, None]

    def test_cci(self) -> None:
        # TP = 1, 2, 3 → SMA 2, mean deviation 2/3 → (3 − 2) / (0.015 × 2/3) = 100
        assert momentum.cci([1, 2, 3], [1, 2, 3], [1, 2, 3], 3)[-1] == pytest.approx(100)

    def test_ohlc_validation(self) -> None:
        with pytest.raises(InvalidInputError, match="close must lie"):
            momentum.williams_r([10, 10], [9, 9], [11, 9.5], 2)
        with pytest.raises(InvalidInputError, match="same length"):
            momentum.cci([10, 10], [9], [9.5, 9.5], 1)


class TestVolatility:
    def test_atr_hand_computed(self) -> None:
        # TR = 2, 2, 2, 3 → ATR_2 = 2, then (2 + 2)/2 = 2, (2 + 3)/2 = 2.5
        assert volatility.atr(HIGH, LOW, CLOSE, 2) == [None, None, 2.0, 2.0, 2.5]

    def test_bollinger_bands(self) -> None:
        result = volatility.bollinger_bands([1, 2, 3], 3, 2)
        sigma = math.sqrt(2 / 3)

        assert result.middle[-1] == pytest.approx(2)
        assert result.upper[-1] == pytest.approx(2 + 2 * sigma)
        assert result.lower[-1] == pytest.approx(2 - 2 * sigma)
        assert result.percent_b[-1] == pytest.approx((3 - (2 - 2 * sigma)) / (4 * sigma))
        assert result.bandwidth[-1] == pytest.approx(4 * sigma / 2)

    def test_bollinger_matches_pandas_population_std(self) -> None:
        rolling = pandas_series(CLOSES).rolling(10)
        upper = (rolling.mean() + 2 * rolling.std(ddof=0)).dropna().tolist()
        assert defined(volatility.bollinger_bands(CLOSES, 10).upper) == pytest.approx(upper)

    def test_flat_prices_have_null_percent_b(self) -> None:
        assert volatility.bollinger_bands([5, 5, 5], 3).percent_b[-1] is None

    def test_historical_volatility_matches_pandas(self) -> None:
        log_returns: Any = pandas_series(np.log(CLOSES)).diff()
        expected = (log_returns.rolling(10).std(ddof=1) * math.sqrt(252)).dropna().tolist()
        assert defined(volatility.historical_volatility(CLOSES, 10)) == pytest.approx(expected)

    def test_historical_volatility_requires_two_returns(self) -> None:
        with pytest.raises(InvalidInputError):
            volatility.historical_volatility(CLOSES, 1)


class TestVolume:
    def test_obv(self) -> None:
        assert volume.obv([10, 11, 11, 9], [100, 200, 300, 400]) == [0.0, 200.0, 200.0, -200.0]

    def test_vwap_cumulative(self) -> None:
        assert volume.vwap([10, 11, 12], [100, 0, 300]) == [10.0, 10.0, pytest.approx(11.5)]

    def test_vwap_null_before_volume(self) -> None:
        assert volume.vwap([10, 11], [0, 50]) == [None, 11.0]

    def test_money_flow_index_hand_computed(self) -> None:
        volumes = [1000, 1100, 1200, 900, 1500]
        tp = [(h + low + c) / 3 for h, low, c in zip(HIGH, LOW, CLOSE, strict=True)]
        flows = [t * v for t, v in zip(tp, volumes, strict=True)]
        # window ending at index 3: flows 2 (up) and 3 (down)
        expected = 100 - 100 / (1 + flows[2] / flows[3])
        assert volume.money_flow_index(HIGH, LOW, CLOSE, volumes, 2)[3] == pytest.approx(expected)

    def test_money_flow_index_without_negative_flow(self) -> None:
        result = volume.money_flow_index(HIGH, LOW, CLOSE, [1000, 1100, 1200, 900, 1500], 2)
        assert result[2] == 100.0

    def test_volumes_must_align(self) -> None:
        with pytest.raises(InvalidInputError, match="same length"):
            volume.obv([10, 11], [100])


class TestRollingReduce:
    def test_chunks_match_a_single_pass(self, monkeypatch: pytest.MonkeyPatch) -> None:
        values = np.random.default_rng(7).normal(100, 5, 500)
        expected = common.windows(values, 30).std(axis=1, ddof=1)
        # 90 cells per chunk = 3 windows of 30: many chunks plus a partial last one.
        monkeypatch.setattr(common, "_WINDOW_CHUNK_CELLS", 90)
        result = common.rolling_reduce(values, 30, lambda rows: rows.std(axis=1, ddof=1))
        assert result.shape == expected.shape
        assert np.array_equal(result, expected)

    def test_period_larger_than_chunk(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(common, "_WINDOW_CHUNK_CELLS", 2)
        result = common.rolling_reduce(np.arange(6.0), 4, lambda rows: rows.sum(axis=1))
        assert result.tolist() == [6.0, 10.0, 14.0]
