"""Deterministic, side-effect-free change assessment (no AI arithmetic)."""
import hashlib
import json

from .models import Change, Order, ProductionReview


def impact_assessment(order: Order, change: Change, review: ProductionReview | None) -> dict:
    qty = change.requested_quantity if change.requested_quantity is not None else order.quantity
    unit_price = (change.requested_unit_sales_price_kopeks
                  if change.requested_unit_sales_price_kopeks is not None
                  else order.unit_sales_price_kopeks)
    delivery_date = change.requested_delivery_date or order.delivery_date
    issues = []

    if review is None or review.feasibility == "UNKNOWN":
        issues.append("PRODUCTION_FEASIBILITY_MISSING")
    elif review.feasibility == "NOT_FEASIBLE":
        issues.append("PRODUCTION_NOT_FEASIBLE")
    if review is not None and review.production_status == "COMPLETED":
        issues.append("PRODUCTION_ALREADY_COMPLETED")
    # For expedited deliveries, the incremental cost must not be guessed as zero.
    if delivery_date < order.delivery_date and change.one_time_change_cost_kopeks is None:
        issues.append("RUSH_COST_MISSING")

    old_revenue = order.quantity * order.unit_sales_price_kopeks
    new_revenue = qty * unit_price
    delta_revenue = new_revenue - old_revenue
    # Null estimated costs stay unknown; for an unchanged delivery date and zero
    # cost of change no extra cost is inferred if estimates are absent.
    new_unit_cost = (change.requested_unit_est_cost_kopeks
                     if change.requested_unit_est_cost_kopeks is not None
                     else order.unit_est_cost_kopeks)
    old_cost = order.quantity * order.unit_est_cost_kopeks if order.unit_est_cost_kopeks is not None else None
    extra_cost = change.one_time_change_cost_kopeks
    new_cost = qty * new_unit_cost + extra_cost if new_unit_cost is not None and extra_cost is not None else None
    delta_cost = new_cost - old_cost if new_cost is not None and old_cost is not None else None
    delta_contribution = delta_revenue - delta_cost if delta_cost is not None else None

    fingerprint_payload = {
        "order_id": order.id, "revision": order.revision,
        "order_quantity": order.quantity, "order_price": order.unit_sales_price_kopeks,
        "order_cost": order.unit_est_cost_kopeks,
        "order_date": order.delivery_date.isoformat(),
        "change_id": change.id,
        "change": {
            "quantity": change.requested_quantity, "price": change.requested_unit_sales_price_kopeks,
            "cost": change.requested_unit_est_cost_kopeks,
            "date": change.requested_delivery_date.isoformat() if change.requested_delivery_date else None,
            "extra_cost": change.one_time_change_cost_kopeks,
        },
        "production_review_id": review.id if review else None,
        "production_status": review.production_status if review else None,
        "completed_quantity": review.completed_quantity if review else None,
        "feasibility": review.feasibility if review else None,
    }
    fingerprint = hashlib.sha256(json.dumps(fingerprint_payload, sort_keys=True).encode()).hexdigest()
    return {
        "change_id": change.id,
        "readiness": "NEEDS_DATA" if issues else "READY_FOR_APPROVAL",
        "fingerprint": fingerprint,
        "issues": issues,
        "old_revenue_kopeks": old_revenue,
        "new_revenue_kopeks": new_revenue,
        "delta_revenue_kopeks": delta_revenue,
        "delta_est_cost_kopeks": delta_cost,
        "delta_est_contribution_kopeks": delta_contribution,
        "proposed_quantity": qty,
        "proposed_delivery_date": delivery_date.isoformat(),
        "can_promise_date": not issues,
    }
