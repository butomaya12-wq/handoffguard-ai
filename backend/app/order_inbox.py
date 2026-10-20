"""Read-only role-scoped order inbox, no migration or notification side effects.

An order needs attention if no ProductionReview exists for its *current*
approved revision. Merely opening a page never marks a review complete.
"""
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .models import Order, OrderRevision, ProductionReview


def list_order_inbox(db: Session, *, limit: int = 25, offset: int = 0) -> dict:
    reviewed_current = (
        select(ProductionReview.id)
        .where(
            ProductionReview.order_id == Order.id,
            ProductionReview.order_revision == Order.revision,
        )
        .exists()
    )
    needs_review = ~reviewed_current
    total = db.scalar(select(func.count(Order.id))) or 0
    attention_total = db.scalar(
        select(func.count(Order.id)).where(needs_review)
    ) or 0
    records = db.execute(
        select(
            Order.id,
            Order.product_code,
            Order.quantity,
            Order.revision,
            Order.production_status,
            Order.completed_quantity,
            Order.delivery_date,
            OrderRevision.created_at.label("revision_recorded_at"),
            needs_review.label("needs_review"),
        )
        .join(
            OrderRevision,
            (OrderRevision.order_id == Order.id)
            & (OrderRevision.revision_number == Order.revision),
        )
        .order_by(
            needs_review.desc(),
            OrderRevision.created_at.desc(),
            Order.id.asc(),
        )
        .offset(offset)
        .limit(limit)
    ).all()
    return {
        "total": total,
        "needs_review": attention_total,
        "limit": limit,
        "offset": offset,
        "items": [
            {
                "id": row.id,
                "product_code": row.product_code,
                "quantity": row.quantity,
                "revision": row.revision,
                "production_status": row.production_status,
                "completed_quantity": row.completed_quantity,
                "delivery_date": row.delivery_date,
                "revision_recorded_at": row.revision_recorded_at,
                "needs_review": bool(row.needs_review),
            }
            for row in records
        ],
    }
