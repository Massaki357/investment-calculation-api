"""Liquidity ratios (Brazilian naming in parentheses)."""

from app.core.exceptions import InvalidInputError
from app.utils.math import safe_divide


def current_ratio(current_assets: float, current_liabilities: float) -> float:
    """Current Ratio (Liquidez Corrente) = current_assets / current_liabilities."""
    return safe_divide(current_assets, current_liabilities, denominator_name="current_liabilities")


def quick_ratio(current_assets: float, inventories: float, current_liabilities: float) -> float:
    """Quick Ratio (Liquidez Seca) = (current_assets − inventories) / current_liabilities."""
    if inventories > current_assets:
        raise InvalidInputError("inventories cannot exceed current_assets")
    return safe_divide(
        current_assets - inventories,
        current_liabilities,
        denominator_name="current_liabilities",
    )


def cash_ratio(
    cash_and_equivalents: float,
    current_liabilities: float,
    short_term_investments: float = 0,
) -> float:
    """Cash Ratio (Liquidez Imediata) = (cash + short_term_investments) / current_liabilities."""
    return safe_divide(
        cash_and_equivalents + short_term_investments,
        current_liabilities,
        denominator_name="current_liabilities",
    )


def general_liquidity_ratio(
    current_assets: float,
    long_term_receivables: float,
    current_liabilities: float,
    non_current_liabilities: float,
) -> float:
    """General Liquidity (Liquidez Geral) = (CA + long-term receivables) / (CL + NCL)."""
    return safe_divide(
        current_assets + long_term_receivables,
        current_liabilities + non_current_liabilities,
        denominator_name="total_liabilities (current_liabilities + non_current_liabilities)",
    )
