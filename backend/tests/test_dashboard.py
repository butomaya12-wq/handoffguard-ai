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
