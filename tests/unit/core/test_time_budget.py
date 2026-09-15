import pytest

from app.core import time_budget as budget_module
from app.core.exceptions import CalculationTimeoutError, LimitExceededError
from app.core.time_budget import check_time_budget, time_budget
from app.services.portfolio import optimization
from app.services.portfolio.inputs import market_from_covariance


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


@pytest.fixture
def clock(monkeypatch: pytest.MonkeyPatch) -> FakeClock:
    fake = FakeClock()
    monkeypatch.setattr(budget_module.time, "monotonic", fake)
    return fake


def test_check_is_a_no_op_outside_a_budget() -> None:
    check_time_budget()


def test_check_passes_until_the_deadline(clock: FakeClock) -> None:
    with time_budget(5):
        clock.now += 5
        check_time_budget()
        clock.now += 0.001
        with pytest.raises(CalculationTimeoutError, match="time limit of 5 seconds"):
            check_time_budget()


def test_timeout_is_reported_as_limit_exceeded() -> None:
    error = CalculationTimeoutError("x")

    assert isinstance(error, LimitExceededError)
    assert error.code == "LIMIT_EXCEEDED"


def test_budget_is_removed_after_the_block(clock: FakeClock) -> None:
    with time_budget(1):
        pass
    clock.now += 100
    check_time_budget()


def test_optimizer_stops_when_the_budget_is_spent(clock: FakeClock) -> None:
    market = market_from_covariance([[0.04, 0.03], [0.03, 0.09]], None)
    with time_budget(1):
        clock.now += 2
        with pytest.raises(CalculationTimeoutError):
            optimization.minimum_variance(market)
        with pytest.raises(CalculationTimeoutError):
            optimization.risk_parity(market)
