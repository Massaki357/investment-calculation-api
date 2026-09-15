"""Wall-clock budget for one calculation request.

The endpoint handler opens a budget; long-running calculations call `check_time_budget()` at safe
points (optimizer iterations, simulation batches, scenario evaluations) and stop with
LIMIT_EXCEEDED once it is spent. Outside a budget (e.g. unit tests of services) checks are no-ops.
"""

import time
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass

from app.core.exceptions import CalculationTimeoutError


@dataclass(frozen=True, slots=True)
class _Budget:
    deadline: float
    seconds: float


_active_budget: ContextVar[_Budget | None] = ContextVar("time_budget", default=None)


@contextmanager
def time_budget(seconds: float) -> Iterator[None]:
    token = _active_budget.set(_Budget(deadline=time.monotonic() + seconds, seconds=seconds))
    try:
        yield
    finally:
        _active_budget.reset(token)


def check_time_budget() -> None:
    budget = _active_budget.get()
    if budget is not None and time.monotonic() > budget.deadline:
        raise CalculationTimeoutError(
            f"the calculation exceeded the time limit of {budget.seconds:g} seconds"
        )
