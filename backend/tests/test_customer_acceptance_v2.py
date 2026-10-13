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


def test_parallel_apply_same_order_has_one_winner(client, headers, make_order):
    """Two genuine concurrent HTTP apply calls may not both create V2."""
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    order, first_id = prepare(client, headers, make_order)
    assert acceptance(client, headers, first_id).status_code == 201

    # A second proposal receives the same V1 baseline and approval.
    change = client.post(f"/api/v1/orders/{order['id']}/changes", headers=headers["sales"],
                         json={"reason": "Second manager requests 130", "requested_quantity": 130})
    assert change.status_code == 201
    second_id = change.json()["id"]
    assessment = client.post(f"/api/v1/changes/{second_id}/assess", headers=headers["sales"])
    assert assessment.status_code == 200
    assert client.post(f"/api/v1/changes/{second_id}/submit", headers=headers["sales"]).status_code == 200
    assert client.post(f"/api/v1/changes/{second_id}/decision", headers=headers["approver"],
                       json={"action": "APPROVE",
                             "assessment_fingerprint": assessment.json()["fingerprint"],
                             "note": "Approved second proposal"}).status_code == 200
    accepted = client.post(f"/api/v1/changes/{second_id}/customer-acceptance",
                           headers=headers["sales"],
                           json={"quantity": 130, "unit_sales_price_kopeks": 100000,
                                 "delivery_date": "2026-11-12",
                                 "source_name": "customer-130", "evidence_text": "Confirmed 130"})
    assert accepted.status_code == 201, accepted.text

    barrier = Barrier(2)
    def apply_once(change_id):
        barrier.wait(timeout=5)
        return client.post(f"/api/v1/changes/{change_id}/apply", headers=headers["approver"])

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(apply_once, first_id)
        second = pool.submit(apply_once, second_id)
        results = [first.result(timeout=15), second.result(timeout=15)]

    assert sorted(r.status_code for r in results) == [201, 409], [r.text for r in results]
    history = client.get(f"/api/v1/orders/{order['id']}/revisions",
                         headers=headers["sales"]).json()
    assert len(history) == 2
    assert [revision["revision_number"] for revision in history] == [1, 2]
    current = client.get(f"/api/v1/orders/{order['id']}", headers=headers["sales"]).json()
    assert current["revision"] == 2
    assert current["quantity"] == history[1]["quantity"]


def test_internal_cost_change_is_preserved_in_approved_revision(client, headers, make_order):
    """Internal estimated cost is part of the fingerprint of the approved change."""
    order = make_order(unit_est_cost_kopeks=60000)
    review = client.post(f"/api/v1/orders/{order['id']}/production-reviews",
                         headers=headers["production"],
                         json={"production_status": "NOT_STARTED", "completed_quantity": 0,
                               "feasibility": "CONFIRMED", "note": "Confirmed"})
    assert review.status_code == 201
    change = client.post(f"/api/v1/orders/{order['id']}/changes", headers=headers["sales"],
                         json={"reason": "Quantity plus revised internal cost",
                               "requested_quantity": 120, "requested_unit_est_cost_kopeks": 65000,
                               "one_time_change_cost_kopeks": 0})
    assert change.status_code == 201
    change_id = change.json()["id"]
    assessment = client.post(f"/api/v1/changes/{change_id}/assess", headers=headers["sales"])
    assert assessment.status_code == 200
    assert assessment.json()["delta_est_cost_kopeks"] == 120 * 65000 - 100 * 60000
    assert client.post(f"/api/v1/changes/{change_id}/submit", headers=headers["sales"]).status_code == 200
    assert client.post(f"/api/v1/changes/{change_id}/decision", headers=headers["approver"],
                       json={"action": "APPROVE",
                             "assessment_fingerprint": assessment.json()["fingerprint"],
                             "note": "Cost reviewed"}).status_code == 200
    assert acceptance(client, headers, change_id).status_code == 201
    assert client.post(f"/api/v1/changes/{change_id}/apply",
                       headers=headers["approver"]).status_code == 201
    history = client.get(f"/api/v1/orders/{order['id']}/revisions",
                         headers=headers["sales"]).json()
    assert history[0]["unit_est_cost_kopeks"] == 60000
    assert history[1]["unit_est_cost_kopeks"] == 65000
