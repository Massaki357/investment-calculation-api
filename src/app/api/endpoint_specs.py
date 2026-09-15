"""Declarative endpoint specifications.

Calculations are declared as data and registered here, so every endpoint gets the same
documentation layout, request/response examples, error responses and output guards:

- MetricEndpoint: single-value result returned as MetricResponse.
- CalculationEndpoint: structured result with its own response model.

Every documented example is validated and executed at import time, so the documentation
cannot drift from the code.
"""

import inspect
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from typing import Annotated, Any

from fastapi import APIRouter, Body, Request
from pydantic import BaseModel

from app.core.config import Settings, use_settings
from app.core.exceptions import NonFiniteResultError
from app.schemas.common import BaseRequest, MetricResponse, Unit, error_responses
from app.utils.validation import ensure_finite, ensure_max_length

_UNIT_HINTS: dict[Unit, str] = {
    Unit.MULTIPLE: "ratio read as 'x'",
    Unit.DECIMAL: "decimal form, 0.10 = 10%",
    Unit.AMOUNT: "monetary value in the input currency",
    Unit.INDEX: "indicator on its own conventional scale",
    Unit.YEARS: "time in years",
    Unit.NUMBER: "dimensionless number",
}

Examples = Mapping[str, Mapping[str, Any]]


def _route_name(path: str) -> str:
    return path.strip("/").replace("-", "_").replace("/", "_")


def _describe(
    summary: str, formulas: Iterable[str], extra: Iterable[str], notes: Iterable[str]
) -> str:
    formulas = tuple(formulas)
    notes = tuple(notes)
    lines = [f"{summary}.", ""]
    if len(formulas) == 1:
        lines.append(f"**Formula:** `{formulas[0]}`")
    else:
        lines += ["**Formulas:**", *(f"- `{formula}`" for formula in formulas)]
    for line in extra:
        lines += ["", line]
    if notes:
        lines += ["", "**Assumptions and notes:**", *(f"- {note}" for note in notes)]
    return "\n".join(lines)


def enforce_series_limit(model: BaseModel, limit: int) -> None:
    """Raise LimitExceededError if any list in the request (at any depth) exceeds `limit` items."""

    def walk(value: Any, path: str) -> None:
        if isinstance(value, BaseModel):
            for field_name in type(value).model_fields:
                walk(getattr(value, field_name), f"{path}.{field_name}" if path else field_name)
        elif isinstance(value, list):
            ensure_max_length(value, limit, path)
            for index, item in enumerate(value):
                if isinstance(item, BaseModel | list):
                    walk(item, f"{path}[{index}]")

    walk(model, "")


def ensure_finite_model(model: BaseModel) -> None:
    """Raise NonFiniteResultError if any float inside a response model is NaN or infinite."""

    def walk(value: Any, path: str) -> None:
        if isinstance(value, float):
            ensure_finite(value, path)
        elif isinstance(value, dict):
            for key, item in value.items():
                walk(item, f"{path}.{key}" if path else str(key))
        elif isinstance(value, list | tuple):
            for index, item in enumerate(value):
                walk(item, f"{path}[{index}]")

    try:
        walk(model.model_dump(), "")
    except NonFiniteResultError as exc:
        raise NonFiniteResultError(f"{exc.message} (the result is too large to represent)") from exc


@dataclass(frozen=True, kw_only=True, slots=True)
class MetricEndpoint[RequestT: BaseRequest]:
    path: str
    metric: str
    unit: Unit
    summary: str
    formula: str
    request_model: type[RequestT]
    compute: Callable[[RequestT], float]
    example: Mapping[str, Any]
    notes: tuple[str, ...] = ()

    @property
    def name(self) -> str:
        return _route_name(self.path)

    def build_response(self, payload: RequestT) -> MetricResponse:
        value = ensure_finite(self.compute(payload), self.metric)
        currency = getattr(payload, "currency", None) if self.unit is Unit.AMOUNT else None
        return MetricResponse(metric=self.metric, value=value, unit=self.unit, currency=currency)

    def description(self) -> str:
        unit_line = f"**Unit:** `{self.unit.value}` ({_UNIT_HINTS[self.unit]})."
        return _describe(self.summary, (self.formula,), (unit_line,), self.notes)


@dataclass(frozen=True, kw_only=True, slots=True)
class CalculationEndpoint[RequestT: BaseRequest, ResponseT: BaseModel]:
    path: str
    title: str
    summary: str
    formulas: tuple[str, ...]
    request_model: type[RequestT]
    response_model: type[ResponseT]
    compute: Callable[[RequestT], ResponseT]
    examples: Examples
    notes: tuple[str, ...] = ()

    @property
    def name(self) -> str:
        return _route_name(self.path)

    def build_response(self, payload: RequestT) -> ResponseT:
        response = self.compute(payload)
        ensure_finite_model(response)
        return response

    def description(self) -> str:
        return _describe(self.summary, self.formulas, (), self.notes)


def add_metric_endpoints(router: APIRouter, endpoints: Iterable[MetricEndpoint[Any]]) -> None:
    for endpoint in endpoints:
        example_response = endpoint.build_response(
            endpoint.request_model.model_validate(endpoint.example)
        )
        _register(
            router,
            path=endpoint.path,
            name=endpoint.name,
            title=endpoint.metric,
            description=endpoint.description(),
            request_model=endpoint.request_model,
            response_model=MetricResponse,
            request_examples={"example": (endpoint.summary, endpoint.example)},
            response_examples={"example": example_response.model_dump(mode="json")},
            build_response=endpoint.build_response,
        )


def add_calculation_endpoints(
    router: APIRouter, endpoints: Iterable[CalculationEndpoint[Any, Any]]
) -> None:
    for endpoint in endpoints:
        response_examples = {
            name: endpoint.build_response(
                endpoint.request_model.model_validate(example)
            ).model_dump(mode="json")
            for name, example in endpoint.examples.items()
        }
        _register(
            router,
            path=endpoint.path,
            name=endpoint.name,
            title=endpoint.title,
            description=endpoint.description(),
            request_model=endpoint.request_model,
            response_model=endpoint.response_model,
            request_examples={
                name: (name.replace("_", " ").capitalize(), example)
                for name, example in endpoint.examples.items()
            },
            response_examples=response_examples,
            build_response=endpoint.build_response,
        )


def _register(
    router: APIRouter,
    *,
    path: str,
    name: str,
    title: str,
    description: str,
    request_model: type[BaseRequest],
    response_model: type[BaseModel],
    request_examples: Mapping[str, tuple[str, Mapping[str, Any]]],
    response_examples: Mapping[str, Any],
    build_response: Callable[[Any], BaseModel],
) -> None:
    def handler(request: Request, payload: BaseRequest) -> BaseModel:
        settings: Settings = request.app.state.settings
        enforce_series_limit(payload, settings.max_series_length)
        with use_settings(settings):
            return build_response(payload)

    body = Body(
        openapi_examples={
            key: {"summary": summary, "value": value}
            for key, (summary, value) in request_examples.items()
        }
    )
    handler.__signature__ = inspect.Signature(  # type: ignore[attr-defined]
        parameters=[
            inspect.Parameter(
                "request", inspect.Parameter.POSITIONAL_OR_KEYWORD, annotation=Request
            ),
            inspect.Parameter(
                "payload",
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
                annotation=Annotated[request_model, body],
            ),
        ],
        return_annotation=response_model,
    )
    handler.__name__ = name

    router.add_api_route(
        path,
        handler,
        methods=["POST"],
        name=name,
        summary=title,
        description=description,
        response_model=response_model,
        responses={
            200: {
                "description": "Calculation result.",
                "content": {
                    "application/json": {
                        "examples": {
                            key: {"value": value} for key, value in response_examples.items()
                        }
                    }
                },
            },
            **error_responses(),
        },
    )
