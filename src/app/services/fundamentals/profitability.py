"""Profitability ratios, margins, turnover and DuPont decomposition."""

from dataclasses import dataclass

from app.utils.math import safe_divide


def return_on_equity(net_income: float, shareholders_equity: float) -> float:
    """ROE = net_income / shareholders_equity."""
    return safe_divide(net_income, shareholders_equity, denominator_name="shareholders_equity")


def return_on_assets(net_income: float, total_assets: float) -> float:
    """ROA = net_income / total_assets."""
    return safe_divide(net_income, total_assets, denominator_name="total_assets")


def nopat(ebit: float, tax_rate: float) -> float:
    """NOPAT = ebit × (1 − tax_rate)."""
    return ebit * (1 - tax_rate)


def invested_capital(
    total_debt: float, shareholders_equity: float, cash_and_equivalents: float
) -> float:
    """Invested Capital (financing approach) = total_debt + shareholders_equity − cash."""
    return total_debt + shareholders_equity - cash_and_equivalents


def return_on_invested_capital(ebit: float, tax_rate: float, invested_capital: float) -> float:
    """ROIC = NOPAT / invested_capital, with NOPAT = ebit × (1 − tax_rate)."""
    return safe_divide(nopat(ebit, tax_rate), invested_capital, denominator_name="invested_capital")


def return_on_capital_employed(
    ebit: float, total_assets: float, current_liabilities: float
) -> float:
    """ROCE = ebit / (total_assets − current_liabilities)."""
    return safe_divide(
        ebit,
        total_assets - current_liabilities,
        denominator_name="capital_employed (total_assets - current_liabilities)",
    )


def margin(numerator: float, revenue: float) -> float:
    """Margin = numerator / revenue (gross profit, EBITDA, EBIT, net income or FCF)."""
    return safe_divide(numerator, revenue, denominator_name="revenue")


def asset_turnover(revenue: float, total_assets: float) -> float:
    """Asset Turnover = revenue / total_assets."""
    return safe_divide(revenue, total_assets, denominator_name="total_assets")


@dataclass(frozen=True, slots=True)
class DuPontThreeFactor:
    net_profit_margin: float
    asset_turnover: float
    equity_multiplier: float

    @property
    def return_on_equity(self) -> float:
        return self.net_profit_margin * self.asset_turnover * self.equity_multiplier


@dataclass(frozen=True, slots=True)
class DuPontFiveFactor:
    tax_burden: float
    interest_burden: float
    operating_margin: float
    asset_turnover: float
    equity_multiplier: float

    @property
    def return_on_equity(self) -> float:
        return (
            self.tax_burden
            * self.interest_burden
            * self.operating_margin
            * self.asset_turnover
            * self.equity_multiplier
        )


def equity_multiplier(total_assets: float, shareholders_equity: float) -> float:
    """Equity Multiplier = total_assets / shareholders_equity."""
    return safe_divide(total_assets, shareholders_equity, denominator_name="shareholders_equity")


def dupont_three_factor(
    net_income: float, revenue: float, total_assets: float, shareholders_equity: float
) -> DuPontThreeFactor:
    """ROE = (net_income / revenue) × (revenue / total_assets) × (total_assets / equity)."""
    return DuPontThreeFactor(
        net_profit_margin=margin(net_income, revenue),
        asset_turnover=asset_turnover(revenue, total_assets),
        equity_multiplier=equity_multiplier(total_assets, shareholders_equity),
    )


def dupont_five_factor(
    net_income: float,
    pretax_income: float,
    ebit: float,
    revenue: float,
    total_assets: float,
    shareholders_equity: float,
) -> DuPontFiveFactor:
    """ROE = (NI/EBT) × (EBT/EBIT) × (EBIT/revenue) × (revenue/assets) × (assets/equity)."""
    return DuPontFiveFactor(
        tax_burden=safe_divide(net_income, pretax_income, denominator_name="pretax_income"),
        interest_burden=safe_divide(pretax_income, ebit, denominator_name="ebit"),
        operating_margin=margin(ebit, revenue),
        asset_turnover=asset_turnover(revenue, total_assets),
        equity_multiplier=equity_multiplier(total_assets, shareholders_equity),
    )
