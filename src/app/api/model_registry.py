"""Registry of calculation endpoints that scenario tools can evaluate.

Sensitivity and scenario analysis never execute user-supplied formulas: they re-run calculations
already published by the API, identified as "<domain>/<path>" (e.g. "valuation/dcf/fcff"), with
inputs validated by the same request model as the original endpoint.
"""

import copy
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ValidationError

from app.api.endpoint_specs import CalculationEndpoint, MetricEndpoint, enforce_series_limit
from app.core.config import current_settings
from app.core.exceptions import AppError, CalculationTimeoutError, InvalidInputError
from app.core.time_budget import check_time_budget


@dataclass(frozen=True, slots=True)
class RegisteredModel:
    model_id: str
    title: str
    request_model: type[BaseModel]
    build_response: Callable[[Any], BaseModel]


@dataclass(frozen=True, slots=True)
class Evaluation:
    output: float | None
    error_code: str | None = None
    error_message: str | None = None


class ModelRegistry:
    def __init__(self) -> None:
        self._models: dict[str, RegisteredModel] = {}

    def register_domain(
        self,
        domain: str,
        endpoints: Iterable[MetricEndpoint[Any] | CalculationEndpoint[Any, Any]],
    ) -> None:
        for endpoint in endpoints:
            model_id = f"{domain}{endpoint.path}"
            title = endpoint.metric if isinstance(endpoint, MetricEndpoint) else endpoint.title
            self._models[model_id] = RegisteredModel(
                model_id=model_id,
                title=title,
                request_model=endpoint.request_model,
                build_response=endpoint.build_response,
            )

    @property
    def models(self) -> list[RegisteredModel]:
        return sorted(self._models.values(), key=lambda model: model.model_id)

    def get(self, model_id: str) -> RegisteredModel:
        try:
            return self._models[model_id]
        except KeyError:
            raise InvalidInputError(
                f"unknown model '{model_id}'; see GET /api/v1/scenarios/models"
            ) from None

    def evaluate(self, model_id: str, inputs: Mapping[str, Any], output: str) -> Evaluation:
        """Run one registered calculation and extract a numeric output (errors are captured)."""
        model = self.get(model_id)
        check_time_budget()
        try:
            payload = model.request_model.model_validate(inputs)
            enforce_series_limit(payload, current_settings().max_series_length)
            response = model.build_response(payload)
        except ValidationError as exc:
            first = exc.errors()[0]
            location = ".".join(str(part) for part in first.get("loc", ()))
            return Evaluation(None, "VALIDATION_ERROR", f"{location}: {first.get('msg')}")
        except CalculationTimeoutError:
            raise  # the budget covers the whole request, not a single evaluation
        except AppError as exc:
            return Evaluation(None, exc.code, exc.message)
        return Evaluation(extract_number(response.model_dump(), output))


def extract_number(data: Any, path: str) -> float | None:
    """Follow a dotted path (dict keys or list indexes) and return a number, None or raise."""
    current = data
    for part in path.split("."):
        if isinstance(current, dict) and part in current:
            current = current[part]
        elif isinstance(current, list) and part.lstrip("-").isdigit():
            try:
                current = current[int(part)]
            except IndexError:
                raise InvalidInputError(f"output path '{path}' is out of range") from None
        else:
            raise InvalidInputError(f"output path '{path}' does not exist in the model response")
    if current is None:
        return None
    if isinstance(current, bool) or not isinstance(current, int | float):
        raise InvalidInputError(f"output path '{path}' does not point to a number")
    return float(current)


def with_overrides(base: Mapping[str, Any], overrides: Mapping[str, Any]) -> dict[str, Any]:
    """Deep copy of base with dotted-path overrides applied ("terminal.growth_rate": 0.02)."""
    result = copy.deepcopy(dict(base))
    for path, value in overrides.items():
        target = result
        parts = path.split(".")
        for part in parts[:-1]:
            child = target.get(part)
            if child is None:
                child = target[part] = {}
            if not isinstance(child, dict):
                raise InvalidInputError(f"cannot set '{path}': '{part}' is not an object")
            target = child
        target[parts[-1]] = copy.deepcopy(value)
    return result
