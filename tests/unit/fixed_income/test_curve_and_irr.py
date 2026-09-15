import pytest

from app.core.exceptions import ConvergenceError, InvalidInputError
from app.services.fixed_income import cash_flows, curve
from app.services.fixed_income.curve import CurveInstrument
from app.utils.solvers import find_sign_change_root


class TestBootstrapping:
    def test_annual_par_bonds(self) -> None:
        points = curve.bootstrap_spot_curve(
            [
                CurveInstrument(3, 0.07, 100, 100),
                CurveInstrument(1, 0.05, 100, 100),
                CurveInstrument(2, 0.06, 100, 100),
            ],
            1,
        )

        d1 = 100 / 105
        d2 = (100 - 6 * d1) / 106
        d3 = (100 - 7 * (d1 + d2)) / 107
        assert [p.maturity_years for p in points] == [1, 2, 3]
        assert [p.discount_factor for p in points] == pytest.approx([d1, d2, d3])
        assert points[0].spot_rate == pytest.approx(0.05)
        assert points[1].spot_rate == pytest.approx(d2 ** (-1 / 2) - 1)
        assert points[2].spot_rate == pytest.approx(d3 ** (-1 / 3) - 1)

    def test_semiannual_zero_coupon_bonds(self) -> None:
        points = curve.bootstrap_spot_curve(
            [CurveInstrument(0.5, 0.0, 98, 100), CurveInstrument(1.0, 0.0, 95, 100)], 2
        )
        assert points[0].spot_rate == pytest.approx(0.98**-2 - 1)
        assert points[1].spot_rate == pytest.approx(0.95**-1 - 1)

    @pytest.mark.parametrize(
        ("instruments", "match"),
        [
            (
                [CurveInstrument(1, 0.05, 100, 100), CurveInstrument(3, 0.05, 100, 100)],
                "consecutive",
            ),
            (
                [CurveInstrument(1, 0.05, 100, 100), CurveInstrument(1, 0.06, 100, 100)],
                "more than one",
            ),
            ([CurveInstrument(1, 0.05, 100, 100), CurveInstrument(2, 0.5, 1, 100)], "non-positive"),
            ([CurveInstrument(1.3, 0.05, 100, 100)], "whole number"),
        ],
    )
    def test_invalid_curves(self, instruments: list[CurveInstrument], match: str) -> None:
        with pytest.raises(InvalidInputError, match=match):
            curve.bootstrap_spot_curve(instruments, 1)


class TestForwardRate:
    def test_one_year_forward_one_year_ahead(self) -> None:
        assert curve.forward_rate(0.05, 1, 0.06, 2) == pytest.approx(1.06**2 / 1.05 - 1)

    def test_from_today_equals_spot(self) -> None:
        assert curve.forward_rate(0.0, 0, 0.06, 2) == pytest.approx(0.06)

    def test_flat_curve_forward_equals_spot(self) -> None:
        assert curve.forward_rate(0.05, 1, 0.05, 3) == pytest.approx(0.05)

    def test_long_must_exceed_short(self) -> None:
        with pytest.raises(InvalidInputError, match="long_maturity"):
            curve.forward_rate(0.05, 2, 0.06, 2)


class TestIrr:
    def test_project_cash_flows(self) -> None:
        irr = cash_flows.internal_rate_of_return([-1000, 300, 400, 500])

        assert cash_flows.net_present_value(irr, [-1000, 300, 400, 500]) == pytest.approx(
            0, abs=1e-9
        )
        assert irr == pytest.approx(0.0889633947, abs=1e-9)

    def test_single_period(self) -> None:
        assert cash_flows.internal_rate_of_return([-100, 110]) == pytest.approx(0.10)

    def test_negative_irr_edge(self) -> None:
        # −100 + 60x + 30x² = 0 with x = 1 / (1 + r) → x = (−60 + √15600) / 60
        x = (-60 + 15600**0.5) / 60
        assert cash_flows.internal_rate_of_return([-100, 60, 30]) == pytest.approx(1 / x - 1)

    def test_leading_zero_and_inflow_first(self) -> None:
        irr = cash_flows.internal_rate_of_return([0, 100, -121])
        assert irr == pytest.approx(0.21)

    def test_three_sign_changes_with_single_real_root(self) -> None:
        flows = [-10, 30, -40, 25]
        irr = cash_flows.internal_rate_of_return(flows)
        assert cash_flows.net_present_value(irr, flows) == pytest.approx(0, abs=1e-9)

    def test_multiple_irrs_are_rejected_with_candidates(self) -> None:
        with pytest.raises(InvalidInputError) as caught:
            cash_flows.internal_rate_of_return([-100, 230, -132])

        assert caught.value.details["irr_candidates"] == pytest.approx([0.10, 0.20])

    def test_no_real_irr(self) -> None:
        with pytest.raises(InvalidInputError, match="no real"):
            cash_flows.internal_rate_of_return([100, -300, 250])

    @pytest.mark.parametrize("flows", [[100, 200], [-100, -1], [0, 0], [5]])
    def test_invalid_series(self, flows: list[float]) -> None:
        with pytest.raises(InvalidInputError):
            cash_flows.internal_rate_of_return(flows)


class TestSolver:
    def test_finds_root(self) -> None:
        root = find_sign_change_root(
            lambda r: 0.25 - r,
            sign_near_minus_one=1.0,
            sign_at_infinity=-1.0,
            too_close_to_minus_one="low",
            too_large="high",
        )
        assert root == pytest.approx(0.25)

    def test_large_root_is_found_by_expansion(self) -> None:
        root = find_sign_change_root(
            lambda r: 5000 - r,
            sign_near_minus_one=1.0,
            sign_at_infinity=-1.0,
            too_close_to_minus_one="low",
            too_large="high",
        )
        assert root == pytest.approx(5000)

    def test_no_root_raises_convergence_error(self) -> None:
        with pytest.raises(ConvergenceError, match="high"):
            find_sign_change_root(
                lambda r: 1.0,
                sign_near_minus_one=1.0,
                sign_at_infinity=-1.0,
                too_close_to_minus_one="low",
                too_large="high",
            )
