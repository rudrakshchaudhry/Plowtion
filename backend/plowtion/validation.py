"""Request validation helpers."""

from __future__ import annotations

import math
from typing import Any, Mapping

# Physically plausible bounds (inclusive). They are deliberately wider than the
# training data so that realistic inputs are accepted, while garbage is rejected.
FEATURE_BOUNDS: dict[str, tuple[float, float]] = {
    "N": (0.0, 500.0),  # nitrogen ratio in soil
    "P": (0.0, 500.0),  # phosphorus ratio in soil
    "K": (0.0, 500.0),  # potassium ratio in soil
    "temperature": (-20.0, 60.0),  # degrees Celsius
    "humidity": (0.0, 100.0),  # relative humidity, percent
    "ph": (0.0, 14.0),
    "rainfall": (0.0, 5000.0),  # millimetres
}


class ValidationError(ValueError):
    def __init__(self, errors: dict[str, str]):
        super().__init__("; ".join(f"{k}: {v}" for k, v in errors.items()))
        self.errors = errors


def _lookup(payload: Mapping[str, Any], name: str) -> Any:
    if name in payload:
        return payload[name]
    lowered = {str(k).lower(): v for k, v in payload.items()}
    return lowered.get(name.lower())


def parse_number(value: Any, name: str, bounds: tuple[float, float]) -> float:
    if value is None or (isinstance(value, str) and value.strip() == ""):
        raise ValidationError({name: "is required"})
    if isinstance(value, bool):
        raise ValidationError({name: "must be a number"})
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValidationError({name: "must be a number"}) from None
    if not math.isfinite(number):
        raise ValidationError({name: "must be a finite number"})
    lo, hi = bounds
    if not lo <= number <= hi:
        raise ValidationError({name: f"must be between {lo:g} and {hi:g}"})
    return number


def validate_fields(payload: Any, fields: Mapping[str, tuple[float, float]]) -> dict[str, float]:
    """Validate that ``payload`` contains every field in range. Keys match case-insensitively."""
    if not isinstance(payload, Mapping):
        raise ValidationError({"body": "must be a JSON object"})
    values: dict[str, float] = {}
    errors: dict[str, str] = {}
    for name, bounds in fields.items():
        try:
            values[name] = parse_number(_lookup(payload, name), name, bounds)
        except ValidationError as exc:
            errors.update(exc.errors)
    if errors:
        raise ValidationError(errors)
    return values
