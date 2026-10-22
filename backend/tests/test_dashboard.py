"""Dashboard contract tests: real SQL, role checks, bounded rows and no writes."""
import json
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.main import create_app
from app.models import Change, Order, OrderRevision

TOKENS = {
    "test-sales-token": {"id": "sales-demo", "role": "sales"},
    "test-production-token": {"id": "production-demo", "role": "production"},
    "test-approver-token": {"id": "approver-demo", "role": "approver"},
}
URL = "/api/v1/analytics/changes"


@pytest.fixture
def analytics(tmp_path, monkeypatch):
    monkeypatch.setenv("HANDOFFGUARD_AUTH_TOKENS", json.dumps(TOKENS))
    url = f"sqlite:///{tmp_path / 'analytics.db'}"
    engine = create_engine(url)
    with TestClient(create_app(url)) as client:
        yield client, engine
    engine.dispose()


def headers(role: str):
    return {"Authorization": f"Bearer test-{role}-token"}


def seed_changes(engine, statuses):
    with Session(engine) as session:
        order = Order(
            product_code="SYNTHETIC-ONLY", quantity=100,
            unit_sales_price_kopeks=100000, delivery_date=date(2026, 11, 12),
            approved_source_id="synthetic-source", revision=1,
        )
        session.add(order)
        session.flush()
        session.add(OrderRevision(
            order_id=order.id, revision_number=1, product_code=order.product_code,
            quantity=100, unit_sales_price_kopeks=100000,
            delivery_date=date(2026, 11, 12), approved_source_id="synthetic-source",
        ))
        for status in statuses:
            session.add(Change(
                order_id=order.id, baseline_revision=1, status=status,
                reason="PRIVATE-CUSTOMER-REQUEST: never export",
                requested_quantity=120,
                assessment_result={"secret_note": "PRIVATE-ASSESSMENT"},
            ))
        session.commit()


def test_single_login_proves_role_without_exposing_identity(analytics):
    client, _ = analytics
    assert client.get("/api/v1/me").status_code == 401
    assert client.get("/api/v1/me", headers={"Authorization": "Bearer wrong"}).status_code == 401
    for role in ("sales", "production", "approver"):
        response = client.get("/api/v1/me", headers=headers(role))
        assert response.status_code == 200
        assert response.json() == {"role": role}
        assert "test-" not in response.text
        assert "demo" not in response.text


def test_empty_database_reports_zero_counts(analytics):
    client, _ = analytics
    response = client.get(URL, headers=headers("sales"))
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == data["filtered_total"] == 0
    assert all(value == 0 for value in data["by_status"].values())
    assert data["items"] == []
    assert data["unknown_count"] == 0
    assert data["limit"] == 25


def test_real_status_grouping_filtering_bound_and_privacy(analytics):
    client, engine = analytics
    statuses = (
        ["DRAFT"] * 26
        + ["ASSESSMENT_REQUIRED", "PENDING_APPROVAL",
           "INTERNALLY_APPROVED", "APPLIED", "REJECTED"]
    )
    seed_changes(engine, statuses)
    before = snapshot(engine)
    response = client.get(URL, headers=headers("sales"))
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["total"] == 31
    assert data["filtered_total"] == 31
    assert data["by_status"] == {
        "DRAFT": 26, "ASSESSMENT_REQUIRED": 1, "PENDING_APPROVAL": 1,
        "INTERNALLY_APPROVED": 1, "APPLIED": 1, "REJECTED": 1,
    }
    assert len(data["items"]) == 25
    assert data["items"] == sorted(data["items"], key=lambda item: item["id"])
    assert set(data["items"][0]) == {
        "id", "order_id", "status", "baseline_revision",
        "current_order_revision", "requested_quantity",
    }
    assert "PRIVATE-CUSTOMER-REQUEST" not in response.text
    assert "PRIVATE-ASSESSMENT" not in response.text
    assert "synthetic-source" not in response.text
    assert "unit_sales_price_kopeks" not in response.text

    filtered = client.get(URL + "?status=APPLIED", headers=headers("approver"))
    assert filtered.status_code == 200
    assert filtered.json()["filter"] == "APPLIED"
    assert filtered.json()["filtered_total"] == 1
    assert filtered.json()["total"] == 31
    assert len(filtered.json()["items"]) == 1
    assert filtered.json()["items"][0]["status"] == "APPLIED"
    assert snapshot(engine) == before, "Analytics endpoint changed DB state"


def snapshot(engine):
    with Session(engine) as session:
        return (
            session.scalar(select(func.count()).select_from(Order)),
            session.scalar(select(func.count()).select_from(OrderRevision)),
            session.scalar(select(func.count()).select_from(Change)),
            session.scalars(select(Change.status).order_by(Change.id)).all(),
        )


def test_roles_and_filter_validation(analytics):
    client, _ = analytics
    assert client.get(URL).status_code == 401
    assert client.get(URL, headers={"Authorization": "Bearer invalid"}).status_code == 401
    assert client.get(URL, headers=headers("production")).status_code == 403
    assert client.get(URL, headers=headers("approver")).status_code == 200
    assert client.get(URL + "?status=INVALID", headers=headers("sales")).status_code == 422
    assert client.get(URL + "?status=applied", headers=headers("sales")).status_code == 422
    assert client.get(URL + "?status=APPLIED", headers=headers("sales")).status_code == 200


def test_unknown_legacy_status_counts_without_exposing_text(analytics):
    client, engine = analytics
    seed_changes(engine, ["DRAFT", "PRIVATE-CUSTOMER-TEXT"])
    data = client.get(URL, headers=headers("sales")).json()
    assert data["total"] == 2
    assert data["by_status"]["DRAFT"] == 1
    assert data["unknown_count"] == 1
    assert data["filtered_total"] == 2
    assert "PRIVATE-CUSTOMER-TEXT" not in str(data)
    assert {row["status"] for row in data["items"]} == {"DRAFT", "UNKNOWN"}


def test_inbox_shows_new_order_to_production_without_uuid_handoff(analytics):
    client, engine = analytics
    inbox_url = "/api/v1/orders/inbox"
    assert client.get(inbox_url).status_code == 401
    assert client.get(inbox_url, headers=headers("production")).json() == {
        "total": 0, "needs_review": 0, "limit": 25, "offset": 0, "items": []
    }
    seed_changes(engine, ["DRAFT"])
    before = snapshot(engine)
    for role in ("sales", "production", "approver"):
        response = client.get(inbox_url, headers=headers(role))
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == data["needs_review"] == 1
        assert len(data["items"]) == 1
        assert data["items"][0]["product_code"] == "SYNTHETIC-ONLY"
        assert data["items"][0]["needs_review"] is True
        assert data["items"][0]["quantity"] == 100
        assert data["items"][0]["revision"] == 1
        assert set(data["items"][0]) == {
            "id", "product_code", "quantity", "revision",
            "production_status", "completed_quantity", "delivery_date",
            "revision_recorded_at", "needs_review",
        }
        assert "PRIVATE" not in response.text
        assert "unit_sales_price" not in response.text
        assert "approved_source" not in response.text
    assert snapshot(engine) == before, "Just viewing the inbox must not change order state"


def test_inbox_review_clears_attention_and_new_revision_requires_review(analytics):
    client, engine = analytics
    seed_changes(engine, [])
    inbox_url = "/api/v1/orders/inbox"
    response = client.get(inbox_url, headers=headers("production"))
    item = response.json()["items"][0]
    assert item["needs_review"]
    # A genuine production review, not a page view, resolves the attention badge.
    recorded = client.post(
        f"/api/v1/orders/{item['id']}/production-reviews",
        headers=headers("production"),
        json={
            "production_status": "NOT_STARTED", "completed_quantity": 0,
            "feasibility": "CONFIRMED", "note": "Synthetic review completed",
        },
    )
    assert recorded.status_code == 201, recorded.text
    reviewed = client.get(inbox_url, headers=headers("production")).json()
    assert reviewed["needs_review"] == 0
    assert reviewed["items"][0]["needs_review"] is False
    # Approved revisions need their own new review; synthetic isolated data only.
    with Session(engine) as session:
        order = session.get(Order, item["id"])
        order.revision = 2
        session.add(OrderRevision(
            order_id=order.id, revision_number=2, product_code=order.product_code,
            quantity=100, unit_sales_price_kopeks=order.unit_sales_price_kopeks,
            delivery_date=order.delivery_date, approved_source_id=order.approved_source_id,
        ))
        session.commit()
    revised = client.get(inbox_url, headers=headers("production")).json()
    assert revised["needs_review"] == 1
    assert revised["items"][0]["revision"] == 2
    assert revised["items"][0]["needs_review"] is True


def test_inbox_pagination_strict_validation_and_no_hidden_orders(analytics):
    client, engine = analytics
    with Session(engine) as session:
        for i in range(6):
            o = Order(
                product_code=f"DEMO-{i}", quantity=100,
                unit_sales_price_kopeks=100000, delivery_date=date(2026, 11, 12),
                approved_source_id="synthetic", revision=1,
            )
            session.add(o)
            session.flush()
            session.add(OrderRevision(
                order_id=o.id, revision_number=1, product_code=o.product_code,
                quantity=o.quantity, unit_sales_price_kopeks=100000,
                delivery_date=o.delivery_date, approved_source_id="synthetic",
            ))
        session.commit()
    for query in ("?limit=0", "?limit=101", "?offset=-1", "?limit=bad"):
        assert client.get("/api/v1/orders/inbox"+query, headers=headers("production")).status_code == 422
    a = client.get("/api/v1/orders/inbox?limit=4", headers=headers("production")).json()
    b = client.get("/api/v1/orders/inbox?limit=4&offset=4", headers=headers("production")).json()
    assert a["total"] == a["needs_review"] == 6
    assert len(a["items"]) == 4
    assert len(b["items"]) == 2
    assert len({x["id"] for x in a["items"]+b["items"]}) == 6


def test_inbox_auto_visibility_uses_latest_persisted_snapshot(analytics):
    client, engine = analytics
    assert client.get("/api/v1/orders/inbox", headers=headers("production")).json()["total"] == 0
    seed_changes(engine, [])
    assert client.get("/api/v1/orders/inbox", headers=headers("production")).json()["total"] == 1
