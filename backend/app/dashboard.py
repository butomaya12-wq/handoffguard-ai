"""Read-only, role-gated analytics for the single-tenant synthetic demo.

No dates on Change: UUID ordering is deterministic, not chronological.
No reason/notes/customer evidence/prices/actor IDs are exported.
"""
from typing import Literal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .models import Change, Order

Status = Literal[
    "DRAFT", "ASSESSMENT_REQUIRED", "PENDING_APPROVAL",
    "INTERNALLY_APPROVED", "APPLIED", "REJECTED",
]
STATUSES = (
    "DRAFT", "ASSESSMENT_REQUIRED", "PENDING_APPROVAL",
    "INTERNALLY_APPROVED", "APPLIED", "REJECTED",
)
MAX_ITEMS = 25


def build_dashboard(db: Session, *, status: Status | None = None) -> dict:
    """All aggregate counts are unfiltered; the detail list honors status."""
    status_rows = db.execute(
        select(Change.status, func.count(Change.id)).group_by(Change.status)
    ).all()
    by_status = {key: 0 for key in STATUSES}
    for key, count in status_rows:
        if key in by_status:
            by_status[key] = int(count)
    # Preserve total even if legacy/unknown statuses exist; expose no free text.
    total = sum(int(count) for _, count in status_rows)
    unknown_count = total - sum(by_status.values())

    stmt = (
        select(
            Change.id, Change.order_id, Change.status,
            Change.baseline_revision, Change.requested_quantity,
            Order.revision.label("current_order_revision"),
        )
        .join(Order, Order.id == Change.order_id)
        .order_by(Change.id)
        .limit(MAX_ITEMS)
    )
    if status is not None:
        stmt = stmt.where(Change.status == status)

    items = [
        {
            "id": record.id,
            "order_id": record.order_id,
            "status": record.status,
            "baseline_revision": record.baseline_revision,
            "current_order_revision": record.current_order_revision,
            "requested_quantity": record.requested_quantity,
        }
        for record in db.execute(stmt).all()
    ]
    return {
        "total": total,
        "by_status": by_status,
        "unknown_count": unknown_count,
        "filter": status,
        "filtered_total": by_status[status] if status else total,
        "limit": MAX_ITEMS,
        "items": items,
    }
