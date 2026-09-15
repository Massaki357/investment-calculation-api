import math

import numpy as np
import pytest
from scipy import stats

from app.core.exceptions import InvalidInputError, LimitExceededError
from app.services.scenarios import monte_carlo as mc

BASE = {
    "initial_value": 100_000.0,
    "expected_return": 0.10,
    "volatility": 0.20,
    "periods": 252,
    "simulations": 20_000,
    "max_cells": 10_000_000,
}


class TestSimulation:
    def test_same_seed_reproduces_results(self) -> None:
        first = mc.simulate_gbm(**BASE, seed=42)
        second = mc.simulate_gbm(**BASE, seed=42)
        assert np.array_equal(first.final_values, second.final_values)
        assert np.array_equal(first.max_drawdowns, second.max_drawdowns)

    def test_different_seeds_differ(self) -> None:
        first = mc.simulate_gbm(**BASE, seed=1)
        second = mc.simulate_gbm(**BASE, seed=2)
        assert not np.array_equal(first.final_values, second.final_values)

    def test_results_do_not_depend_on_batch_size(self, monkeypatch: pytest.MonkeyPatch) -> None:
        reference = mc.simulate_gbm(**{**BASE, "simulations": 500}, seed=7)
        monkeypatch.setattr(mc, "_BATCH_CELLS", 1_000)
        batched = mc.simulate_gbm(**{**BASE, "simulations": 500}, seed=7)
        assert np.allclose(reference.final_values, batched.final_values, rtol=1e-12, atol=0)

    def test_generated_seed_is_returned_and_reproducible(self) -> None:
        generated = mc.simulate_gbm(**{**BASE, "simulations": 100})
        assert 0 <= generated.seed_used < 2**53
        replay = mc.simulate_gbm(**{**BASE, "simulations": 100}, seed=generated.seed_used)
        assert np.array_equal(generated.final_values, replay.final_values)

    def test_zero_volatility_is_deterministic(self) -> None:
        result = mc.simulate_gbm(**{**BASE, "volatility": 0.0, "simulations": 10}, seed=3)
        assert result.final_values == pytest.approx([100_000 * math.exp(0.10)] * 10)
        assert np.all(result.max_drawdowns == 0)

    def test_distribution_matches_gbm_theory(self) -> None:
        result = mc.simulate_gbm(**BASE, seed=2026)
        finals = result.final_values
        log_growth = np.log(finals / BASE["initial_value"])

        # ln(S_T / S_0) ~ N((μ − σ²/2) T, σ² T) with T = 1
        standard_error = 0.20 / math.sqrt(BASE["simulations"])
        assert log_growth.mean() == pytest.approx(0.08, abs=4 * standard_error)
        assert log_growth.std(ddof=1) == pytest.approx(0.20, rel=0.03)
        assert result.theoretical_mean_final_value == pytest.approx(100_000 * math.exp(0.10))
        expected_loss_probability = stats.norm.cdf(-0.08 / 0.20)
        assert float((finals < 100_000).mean()) == pytest.approx(
            expected_loss_probability, abs=0.015
        )

    def test_drawdowns_are_non_positive_and_paths_start_at_initial_value(self) -> None:
        result = mc.simulate_gbm(**{**BASE, "simulations": 50}, seed=5, sample_paths=3)
        assert np.all(result.max_drawdowns <= 0)
        assert len(result.sample_paths) == 3
        assert all(len(path) == 253 and path[0] == 100_000 for path in result.sample_paths)
        assert result.sample_paths[0][-1] == pytest.approx(result.final_values[0])

    def test_cell_limit(self) -> None:
        with pytest.raises(LimitExceededError, match="exceeds the limit"):
            mc.simulate_gbm(**{**BASE, "max_cells": 1_000}, seed=1)

    @pytest.mark.parametrize("change", [{"initial_value": 0}, {"volatility": -0.1}, {"periods": 0}])
    def test_invalid_parameters(self, change: dict[str, float]) -> None:
        with pytest.raises(InvalidInputError):
            mc.simulate_gbm(**{**BASE, **change}, seed=1)


class TestSummaries:
    def test_summarize(self) -> None:
        values = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        summary = mc.summarize(values, [50, 100])
        assert summary.mean == 3.0
        assert summary.standard_deviation == pytest.approx(np.std(values, ddof=1))
        assert summary.percentiles == [(50.0, 3.0), (100.0, 5.0)]

    def test_single_value_has_zero_standard_deviation(self) -> None:
        assert mc.summarize(np.array([7.0]), []).standard_deviation == 0.0

    def test_tail_loss(self) -> None:
        finals = np.array([80.0, 90.0, 100.0, 110.0, 120.0])
        loss = mc.tail_loss(finals, 100.0, 0.8)
        # quantile at 20%: 80 + 0.8 × 10 = 88 → VaR = 12; tail {80} → ES = 20
        assert loss.value_at_risk == pytest.approx(12.0)
        assert loss.expected_shortfall == pytest.approx(20.0)
