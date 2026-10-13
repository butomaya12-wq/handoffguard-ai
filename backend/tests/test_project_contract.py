"""API contract consistency, legacy database behavior and concurrency regression checks."""
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient

from app.main import create_app


def test_documented_implemented_operations_match_fastapi():
    """Draft may contain planned routes, but all implemented paths and methods must match."""
    contract = yaml.safe_load((Path(__file__).resolve().parents[2] / "openapi.yaml").read_text())
    with TestClient(create_app("sqlite://")) as api:
        generated = api.app.openapi()
    for path, methods in generated["paths"].items():
        assert path in contract["paths"], f"Missing documented path: {path}"
        for method, details in methods.items():
            if method.lower() not in {"get", "post", "put", "patch", "delete"}:
                continue
            assert method in contract["paths"][path], f"Missing {method} {path}"
            documented = contract["paths"][path][method]
            assert documented["operationId"] == details["operationId"]


def test_existing_gate01_database_does_not_get_silent_fake_v1(tmp_path):
    """Metadata.create_all cannot recover historically approved snapshots."""
    from sqlalchemy import create_engine, text
    from app.models import Base, Order, ProductionReview, Change, ApprovalDecision
    db_file = tmp_path / "old.db"
    url = f"sqlite:///{db_file}"
    engine = create_engine(url)
    # The legacy schema contained these four tables, but no order_revisions.
    Base.metadata.create_all(engine, tables=[
        Order.__table__, ProductionReview.__table__, Change.__table__, ApprovalDecision.__table__
    ])
    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO orders
            (id, product_code, quantity, unit_sales_price_kopeks, delivery_date,
             approved_source_id, revision, production_status, completed_quantity)
            VALUES ('old-1', 'FRAME', 100, 100000, '2026-11-12',
                    'legacy-source', 1, 'NOT_STARTED', 0)
        """))
    engine.dispose()
    # Refuse to serve incomplete history: only an explicit audited migration may fix this.
    with pytest.raises(RuntimeError, match="lack approved V1 snapshots"):
        with TestClient(create_app(url)):
            pass


@pytest.mark.parametrize("_attempt", range(5))
def test_repeat_concurrency_regression(_attempt, client, headers, make_order):
    """Repeated race reproduction; detects regressions, not a full stress benchmark."""
    from test_customer_acceptance_v2 import test_parallel_apply_same_order_has_one_winner
    test_parallel_apply_same_order_has_one_winner(client, headers, make_order)
