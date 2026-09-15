"""Reusable cross-field checks for request models (raise ValueError → HTTP 422)."""

from pydantic import BaseModel


def require_exactly_one(model: BaseModel, *field_names: str) -> None:
    provided = [name for name in field_names if getattr(model, name) is not None]
    if len(provided) != 1:
        raise ValueError(f"send exactly one of: {', '.join(field_names)}")


def require_fields(model: BaseModel, context: str, *field_names: str) -> None:
    missing = [name for name in field_names if getattr(model, name) is None]
    if missing:
        raise ValueError(f"{context} requires: {', '.join(missing)}")
