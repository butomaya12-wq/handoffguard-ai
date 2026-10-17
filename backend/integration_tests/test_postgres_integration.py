"""Real PostgreSQL verification on a disposable, local-only GitHub Actions service.

Deliberately outside backend/tests/: existing SQLite test suite remains unchanged.
Must not run against a real, hosted, shared, or production database.
"""

import json
import os

from fastapi.testclient import TestClient
from sqlalchemy.engine.url import make_url

from app.main import create_app


def guarded_ci_postgres_url() -> str:
    raw = os.environ.get("HANDOFFGUARD_TEST_POSTGRES_URL")
    if not raw:
        raise RuntimeError(
            "HANDOFFGUARD_TEST_POSTGRES_URL is required for explicit PostgreSQL CI integration tests"
        )
    url = make_url(raw)
    if (
        url.drivername != "postgresql+psycopg"
        or url.host not in {"localhost", "127.0.0.1"}
        or url.port != 5432
        or url.database != "handoffguard_ci"
        or url.username != "handoffguard_ci"
    ):
        raise RuntimeError(
            "Safety guard: integration tests may ONLY connect to the disposable "
            "localhost:5432/handoffguard_ci PostgreSQL service as handoffguard_ci"
        )
    return raw


def test_postgres_v1_to_v2_persistence_and_auth_after_restart(monkeypatch):
    """Use a real PG engine, enforce role gates, and reopen to verify durable V1/V2."""
    url = guarded_ci_postgres_url()
    role_records = {
        "ci-postgres-sales": {"id": "sales-ci-postgres", "role": "sales"},
        "ci-postgres-production": {"id": "production-ci-postgres", "role": "production"},
        "ci-postgres-approver": {"id": "approver-ci-postgres", "role": "approver"},
    }
    monkeypatch.setenv("HANDOFFGUARD_AUTH_TOKENS", json.dumps(role_records))
    headers = {
        role: {"Authorization": f"Bearer ci-postgres-{role}"}
        for role in ("sales", "production", "approver")
    }

    with TestClient(create_app(url)) as api:
        # Authentication is enforced by FastAPI on real PostgreSQL, not by a mock.
        unauthenticated = api.get("/api/v1/orders/not-found")
        assert unauthenticated.status_code == 401, unauthenticated.text

        created = api.post(
            "/api/v1/orders",
            headers=headers["sales"],
            json={
                "product_code": "SYNTHETIC-PG-CI",
                "quantity": 100,
                "unit_sales_price_kopeks": 100000,
                "unit_est_cost_kopeks": 60000,
                "delivery_date": "2026-11-12",
                "approved_source_id": "synthetic-postgres-ci",
            },
        )
        assert created.status_code == 201, created.text
        order = created.json()
        order_id = order["id"]
        assert (order["revision"], order["quantity"]) == (1, 100)

        forbidden_review = api.post(
            f"/api/v1/orders/{order_id}/production-reviews",
            headers=headers["sales"],
            json={
                "production_status": "NOT_STARTED",
                "completed_quantity": 0,
                "feasibility": "CONFIRMED",
                "note": "Not authorized",
            },
        )
        assert forbidden_review.status_code == 403, forbidden_review.text

        review = api.post(
            f"/api/v1/orders/{order_id}/production-reviews",
            headers=headers["production"],
            json={
                "production_status": "NOT_STARTED",
                "completed_quantity": 0,
                "feasibility": "CONFIRMED",
                "note": "Synthetic capacity approved",
            },
        )
        assert review.status_code == 201, review.text

        change = api.post(
            f"/api/v1/orders/{order_id}/changes",
            headers=headers["sales"],
            json={"reason": "Synthetic customer requests 120", "requested_quantity": 120},
        )
        assert change.status_code == 201, change.text
        change_id = change.json()["id"]

        # A second proposal from V1 must not be promoted after a competing V2.
        stale = api.post(
            f"/api/v1/orders/{order_id}/changes",
            headers=headers["sales"],
            json={"reason": "Competing 130 proposal", "requested_quantity": 130},
        )
        assert stale.status_code == 201, stale.text
        stale_id = stale.json()["id"]

        assessment = api.post(f"/api/v1/changes/{change_id}/assess", headers=headers["sales"])
        assert assessment.status_code == 200, assessment.text
        fingerprint = assessment.json()["fingerprint"]
        assert assessment.json()["readiness"] == "READY_FOR_APPROVAL"
        assert assessment.json()["delta_revenue_kopeks"] == 2_000_000
        submitted = api.post(f"/api/v1/changes/{change_id}/submit", headers=headers["sales"])
        assert submitted.status_code == 200, submitted.text

        forbidden_approval = api.post(
            f"/api/v1/changes/{change_id}/decision",
            headers=headers["sales"],
            json={
                "action": "APPROVE",
                "assessment_fingerprint": fingerprint,
                "note": "Sales may not approve",
            },
        )
        assert forbidden_approval.status_code == 403, forbidden_approval.text

        approved = api.post(
            f"/api/v1/changes/{change_id}/decision",
            headers=headers["approver"],
            json={
                "action": "APPROVE",
                "assessment_fingerprint": fingerprint,
                "note": "Synthetic internal approval",
            },
        )
        assert approved.status_code == 200, approved.text

        premature_apply = api.post(
            f"/api/v1/changes/{change_id}/apply", headers=headers["approver"]
        )
        assert premature_apply.status_code == 409, premature_apply.text

        wrong_terms = {
            "quantity": 121,
            "unit_sales_price_kopeks": 100000,
            "delivery_date": "2026-11-12",
            "source_name": "synthetic-confirmation",
            "evidence_text": "Synthetic customer approval for 120",
        }
        incorrect = api.post(
            f"/api/v1/changes/{change_id}/customer-acceptance",
            headers=headers["sales"],
            json=wrong_terms,
        )
        assert incorrect.status_code == 409, incorrect.text

        accepted = api.post(
            f"/api/v1/changes/{change_id}/customer-acceptance",
            headers=headers["sales"],
            json={**wrong_terms, "quantity": 120},
        )
        assert accepted.status_code == 201, accepted.text

        forbidden_apply = api.post(
            f"/api/v1/changes/{change_id}/apply", headers=headers["sales"]
        )
        assert forbidden_apply.status_code == 403, forbidden_apply.text

        applied = api.post(
            f"/api/v1/changes/{change_id}/apply", headers=headers["approver"]
        )
        assert applied.status_code == 201, applied.text
        assert applied.json()["approved_revision"] == 2

        replay = api.post(
            f"/api/v1/changes/{change_id}/apply", headers=headers["approver"]
        )
        assert replay.status_code == 409, replay.text

        stale_reassessment = api.post(
            f"/api/v1/changes/{stale_id}/assess", headers=headers["sales"]
        )
        assert stale_reassessment.status_code == 409, stale_reassessment.text

    # Recreate engine, session factory and HTTP client: proof that data lives in PG.
    with TestClient(create_app(url)) as reopened:
        current = reopened.get(f"/api/v1/orders/{order_id}", headers=headers["sales"])
        assert current.status_code == 200, current.text
        assert (current.json()["revision"], current.json()["quantity"]) == (2, 120)
        history = reopened.get(
            f"/api/v1/orders/{order_id}/revisions", headers=headers["sales"]
        )
        assert history.status_code == 200, history.text
        revisions = history.json()
        assert [(r["revision_number"], r["quantity"]) for r in revisions] == [
            (1, 100),
            (2, 120),
        ]
        assert revisions[0]["approved_change_id"] is None
        assert revisions[1]["approved_change_id"] == change_id
        assert revisions[1]["approved_source_id"] == accepted.json()["id"]
        assert revisions[0]["quantity"] == 100

        saved_change = reopened.get(
            f"/api/v1/changes/{change_id}", headers=headers["sales"]
        )
        assert saved_change.status_code == 200, saved_change.text
        assert saved_change.json()["status"] == "APPLIED"
