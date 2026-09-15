"""Dividend metrics."""

from app.services.fundamentals.growth import cagr
from app.utils.math import safe_divide


def dividend_yield(dividend_per_share: float, share_price: float) -> float:
    """Dividend Yield = dividend_per_share / share_price."""
    return safe_divide(dividend_per_share, share_price, denominator_name="share_price")


def dividend_payout_ratio(dividends_paid: float, net_income: float) -> float:
    """Dividend Payout = dividends_paid / net_income."""
    return safe_divide(dividends_paid, net_income, denominator_name="net_income")


def dividend_coverage(earnings_per_share: float, dividend_per_share: float) -> float:
    """Dividend Coverage = earnings_per_share / dividend_per_share."""
    return safe_divide(
        earnings_per_share, dividend_per_share, denominator_name="dividend_per_share"
    )


def dividend_cagr(beginning_dividend: float, ending_dividend: float, years: float) -> float:
    """Dividend CAGR = (ending_dividend / beginning_dividend) ^ (1 / years) − 1."""
    return cagr(
        beginning_dividend,
        ending_dividend,
        years,
        beginning_name="beginning_dividend",
        ending_name="ending_dividend",
    )


def dividend_per_share(total_dividends: float, shares_outstanding: float) -> float:
    """DPS = total_dividends / shares_outstanding."""
    return safe_divide(total_dividends, shares_outstanding, denominator_name="shares_outstanding")


def yield_on_cost(dividend_per_share: float, average_cost_per_share: float) -> float:
    """Yield on Cost = dividend_per_share / average_cost_per_share."""
    return safe_divide(
        dividend_per_share, average_cost_per_share, denominator_name="average_cost_per_share"
    )
