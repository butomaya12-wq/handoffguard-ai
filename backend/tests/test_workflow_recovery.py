"""Browser workflow recovery is read-only and role restricted."""


def test_recover_approved_change_after_reload(client, headers, make_order):
    from test_customer_acceptance_v2 import prepare, acceptance

    order, change_id = prepare(client, headers, make_order)
    url = f"/api/v1/orders/{order['id']}/changes"
    read = client.get(url, headers=headers["sales"])
    assert read.status_code == 200, read.text
    workflows = read.json()
    assert len(workflows) == 1
    before = workflows[0]
    assert before["id"] == change_id
    assert before["status"] == "INTERNALLY_APPROVED"
    assert before["requested_quantity"] == 120
    assert before["assessment"]["readiness"] == "READY_FOR_APPROVAL"
    assert len(before["assessment"]["fingerprint"]) == 64
    assert before["customer_accepted"] is False

    assert acceptance(client, headers, change_id).status_code == 201
    after = client.get(url, headers=headers["sales"])
    assert after.status_code == 200
    assert after.json()[0]["customer_accepted"] is True
    assert client.get(url, headers=headers["approver"]).status_code == 200
    assert client.get(url, headers=headers["production"]).status_code == 403
    assert client.get(url).status_code == 401
    assert client.get("/api/v1/orders/no-such-order/changes", headers=headers["sales"]).status_code == 404

    unchanged_order = client.get(f"/api/v1/orders/{order['id']}", headers=headers["sales"]).json()
    unchanged_history = client.get(f"/api/v1/orders/{order['id']}/revisions", headers=headers["sales"]).json()
    assert unchanged_order["revision"] == 1
    assert len(unchanged_history) == 1

    applied = client.post(f"/api/v1/changes/{change_id}/apply", headers=headers["approver"])
    assert applied.status_code == 201, applied.text
    persisted = client.get(url, headers=headers["sales"]).json()[0]
    assert persisted["status"] == "APPLIED"
    assert persisted["customer_accepted"] is True
