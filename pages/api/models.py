"""Pydantic models of API responses (contracts)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Product = Literal["PDL", "Installment", "Credit line"]
Status = Literal["approved", "rejected", "pending"]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Check(Strict):
    uuid: str = Field(pattern=r"^[0-9a-f-]{36}$")
    check_type: Literal["bureau", "antifraud", "income", "ai_scoring"]
    product: Product
    risk_flag: bool
    ai_verdict: Literal["low risk", "medium risk", "high risk"] | None


class Application(Strict):
    uuid: str = Field(pattern=r"^[0-9a-f-]{36}$")
    external_id: str | None
    client_name: str
    product: Product
    status: Status
    channel: Literal["web", "mobile", "partner"]
    amount: int = Field(ge=0)
    created_at: str
    risk_flags: int = Field(ge=0)
    checks: list[Check] = Field(min_length=1)


class ApplicationsList(Strict):
    total: int = Field(ge=0)
    page: int = Field(ge=1)
    page_size: int
    items: list[Application]


class ErrorResponse(Strict):
    error: str
    fields: dict[str, str] | None = None


class SessionCreated(Strict):
    status: Literal["ok"]
