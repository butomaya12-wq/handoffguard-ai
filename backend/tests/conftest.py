import json

import pytest
from fastapi.testclient import TestClient

from app.main import create_app


TOKENS = {
    "test-sales-token": {"id": "sales-demo", "role": "sales"},
    "test-production-token": {"id": "production-demo", "role": "production"},
    "test-approver-token": {"id": "approver-demo", "role": "approver"},
}


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("HANDOFFGUARD_AUTH_TOKENS", json.dumps(TOKENS))
    with TestClient(create_app(f"sqlite:///{tmp_path / 'test.db'}")) as api:
        yield api


@pytest.fixture
def headers():
    return {role: {"Authorization": f"Bearer test-{role}-token"} for role in ("sales", "production", "approver")}


@pytest.fixture
def make_order(client, headers):
    def create(**overrides):
        payload = {"product_code": "FRAME-01", "quantity": 100, "unit_sales_price_kopeks": 100000,
                   "delivery_date": "2026-11-12", "approved_source_id": "order-100-approved"}
        payload.update(overrides)
        response = client.post("/api/v1/orders", headers=headers["sales"], json=payload)
        assert response.status_code == 201, response.text
        return response.json()
    return create
