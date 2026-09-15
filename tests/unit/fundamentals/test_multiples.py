import pytest

from app.core.exceptions import DivisionByZeroError
from app.services.fundamentals import multiples as m


@pytest.mark.parametrize(
    ("func", "args", "expected"),
    [
        (m.price_to_earnings, (35.5, 4.2), 8.452380952380953),
        (m.price_to_book, (20.0, 16.0), 1.25),
        (m.price_to_sales, (5e9, 2e9), 2.5),
        (m.ev_to_ebitda, (12e9, 1.5e9), 8.0),
        (m.ev_to_ebit, (12e9, 1e9), 12.0),
        (m.ev_to_revenue, (12e9, 4e9), 3.0),
        (m.ev_to_free_cash_flow, (12e9, 8e8), 15.0),
        (m.earnings_yield, (4.2, 35.5), 0.11830985915492958),
        (m.operating_earnings_yield, (1e9, 12e9), 0.08333333333333333),
        (m.free_cash_flow_yield, (4e8, 5e9), 0.08),
        (m.ebitda_yield, (1.5e9, 12e9), 0.125),
        (m.peg_ratio, (15.0, 0.10), 1.5),
    ],
)
def test_known_values(func, args, expected) -> None:
    assert func(*args) == pytest.approx(expected, rel=1e-12)


@pytest.mark.parametrize(
    ("func", "args", "expected"),
    [
        (m.price_to_earnings, (30.0, -2.0), -15.0),
        (m.price_to_book, (20.0, -4.0), -5.0),
        (m.ev_to_ebitda, (12e9, -1e9), -12.0),
        (m.ev_to_ebit, (-1e9, 5e8), -2.0),
        (m.free_cash_flow_yield, (-4e8, 5e9), -0.08),
        (m.peg_ratio, (15.0, -0.05), -3.0),
        (m.earnings_yield, (0.0, 35.5), 0.0),
    ],
)
def test_edge_cases_return_signed_values(func, args, expected) -> None:
    assert func(*args) == pytest.approx(expected, rel=1e-12)


@pytest.mark.parametrize(
    ("func", "args", "field"),
    [
        (m.price_to_earnings, (35.5, 0.0), "earnings_per_share"),
        (m.price_to_book, (20.0, 0.0), "book_value_per_share"),
        (m.price_to_sales, (5e9, 0.0), "revenue"),
        (m.ev_to_ebitda, (12e9, 0.0), "ebitda"),
        (m.ev_to_ebit, (12e9, 0.0), "ebit"),
        (m.ev_to_revenue, (12e9, 0.0), "revenue"),
        (m.ev_to_free_cash_flow, (12e9, 0.0), "free_cash_flow"),
        (m.earnings_yield, (4.2, 0.0), "share_price"),
        (m.operating_earnings_yield, (1e9, 0.0), "enterprise_value"),
        (m.free_cash_flow_yield, (4e8, 0.0), "market_capitalization"),
        (m.ebitda_yield, (1.5e9, 0.0), "enterprise_value"),
        (m.peg_ratio, (15.0, 0.0), "earnings_growth_rate"),
    ],
)
def test_zero_denominator_raises(func, args, field) -> None:
    with pytest.raises(DivisionByZeroError, match=field):
        func(*args)


def test_earnings_yield_is_inverse_of_pe() -> None:
    assert m.earnings_yield(4.2, 35.5) == pytest.approx(1 / m.price_to_earnings(35.5, 4.2))
