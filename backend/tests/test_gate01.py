"""Gate 01: do not promote a customer request into an approved order."""


def change_url(order):
    return f"/api/v1/orders/{order['id']}/changes"


def review_url(order):
    return f"/api/v1/orders/{order['id']}/production-reviews"


def test_a_original_order_immutable_during_change(client, headers, make_order):
    original = make_order()
    response = client.post(change_url(original), headers=headers["sales"],
                           json={"reason": "Client requested more units", "requested_quantity": 120})
    assert response.status_code == 201
    proposal = response.json()
    assert proposal["status"] == "DRAFT"
    assert proposal["requested_quantity"] == 120
    current = client.get(f"/api/v1/orders/{original['id']}", headers=headers["sales"]).json()
    assert current == original
    assert current["quantity"] == 100
    assert current["revision"] == 1
    assert current["production_status"] == "NOT_STARTED"


def test_b_calculation_and_unknown_production_risk(client, headers, make_order):
    order = make_order(unit_est_cost_kopeks=65000)
    review = client.post(review_url(order), headers=headers["production"], json={
        "production_status": "IN_PRODUCTION", "completed_quantity": 80,
        "feasibility": "UNKNOWN", "note": "Need capacity check"})
    assert review.status_code == 201
    change = client.post(change_url(order), headers=headers["sales"], json={
        "reason": "Increase to 120, reprice", "requested_quantity": 120,
        "requested_unit_sales_price_kopeks": 110000,
        "requested_unit_est_cost_kopeks": 70000,
        "one_time_change_cost_kopeks": 0}).json()
    response = client.post(f"/api/v1/changes/{change['id']}/assess", headers=headers["sales"])
    assert response.status_code == 200
    impact = response.json()
    assert impact["readiness"] == "NEEDS_DATA"
    assert "PRODUCTION_FEASIBILITY_MISSING" in impact["issues"]
    assert impact["old_revenue_kopeks"] == 10_000_000
    assert impact["new_revenue_kopeks"] == 13_200_000
    assert impact["delta_revenue_kopeks"] == 3_200_000
    assert impact["delta_est_cost_kopeks"] == 1_900_000
    assert impact["delta_est_contribution_kopeks"] == 1_300_000
    blocked = client.post(f"/api/v1/changes/{change['id']}/submit", headers=headers["sales"])
    assert blocked.status_code == 409
    current = client.get(f"/api/v1/orders/{order['id']}", headers=headers["sales"]).json()
    assert (current["quantity"], current["completed_quantity"], current["production_status"]) == (100, 80, "IN_PRODUCTION")


def test_c_sales_cannot_act_as_authorized_approver(client, headers, make_order):
    order = make_order()
    review = client.post(review_url(order), headers=headers["production"], json={
        "production_status": "NOT_STARTED", "completed_quantity": 0,
        "feasibility": "CONFIRMED", "note": "Capacity available"})
    assert review.status_code == 201
    change = client.post(change_url(order), headers=headers["sales"], json={
        "reason": "Increase", "requested_quantity": 120}).json()
    impact = client.post(f"/api/v1/changes/{change['id']}/assess", headers=headers["sales"]).json()
    assert impact["readiness"] == "READY_FOR_APPROVAL"
    submitted = client.post(f"/api/v1/changes/{change['id']}/submit", headers=headers["sales"])
    assert submitted.status_code == 200
    attempt = client.post(f"/api/v1/changes/{change['id']}/decision", headers=headers["sales"], json={
        "action": "APPROVE", "assessment_fingerprint": impact["fingerprint"], "note": "I approve myself"})
    assert attempt.status_code == 403
    assert client.get(f"/api/v1/changes/{change['id']}", headers=headers["sales"]).json()["status"] == "PENDING_APPROVAL"


def test_valid_company_approver_can_approve_but_original_order_remains(client, headers, make_order):
    order = make_order()
    client.post(review_url(order), headers=headers["production"], json={
        "production_status": "NOT_STARTED", "completed_quantity": 0,
        "feasibility": "CONFIRMED", "note": "Feasible"})
    change = client.post(change_url(order), headers=headers["sales"], json={
        "reason": "Increase", "requested_quantity": 120}).json()
    assessment = client.post(f"/api/v1/changes/{change['id']}/assess", headers=headers["sales"]).json()
    assert assessment["readiness"] == "READY_FOR_APPROVAL"
    assert client.post(f"/api/v1/changes/{change['id']}/submit", headers=headers["sales"]).status_code == 200
    response = client.post(f"/api/v1/changes/{change['id']}/decision", headers=headers["approver"], json={
        "action": "APPROVE", "assessment_fingerprint": assessment["fingerprint"], "note": "Conditions verified"})
    assert response.status_code == 200, response.text
    assert response.json()["reviewer_id"] == "approver-demo"
    assert client.get(f"/api/v1/changes/{change['id']}", headers=headers["sales"]).json()["status"] == "INTERNALLY_APPROVED"
    assert client.get(f"/api/v1/orders/{order['id']}", headers=headers["sales"]).json() == order


def test_stale_production_review_prevents_approval(client, headers, make_order):
    order = make_order()
    client.post(review_url(order), headers=headers["production"], json={
        "production_status": "NOT_STARTED", "completed_quantity": 0,
        "feasibility": "CONFIRMED", "note": "OK"})
    change = client.post(change_url(order), headers=headers["sales"], json={
        "reason": "Increase", "requested_quantity": 120}).json()
    assessment = client.post(f"/api/v1/changes/{change['id']}/assess", headers=headers["sales"]).json()
    assert client.post(f"/api/v1/changes/{change['id']}/submit", headers=headers["sales"]).status_code == 200
    client.post(review_url(order), headers=headers["production"], json={
        "production_status": "IN_PRODUCTION", "completed_quantity": 80,
        "feasibility": "UNKNOWN", "note": "Now uncertain"})
    attempt = client.post(f"/api/v1/changes/{change['id']}/decision", headers=headers["approver"], json={
        "action": "APPROVE", "assessment_fingerprint": assessment["fingerprint"], "note": "Old assessment"})
    assert attempt.status_code == 409


def test_expediting_without_rush_cost_does_not_guess(client, headers, make_order):
    order = make_order()
    client.post(review_url(order), headers=headers["production"], json={
        "production_status": "NOT_STARTED", "completed_quantity": 0,
        "feasibility": "UNKNOWN", "note": "No confirmation on deadline"})
    change = client.post(change_url(order), headers=headers["sales"], json={
        "reason": "Expedite", "requested_delivery_date": "2026-11-08"}).json()
    assessment = client.post(f"/api/v1/changes/{change['id']}/assess", headers=headers["sales"]).json()
    assert assessment["readiness"] == "NEEDS_DATA"
    assert {"PRODUCTION_FEASIBILITY_MISSING", "RUSH_COST_MISSING"}.issubset(assessment["issues"])
    assert assessment["delta_est_contribution_kopeks"] is None
    assert assessment["can_promise_date"] is False


def test_incomplete_change_and_invalid_review_rejected(client, headers, make_order):
    order = make_order()
    assert client.post(change_url(order), headers=headers["sales"], json={"reason": "No changes"}).status_code == 422
    assert client.post(review_url(order), headers=headers["production"], json={
        "production_status": "NOT_STARTED", "completed_quantity": 80,
        "feasibility": "CONFIRMED", "note": "Invalid"}).status_code == 422


def test_missing_or_forged_token_is_never_approval_authority(client, headers, make_order):
    order = make_order()
    assert client.get(f"/api/v1/orders/{order['id']}").status_code == 401
    assert client.post(review_url(order), headers=headers["sales"], json={
        "production_status": "NOT_STARTED", "completed_quantity": 0,
        "feasibility": "CONFIRMED", "note": "Forged"}).status_code == 403


def test_new_production_review_revokes_pending_internal_approval(client, headers, make_order):
    order = make_order()
    client.post(review_url(order), headers=headers["production"], json={
        "production_status": "NOT_STARTED", "completed_quantity": 0,
        "feasibility": "CONFIRMED", "note": "Ready"})
    change = client.post(change_url(order), headers=headers["sales"], json={
        "reason": "Increase", "requested_quantity": 120}).json()
    impact = client.post(f"/api/v1/changes/{change['id']}/assess", headers=headers["sales"]).json()
    assert client.post(f"/api/v1/changes/{change['id']}/submit", headers=headers["sales"]).status_code == 200
    assert client.post(f"/api/v1/changes/{change['id']}/decision", headers=headers["approver"], json={
        "action": "APPROVE", "assessment_fingerprint": impact["fingerprint"], "note": "Approved"}).status_code == 200
    changed = client.post(review_url(order), headers=headers["production"], json={
        "production_status": "IN_PRODUCTION", "completed_quantity": 10,
        "feasibility": "UNKNOWN", "note": "Production started"})
    assert changed.status_code == 201
    assert client.get(f"/api/v1/changes/{change['id']}", headers=headers["sales"]).json()["status"] == "ASSESSMENT_REQUIRED"
    assert client.post(f"/api/v1/changes/{change['id']}/submit", headers=headers["sales"]).status_code == 409


def test_production_progress_cannot_move_backward(client, headers, make_order):
    order = make_order()
    assert client.post(review_url(order), headers=headers["production"], json={
        "production_status": "IN_PRODUCTION", "completed_quantity": 80,
        "feasibility": "CONFIRMED", "note": "On track"}).status_code == 201
    regression = client.post(review_url(order), headers=headers["production"], json={
        "production_status": "NOT_STARTED", "completed_quantity": 0,
        "feasibility": "CONFIRMED", "note": "Reset attempt"})
    assert regression.status_code == 409


def test_api_exposes_bearer_auth_scheme(client):
    spec = client.get("/openapi.json").json()
    assert any(v.get("scheme") == "bearer" for v in spec["components"]["securitySchemes"].values())
    assert "/api/v1/changes/{change_id}/decision" in spec["paths"]
