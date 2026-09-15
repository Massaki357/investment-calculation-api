from app.schemas.fundamentals.common import PeriodBalance
from app.services.fundamentals.balances import average_balance

AVERAGE_BALANCE_NOTE = (
    "Balance fields accept a number or {beginning, ending}; the latter uses the simple average."
)
SIGNED_RESULT_NOTE = "Negative denominators return the signed result without interpretation."


def resolve_balance(balance: float | PeriodBalance) -> float:
    if isinstance(balance, PeriodBalance):
        return average_balance(balance.beginning, balance.ending)
    return balance
