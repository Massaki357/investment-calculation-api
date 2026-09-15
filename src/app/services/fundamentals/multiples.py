"""Valuation multiples and yields."""

from app.utils.math import safe_divide


def price_to_earnings(share_price: float, earnings_per_share: float) -> float:
    """P/E = share_price / earnings_per_share."""
    return safe_divide(share_price, earnings_per_share, denominator_name="earnings_per_share")


def price_to_book(share_price: float, book_value_per_share: float) -> float:
    """P/B = share_price / book_value_per_share."""
    return safe_divide(share_price, book_value_per_share, denominator_name="book_value_per_share")


def price_to_sales(market_capitalization: float, revenue: float) -> float:
    """P/S = market_capitalization / revenue."""
    return safe_divide(market_capitalization, revenue, denominator_name="revenue")


def ev_to_ebitda(enterprise_value: float, ebitda: float) -> float:
    """EV/EBITDA = enterprise_value / ebitda."""
    return safe_divide(enterprise_value, ebitda, denominator_name="ebitda")


def ev_to_ebit(enterprise_value: float, ebit: float) -> float:
    """EV/EBIT = enterprise_value / ebit."""
    return safe_divide(enterprise_value, ebit, denominator_name="ebit")


def ev_to_revenue(enterprise_value: float, revenue: float) -> float:
    """EV/Revenue = enterprise_value / revenue."""
    return safe_divide(enterprise_value, revenue, denominator_name="revenue")


def ev_to_free_cash_flow(enterprise_value: float, free_cash_flow: float) -> float:
    """EV/FCF = enterprise_value / free_cash_flow."""
    return safe_divide(enterprise_value, free_cash_flow, denominator_name="free_cash_flow")


def earnings_yield(earnings_per_share: float, share_price: float) -> float:
    """Earnings Yield = earnings_per_share / share_price (inverse of P/E)."""
    return safe_divide(earnings_per_share, share_price, denominator_name="share_price")


def operating_earnings_yield(ebit: float, enterprise_value: float) -> float:
    """Operating Earnings Yield (Greenblatt) = ebit / enterprise_value."""
    return safe_divide(ebit, enterprise_value, denominator_name="enterprise_value")


def free_cash_flow_yield(free_cash_flow: float, market_capitalization: float) -> float:
    """FCF Yield = free_cash_flow / market_capitalization."""
    return safe_divide(
        free_cash_flow, market_capitalization, denominator_name="market_capitalization"
    )


def ebitda_yield(ebitda: float, enterprise_value: float) -> float:
    """EBITDA Yield = ebitda / enterprise_value."""
    return safe_divide(ebitda, enterprise_value, denominator_name="enterprise_value")


def peg_ratio(pe_ratio: float, earnings_growth_rate: float) -> float:
    """PEG = pe_ratio / (earnings_growth_rate × 100).

    The growth rate arrives as a decimal (0.15) but PEG is conventionally computed with
    growth in percentage points (15), hence the × 100.
    """
    return safe_divide(
        pe_ratio, earnings_growth_rate * 100, denominator_name="earnings_growth_rate"
    )
