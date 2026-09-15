import pytest

from app.api.model_registry import extract_number, with_overrides
from app.api.v1.routes.scenarios import registry
from app.core.exceptions import InvalidInputError
from app.services.scenarios import analysis


class TestProbabilityWeighting:
    def test_weighted_value(self) -> None:
        assert analysis.probability_weighted_value([8, 11, 13], [0.25, 0.5, 0.25]) == 10.75

    def test_single_certain_scenario(self) -> None:
        assert analysis.probability_weighted_value([42.0], [1.0]) == 42.0

    @pytest.mark.parametrize(
        ("values", "probabilities", "match"),
        [
            ([1, 2], [0.5, 0.4], "sum to 1"),
            ([1, 2], [1.2, -0.2], "negative"),
            ([1, 2], [1.0], "exactly one"),
        ],
    )
    def test_invalid_probabilities(
        self, values: list[float], probabilities: list[float], match: str
    ) -> None:
        with pytest.raises(InvalidInputError, match=match):
            analysis.probability_weighted_value(values, probabilities)


class TestStressTest:
    def test_factor_pnl(self) -> None:
        positions = [
            analysis.Position("equities", 600_000, {"equity": 1.1}),
            analysis.Position("bonds", 300_000, {"rates": -6.5}),
            analysis.Position("gold", 100_000, {"gold": 1.0}),
        ]
        result = analysis.stress_test(
            positions, "crash", {"equity": -0.30, "rates": -0.01, "gold": 0.08}
        )

        pnls = {item.name: item.pnl for item in result.positions}
        assert pnls["equities"] == pytest.approx(-198_000)
        assert pnls["bonds"] == pytest.approx(19_500)
        assert pnls["gold"] == pytest.approx(8_000)
        assert result.total_pnl == pytest.approx(-170_500)
        assert result.value_after == pytest.approx(829_500)
        assert result.return_on_gross_exposure == pytest.approx(-0.1705)

    def test_missing_factor_has_zero_shock(self) -> None:
        result = analysis.stress_test(
            [analysis.Position("x", 100, {"fx": 2.0})], "calm", {"equity": -0.1}
        )
        assert result.total_pnl == 0

    def test_short_position_gains_in_a_crash(self) -> None:
        result = analysis.stress_test(
            [analysis.Position("short", -50_000, {"equity": 1.0})], "crash", {"equity": -0.2}
        )
        assert result.total_pnl == pytest.approx(10_000)

    def test_zero_gross_exposure(self) -> None:
        result = analysis.stress_test(
            [analysis.Position("empty", 0, {"equity": 1.0})], "s", {"equity": -0.2}
        )
        assert result.return_on_gross_exposure is None


class TestRegistryHelpers:
    def test_extract_number(self) -> None:
        data = {"value": 3, "components": [{"value": 1.5}], "latest": {"macd": None}}
        assert extract_number(data, "value") == 3.0
        assert extract_number(data, "components.0.value") == 1.5
        assert extract_number(data, "latest.macd") is None

    @pytest.mark.parametrize("path", ["missing", "components.5.value", "components"])
    def test_extract_number_errors(self, path: str) -> None:
        with pytest.raises(InvalidInputError):
            extract_number({"components": [{"value": 1.0}]}, path)

    def test_with_overrides_is_deep_and_non_mutating(self) -> None:
        base = {
            "discount_rate": 0.1,
            "terminal": {"method": "perpetuity_growth", "growth_rate": 0.02},
        }
        changed = with_overrides(base, {"terminal.growth_rate": 0.03, "discount_rate": 0.12})
        assert changed["terminal"] == {"method": "perpetuity_growth", "growth_rate": 0.03}
        assert base["terminal"]["growth_rate"] == 0.02

    def test_with_overrides_rejects_non_object_parent(self) -> None:
        with pytest.raises(InvalidInputError, match="not an object"):
            with_overrides({"discount_rate": 0.1}, {"discount_rate.x": 1})

    def test_registry_contains_every_domain_but_not_scenarios(self) -> None:
        ids = {model.model_id for model in registry.models}
        for prefix in (
            "fundamentals/",
            "valuation/",
            "fixed-income/",
            "risk/",
            "statistics/",
            "portfolio/",
            "technical/",
        ):
            assert any(model_id.startswith(prefix) for model_id in ids)
        assert not any(model_id.startswith("scenarios/") for model_id in ids)

    def test_evaluate_captures_calculation_errors(self) -> None:
        evaluation = registry.evaluate(
            "valuation/gordon-growth",
            {"current_dividend": 2, "cost_of_equity": 0.05, "growth_rate": 0.05},
            "value",
        )
        assert evaluation.output is None
        assert evaluation.error_code == "INVALID_INPUT"

    def test_evaluate_captures_validation_errors(self) -> None:
        evaluation = registry.evaluate(
            "fundamentals/pe-ratio", {"share_price": -1, "earnings_per_share": 2}, "value"
        )
        assert evaluation.error_code == "VALIDATION_ERROR"
        assert "share_price" in (evaluation.error_message or "")

    def test_unknown_model(self) -> None:
        with pytest.raises(InvalidInputError, match="unknown model"):
            registry.get("valuation/does-not-exist")
