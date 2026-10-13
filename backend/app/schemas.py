"""Typed API inputs; business calculation is deliberately outside the LLM."""
from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class CreateOrder(BaseModel):
    product_code: str = Field(min_length=1, max_length=100)
    quantity: int = Field(gt=0)
    unit_sales_price_kopeks: int = Field(ge=0)
    unit_est_cost_kopeks: int | None = Field(default=None, ge=0)
    delivery_date: date
    approved_source_id: str = Field(min_length=1, max_length=128)


class ProductionReviewInput(BaseModel):
    production_status: Literal["NOT_STARTED", "IN_PRODUCTION", "COMPLETED"]
    completed_quantity: int = Field(ge=0)
    feasibility: Literal["CONFIRMED", "NOT_FEASIBLE", "UNKNOWN"]
    note: str = Field(min_length=1)


class ChangeInput(BaseModel):
    reason: str = Field(min_length=1)
    requested_quantity: int | None = Field(default=None, gt=0)
    requested_unit_sales_price_kopeks: int | None = Field(default=None, ge=0)
    requested_unit_est_cost_kopeks: int | None = Field(default=None, ge=0)
    requested_delivery_date: date | None = None
    one_time_change_cost_kopeks: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def at_least_one_requested_change(self):
        if all(getattr(self, key) is None for key in (
            "requested_quantity", "requested_unit_sales_price_kopeks",
            "requested_unit_est_cost_kopeks", "requested_delivery_date",
            "one_time_change_cost_kopeks")):
            raise ValueError("At least one changed field is required")
        return self


class DecisionInput(BaseModel):
    action: Literal["APPROVE", "REJECT"]
    assessment_fingerprint: str = Field(min_length=64, max_length=64)
    note: str = Field(min_length=1)


class CustomerAcceptanceInput(BaseModel):
    quantity: int = Field(gt=0)
    unit_sales_price_kopeks: int = Field(ge=0)
    delivery_date: date
    source_name: str = Field(min_length=1, max_length=200)
    evidence_text: str = Field(min_length=1)
