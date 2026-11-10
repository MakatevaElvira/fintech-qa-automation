"""Dataclasses of test data, built from env configs (ui_data / api_data)."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ProductFilterCase:
    products: list[str]


@dataclass(frozen=True)
class StatusFilterCase:
    statuses: list[str]
    label: str | None = None


@dataclass(frozen=True)
class AmountFilterCase:
    amount_min: int
    amount_max: int


@dataclass(frozen=True)
class ApiListCase:
    params: dict = field(default_factory=dict)
    expected_status: int = 200
    error_field: str | None = None

    @property
    def negative(self) -> bool:
        return self.expected_status >= 400
