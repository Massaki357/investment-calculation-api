"""Declarative registration of single-value metric endpoints.

Most calculations share one shape: POST a request model, run a pure service function,
return a MetricResponse. Each one is declared as a MetricEndpoint (path, formula, example,
compute) and registered here, so every endpoint gets the same documentation, examples,
error responses and output guards without repeating route boilerplate.

Calculations with structured results (DCF, DuPont, optimizers...) use explicit routes instead.
"""

import inspect
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from typing import Annotated, Any

from fastapi import APIRouter, Body

from app.schemas.common import BaseRequest, MetricResponse, Unit, error_responses
from app.utils.validation import ensure_finite

_UNIT_HINTS: dict[Unit, str] = {
    Unit.MULTIPLE: "ratio read as 'x'",
    Unit.DECIMAL: "decimal form, 0.10 = 10%",
    Unit.AMOUNT: "monetary value in the input currency",
    Unit.INDEX: "indicator on its own conventional scale",
    Unit.YEARS: "time in years",
    Unit.NUMBER: "dimensionless number",
}


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
        return self.path.strip("/").replace("-", "_").replace("/", "_")

    def build_response(self, payload: RequestT) -> MetricResponse:
        value = ensure_finite(self.compute(payload), self.metric)
        currency = getattr(payload, "currency", None) if self.unit is Unit.AMOUNT else None
        return MetricResponse(metric=self.metric, value=value, unit=self.unit, currency=currency)

    def description(self) -> str:
        lines = [
            f"{self.summary}.",
            "",
            f"**Formula:** `{self.formula}`",
            "",
            f"**Unit:** `{self.unit.value}` ({_UNIT_HINTS[self.unit]}).",
        ]
        if self.notes:
            lines += ["", "**Assumptions and notes:**", *(f"- {note}" for note in self.notes)]
        return "\n".join(lines)


def add_metric_endpoints(router: APIRouter, endpoints: Iterable[MetricEndpoint[Any]]) -> None:
    for endpoint in endpoints:
        _add_metric_endpoint(router, endpoint)


def _add_metric_endpoint(router: APIRouter, endpoint: MetricEndpoint[Any]) -> None:
    # Validating and computing the example at import time guarantees docs never drift.
    example_request = endpoint.request_model.model_validate(endpoint.example)
    example_response = endpoint.build_response(example_request)

    def handler(payload: BaseRequest) -> MetricResponse:
        return endpoint.build_response(payload)

    body = Body(
        openapi_examples={"example": {"summary": endpoint.summary, "value": endpoint.example}}
    )
    handler.__signature__ = inspect.Signature(  # type: ignore[attr-defined]
        parameters=[
            inspect.Parameter(
                "payload",
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
                annotation=Annotated[endpoint.request_model, body],
            )
        ],
        return_annotation=MetricResponse,
    )
    handler.__name__ = endpoint.name

    router.add_api_route(
        endpoint.path,
        handler,
        methods=["POST"],
        name=endpoint.name,
        summary=endpoint.metric,
        description=endpoint.description(),
        response_model=MetricResponse,
        responses={
            200: {
                "description": "Calculated metric.",
                "content": {
                    "application/json": {"example": example_response.model_dump(mode="json")}
                },
            },
            **error_responses(),
        },
    )
