"""Integration-style API tests for customer terms and approved V2."""


def prepare(client, headers, make_order, quantity=120):
    order = make_order()
    review = client.post(f"/api/v1/orders/{order['id']}/production-reviews",
                         headers=headers["production"],
                         json={"production_status": "NOT_STARTED", "completed_quantity": 0,
                               "feasibility": "CONFIRMED", "note": "Capacity confirmed"})
    assert review.status_code == 201, review.text
    change = client.post(f"/api/v1/orders/{order['id']}/changes", headers=headers["sales"],
                         json={"reason": "Customer requested larger order",
                               "requested_quantity": quantity})
    assert change.status_code == 201, change.text
    change_id = change.json()["id"]
    assessment = client.post(f"/api/v1/changes/{change_id}/assess",
                             headers=headers["sales"])
    assert assessment.status_code == 200, assessment.text
    assert assessment.json()["readiness"] == "READY_FOR_APPROVAL"
    submit = client.post(f"/api/v1/changes/{change_id}/submit", headers=headers["sales"])
    assert submit.status_code == 200, submit.text
    approved = client.post(f"/api/v1/changes/{change_id}/decision",
                           headers=headers["approver"],
                           json={"action": "APPROVE", "assessment_fingerprint": assessment.json()["fingerprint"],
                                 "note": "Approved commercial terms"})
    assert approved.status_code == 200, approved.text
    return order, change_id


def acceptance(client, headers, change_id, price=100000):
    return client.post(f"/api/v1/changes/{change_id}/customer-acceptance",
                       headers=headers["sales"],
                       json={"quantity": 120, "unit_sales_price_kopeks": price,
                             "delivery_date": "2026-11-12",
                             "source_name": "customer-confirmation-demo",
                             "evidence_text": "Customer confirmed quantity, unit price and date"})


def test_acceptance_and_atomic_apply_v2(client, headers, make_order):
    order, change_id = prepare(client, headers, make_order)
    assert acceptance(client, headers, change_id).status_code == 201
    applied = client.post(f"/api/v1/changes/{change_id}/apply", headers=headers["approver"])
    assert applied.status_code == 201, applied.text
    assert applied.json()["approved_revision"] == 2
    current = client.get(f"/api/v1/orders/{order['id']}", headers=headers["sales"]).json()
    assert (current["revision"], current["quantity"]) == (2, 120)
    history = client.get(f"/api/v1/orders/{order['id']}/revisions", headers=headers["sales"]).json()
    assert [(r["revision_number"], r["quantity"]) for r in history] == [(1, 100), (2, 120)]
    assert history[1]["approved_change_id"] == change_id
    assert history[0]["quantity"] == 100


def test_price_mismatch_blocks_customer_acceptance(client, headers, make_order):
    order, change_id = prepare(client, headers, make_order)
    assert acceptance(client, headers, change_id, price=90000).status_code == 409
    assert client.post(f"/api/v1/changes/{change_id}/apply", headers=headers["approver"]).status_code == 409
    assert client.get(f"/api/v1/orders/{order['id']}", headers=headers["sales"]).json()["quantity"] == 100


def test_apply_requires_acceptance_and_repeated_apply_is_blocked(client, headers, make_order):
    order, change_id = prepare(client, headers, make_order)
    assert client.post(f"/api/v1/changes/{change_id}/apply", headers=headers["approver"]).status_code == 409
    assert acceptance(client, headers, change_id).status_code == 201
    assert acceptance(client, headers, change_id).status_code == 409
    assert client.post(f"/api/v1/changes/{change_id}/apply", headers=headers["approver"]).status_code == 201
    assert client.post(f"/api/v1/changes/{change_id}/apply", headers=headers["approver"]).status_code == 409


def test_concurrent_proposals_cannot_apply_stale_version(client, headers, make_order):
    order, first_id = prepare(client, headers, make_order)
    second = client.post(f"/api/v1/orders/{order['id']}/changes", headers=headers["sales"],
                         json={"reason": "Other manager wants 130", "requested_quantity": 130})
    assert second.status_code == 201
    assert acceptance(client, headers, first_id).status_code == 201
    assert client.post(f"/api/v1/changes/{first_id}/apply", headers=headers["approver"]).status_code == 201
    # The stale request remains recorded, but cannot pass its former assessment.
    second_assess = client.post(f"/api/v1/changes/{second.json()['id']}/assess", headers=headers["sales"])
    assert second_assess.status_code == 409


def test_only_authorized_roles_can_accept_or_apply(client, headers, make_order):
    order, change_id = prepare(client, headers, make_order)
    assert client.post(f"/api/v1/changes/{change_id}/apply", headers=headers["sales"]).status_code == 403
    r = client.post(f"/api/v1/changes/{change_id}/customer-acceptance",
                    headers=headers["production"], json={
                        "quantity": 120, "unit_sales_price_kopeks": 100000,
                        "delivery_date": "2026-11-12", "source_name": "evidence",
                        "evidence_text": "Confirmed"})
    assert r.status_code == 403
