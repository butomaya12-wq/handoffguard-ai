"""Persisted baseline, human production review, and proposed change records."""
from datetime import date, datetime, timezone
from uuid import uuid4

from sqlalchemy import Date, DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def make_id() -> str:
    return str(uuid4())


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Order(Base):
    __tablename__ = "orders"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=make_id)
    product_code: Mapped[str] = mapped_column(String(100))
    quantity: Mapped[int] = mapped_column(Integer)
    unit_sales_price_kopeks: Mapped[int] = mapped_column(Integer)
    unit_est_cost_kopeks: Mapped[int | None] = mapped_column(Integer, nullable=True)
    delivery_date: Mapped[date] = mapped_column(Date)
    approved_source_id: Mapped[str] = mapped_column(String(128))
    revision: Mapped[int] = mapped_column(Integer, default=1)
    production_status: Mapped[str] = mapped_column(String(32), default="NOT_STARTED")
    completed_quantity: Mapped[int] = mapped_column(Integer, default=0)


class ProductionReview(Base):
    __tablename__ = "production_reviews"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=make_id)
    order_id: Mapped[str] = mapped_column(ForeignKey("orders.id"), index=True)
    order_revision: Mapped[int] = mapped_column(Integer)
    production_status: Mapped[str] = mapped_column(String(32))
    completed_quantity: Mapped[int] = mapped_column(Integer)
    feasibility: Mapped[str] = mapped_column(String(32))
    note: Mapped[str] = mapped_column(Text)
    reviewer_id: Mapped[str] = mapped_column(String(128))
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class Change(Base):
    __tablename__ = "changes"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=make_id)
    order_id: Mapped[str] = mapped_column(ForeignKey("orders.id"), index=True)
    baseline_revision: Mapped[int] = mapped_column(Integer)
    reason: Mapped[str] = mapped_column(Text)
    requested_quantity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    requested_unit_sales_price_kopeks: Mapped[int | None] = mapped_column(Integer, nullable=True)
    requested_unit_est_cost_kopeks: Mapped[int | None] = mapped_column(Integer, nullable=True)
    requested_delivery_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    one_time_change_cost_kopeks: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(40), default="DRAFT")
    latest_fingerprint: Mapped[str | None] = mapped_column(String(64), nullable=True)
    latest_readiness: Mapped[str | None] = mapped_column(String(40), nullable=True)
    latest_review_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    assessment_result: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class ApprovalDecision(Base):
    __tablename__ = "approval_decisions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=make_id)
    change_id: Mapped[str] = mapped_column(ForeignKey("changes.id"), index=True)
    assessment_fingerprint: Mapped[str] = mapped_column(String(64))
    reviewer_id: Mapped[str] = mapped_column(String(128))
    action: Mapped[str] = mapped_column(String(16))
    note: Mapped[str] = mapped_column(Text)
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
