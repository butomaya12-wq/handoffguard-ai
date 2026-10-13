"""Lesson: an approved baseline creates history, proposals/rejections do not."""


def revisions(client, headers, order):
    response = client.get(f"/api/v1/orders/{order['id']}/revisions", headers=headers["sales"])
    assert response.status_code == 200, response.text
    return response.json()


def test_new_order_creates_exactly_one_approved_v1(client, headers, make_order):
    order = make_order(quantity=100, unit_sales_price_kopeks=100000)
    history = revisions(client, headers, order)
    assert len(history) == 1
    first = history[0]
    assert first["order_id"] == order["id"]
    assert first["revision_number"] == 1
    assert first["quantity"] == 100
    assert first["unit_sales_price_kopeks"] == 100000
    assert first["delivery_date"] == "2026-11-12"
    assert first["approved_source_id"] == "order-100-approved"
    assert first["approved_change_id"] is None
    assert order["revision"] == 1


def test_proposal_does_not_create_approved_revision(client, headers, make_order):
    order = make_order()
    response = client.post(f"/api/v1/orders/{order['id']}/changes", headers=headers["sales"],
                           json={"reason": "Please produce 120", "requested_quantity": 120})
    assert response.status_code == 201
    assert [v["revision_number"] for v in revisions(client, headers, order)] == [1]
    assert [v["quantity"] for v in revisions(client, headers, order)] == [100]


def test_rejected_change_stays_in_history_without_new_revision(client, headers, make_order):
    order = make_order()
    assert client.post(f"/api/v1/orders/{order['id']}/production-reviews", headers=headers["production"],
                       json={"production_status": "NOT_STARTED", "completed_quantity": 0,
                             "feasibility": "CONFIRMED", "note": "Can produce"}).status_code == 201
    change_response = client.post(f"/api/v1/orders/{order['id']}/changes", headers=headers["sales"],
                                  json={"reason": "Client asks for 130", "requested_quantity": 130})
    assert change_response.status_code == 201
    change_id = change_response.json()["id"]
    impact = client.post(f"/api/v1/changes/{change_id}/assess", headers=headers["sales"]).json()
    assert impact["readiness"] == "READY_FOR_APPROVAL"
    assert client.post(f"/api/v1/changes/{change_id}/submit", headers=headers["sales"]).status_code == 200
    decision = client.post(f"/api/v1/changes/{change_id}/decision", headers=headers["approver"],
                           json={"action": "REJECT", "assessment_fingerprint": impact["fingerprint"],
                                 "note": "Cannot meet customer timeline"})
    assert decision.status_code == 200, decision.text
    change = client.get(f"/api/v1/changes/{change_id}", headers=headers["sales"]).json()
    assert change["status"] == "REJECTED"
    assert change["requested_quantity"] == 130
    assert [v["quantity"] for v in revisions(client, headers, order)] == [100]


def test_unknown_order_history_returns_404(client, headers):
    response = client.get("/api/v1/orders/no-such-order/revisions", headers=headers["sales"])
    assert response.status_code == 404
