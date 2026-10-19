"""HandoffGuard API — Gate 01: create, propose, assess and enforce role boundaries."""
import json
import os
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import create_engine, select, update
from sqlalchemy.orm import Session, sessionmaker

from .logic import impact_assessment
from .observability import observe_business_operation
from .alerting import AlertMonitor
from .dashboard import Status as DashboardStatus, build_dashboard
from .order_inbox import list_order_inbox
from .models import Base, Order, OrderRevision, ProductionReview, Change, ApprovalDecision, CustomerAcceptance
from .schemas import CreateOrder, ProductionReviewInput, ChangeInput, DecisionInput, CustomerAcceptanceInput


def create_app(database_url: str | None = None) -> FastAPI:
    database_url = database_url or os.getenv("HANDOFFGUARD_DATABASE_URL", "sqlite:///./handoffguard.db")
    engine = create_engine(database_url, connect_args={"check_same_thread": False} if database_url.startswith("sqlite") else {}, pool_pre_ping=True)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        Base.metadata.create_all(engine)
        # Fail closed on pre-V1 databases: create_all cannot reconstruct approved history.
        with session_factory() as migration_check:
            missing = migration_check.scalars(select(Order.id).outerjoin(
                OrderRevision, (OrderRevision.order_id == Order.id) & (OrderRevision.revision_number == 1)
            ).where(OrderRevision.id.is_(None)).limit(1)).first()
            if missing is not None:
                raise RuntimeError("Existing orders lack approved V1 snapshots. Back up and migrate the database before starting; never fabricate historical approval records.")
        # Inert unless explicitly opted in on the gated cloud entrypoint.
        # No public diagnostic route and no synthetic business failure.
        if (
            getattr(app.state, "cloud_mode", False)
            and os.getenv("HANDOFFGUARD_ALERT_DIAGNOSTIC_ON_START") == "SEND_ON_NEXT_START"
        ):
            await app.state.alert_monitor.send_diagnostic()
        yield
        engine.dispose()

    app = FastAPI(title="HandoffGuard AI API", version="0.3.0-gate01", lifespan=lifespan)
    # Per-app, best-effort threshold state. Never a durable production pager.
    app.state.alert_monitor = AlertMonitor.from_environment()
    # Safe JSON events for authenticated business operations; no user payloads.
    app.middleware("http")(observe_business_operation)

    def get_db():
        with session_factory() as session:
            yield session

    bearer = HTTPBearer(auto_error=False)

    def current_actor(credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]) -> dict:
        if credentials is None or credentials.scheme.lower() != "bearer":
            raise HTTPException(status_code=401, detail="Bearer token required")
        # Tokens mapped to trusted identities/roles on the SERVER. No role in request body.
        try:
            configured = json.loads(os.getenv("HANDOFFGUARD_AUTH_TOKENS", "{}"))
        except json.JSONDecodeError:
            raise HTTPException(status_code=503, detail="Authentication server misconfigured")
        record = configured.get(credentials.credentials)
        if not isinstance(record, dict) or record.get("role") not in {"sales", "production", "approver"} or not record.get("id"):
            raise HTTPException(status_code=401, detail="Invalid token")
        return record

    def require_role(*allowed: str):
        def check(actor: Annotated[dict, Depends(current_actor)]):
            if actor["role"] not in allowed:
                raise HTTPException(status_code=403, detail="Insufficient role")
            return actor
        return check

    def fetch_order(db: Session, order_id: str) -> Order:
        order = db.get(Order, order_id)
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")
        return order

    def fetch_change(db: Session, change_id: str) -> Change:
        change = db.get(Change, change_id)
        if not change:
            raise HTTPException(status_code=404, detail="Change not found")
        return change

    def serialize_order(order: Order) -> dict:
        return {key: getattr(order, key) for key in (
            "id", "product_code", "quantity", "unit_sales_price_kopeks", "unit_est_cost_kopeks",
            "delivery_date", "approved_source_id", "revision", "production_status", "completed_quantity")}

    def serialize_change(change: Change) -> dict:
        return {key: getattr(change, key) for key in (
            "id", "order_id", "baseline_revision", "reason", "requested_quantity",
            "requested_unit_sales_price_kopeks", "requested_unit_est_cost_kopeks",
            "requested_delivery_date", "one_time_change_cost_kopeks", "status")}

    def latest_review(db: Session, order_id: str):
        return db.scalars(select(ProductionReview).where(ProductionReview.order_id == order_id)
                          .order_by(ProductionReview.recorded_at.desc(), ProductionReview.id.desc())).first()

    @app.get("/api/v1/me", operation_id="getCurrentSession")
    def get_current_session(actor: Annotated[dict, Depends(current_actor)]):
        """Return only the validated role, never tokens or actor identifiers."""
        return {"role": actor["role"]}

    @app.get("/api/v1/analytics/changes", operation_id="listChangeAnalytics")
    def list_change_analytics(
        db: Annotated[Session, Depends(get_db)],
        actor: Annotated[dict, Depends(require_role("sales", "approver"))],
        status: DashboardStatus | None = None,
    ):
        """Read-only totals and bounded synthetic-demo rows; no free-text or PII."""
        return build_dashboard(db, status=status)

    @app.get("/api/v1/orders/inbox", operation_id="listOrderInbox")
    def get_order_inbox(
        db: Annotated[Session, Depends(get_db)],
        actor: Annotated[dict, Depends(current_actor)],
        limit: Annotated[int, Query(ge=1, le=100)] = 25,
        offset: Annotated[int, Query(ge=0)] = 0,
    ):
        """Live queue: current revision requires a recorded production review."""
        return list_order_inbox(db, limit=limit, offset=offset)

    @app.post("/api/v1/orders", status_code=201, operation_id="createOrder")
    def create_order(payload: CreateOrder, db: Annotated[Session, Depends(get_db)], actor: Annotated[dict, Depends(require_role("sales"))]):
        order = Order(**payload.model_dump())
        db.add(order)
        db.flush()  # Allocates order.id; does NOT commit the transaction yet.
        db.add(OrderRevision(
            order_id=order.id,
            revision_number=1,
            product_code=order.product_code,
            quantity=order.quantity,
            unit_sales_price_kopeks=order.unit_sales_price_kopeks,
            unit_est_cost_kopeks=order.unit_est_cost_kopeks,
            delivery_date=order.delivery_date,
            approved_source_id=order.approved_source_id,
        ))
        db.commit()  # Order and V1 history are written atomically.
        db.refresh(order)
        return serialize_order(order)

    @app.get("/api/v1/orders/{order_id}", operation_id="getOrder")
    def get_order(order_id: str, db: Annotated[Session, Depends(get_db)], actor: Annotated[dict, Depends(current_actor)]):
        return serialize_order(fetch_order(db, order_id))


    @app.get("/api/v1/orders/{order_id}/revisions", operation_id="listOrderRevisions")
    def list_order_revisions(order_id: str, db: Annotated[Session, Depends(get_db)], actor: Annotated[dict, Depends(current_actor)]):
        fetch_order(db, order_id)
        revisions = db.scalars(
            select(OrderRevision).where(OrderRevision.order_id == order_id)
            .order_by(OrderRevision.revision_number.asc())
        ).all()
        return [
            {"id": item.id, "order_id": item.order_id, "revision_number": item.revision_number,
             "product_code": item.product_code, "quantity": item.quantity,
             "unit_sales_price_kopeks": item.unit_sales_price_kopeks,
             "unit_est_cost_kopeks": item.unit_est_cost_kopeks,
             "delivery_date": item.delivery_date, "approved_source_id": item.approved_source_id,
             "approved_change_id": item.approved_change_id, "created_at": item.created_at}
            for item in revisions
        ]

    @app.post("/api/v1/orders/{order_id}/production-reviews", status_code=201, operation_id="recordProductionReview")
    def record_production_review(order_id: str, payload: ProductionReviewInput, db: Annotated[Session, Depends(get_db)], actor: Annotated[dict, Depends(require_role("production"))]):
        order = fetch_order(db, order_id)
        if payload.completed_quantity > order.quantity:
            raise HTTPException(status_code=422, detail="Completed quantity exceeds currently approved quantity")
        if payload.production_status == "NOT_STARTED" and payload.completed_quantity != 0:
            raise HTTPException(status_code=422, detail="NOT_STARTED cannot have produced units")
        if payload.production_status == "COMPLETED" and payload.completed_quantity != order.quantity:
            raise HTTPException(status_code=422, detail="COMPLETED requires full quantity")
        status_order = {"NOT_STARTED": 0, "IN_PRODUCTION": 1, "COMPLETED": 2}
        if (status_order[payload.production_status] < status_order[order.production_status]
                or payload.completed_quantity < order.completed_quantity):
            raise HTTPException(status_code=409, detail="Production progress cannot move backward")
        # Current production state changes only through a production review, not a sales change.
        review = ProductionReview(order_id=order.id, order_revision=order.revision, reviewer_id=actor["id"], **payload.model_dump())
        order.production_status = payload.production_status
        order.completed_quantity = payload.completed_quantity
        db.add(review)
        # A new production snapshot invalidates ALL pending/approved assessments.
        for change in db.scalars(select(Change).where(Change.order_id == order.id,
                                                     Change.status.in_(["ASSESSMENT_REQUIRED", "PENDING_APPROVAL", "INTERNALLY_APPROVED"]))):
            change.status = "ASSESSMENT_REQUIRED"
            change.latest_fingerprint = None
            change.latest_readiness = None
            change.latest_review_id = None
            change.assessment_result = None
        db.commit()
        db.refresh(review)
        return {"id": review.id, "order_id": review.order_id, "order_revision": review.order_revision,
                "reviewer_id": review.reviewer_id, "recorded_at": review.recorded_at,
                **payload.model_dump()}

    @app.get("/api/v1/orders/{order_id}/changes", operation_id="listOrderChanges")
    def list_order_changes(order_id: str, db: Annotated[Session, Depends(get_db)],
                           actor: Annotated[dict, Depends(require_role("sales", "approver"))]):
        """Read persisted workflow state after a browser reload. This endpoint never approves anything."""
        fetch_order(db, order_id)
        changes = db.scalars(select(Change).where(Change.order_id == order_id)).all()
        if not changes:
            return []
        accepted_ids = {
            item.change_id: item.assessment_fingerprint
            for item in db.scalars(select(CustomerAcceptance).where(
                CustomerAcceptance.change_id.in_([change.id for change in changes])
            )).all()
        }
        return [{
            **serialize_change(change),
            "assessment": change.assessment_result,
            "customer_accepted": (
                change.status in {"INTERNALLY_APPROVED", "APPLIED"}
                and change.latest_fingerprint is not None
                and accepted_ids.get(change.id) == change.latest_fingerprint
            )
        } for change in changes]

    @app.post("/api/v1/orders/{order_id}/changes", status_code=201, operation_id="createChange")
    def create_change(order_id: str, payload: ChangeInput, db: Annotated[Session, Depends(get_db)], actor: Annotated[dict, Depends(require_role("sales"))]):
        order = fetch_order(db, order_id)
        change = Change(order_id=order.id, baseline_revision=order.revision, **payload.model_dump())
        db.add(change)
        db.commit()
        db.refresh(change)
        return serialize_change(change)

    @app.get("/api/v1/changes/{change_id}", operation_id="getChange")
    def get_change(change_id: str, db: Annotated[Session, Depends(get_db)], actor: Annotated[dict, Depends(current_actor)]):
        return serialize_change(fetch_change(db, change_id))

    @app.post("/api/v1/changes/{change_id}/assess", operation_id="assessChange")
    def assess(change_id: str, db: Annotated[Session, Depends(get_db)], actor: Annotated[dict, Depends(require_role("sales"))]):
        change = fetch_change(db, change_id)
        order = fetch_order(db, change.order_id)
        if change.status in {"INTERNALLY_APPROVED", "REJECTED", "APPLIED"}:
            raise HTTPException(status_code=409, detail="Cannot reassess finalized change")
        if order.revision != change.baseline_revision:
            raise HTTPException(status_code=409, detail="Baseline revision is stale")
        review = latest_review(db, order.id)
        result = impact_assessment(order, change, review)
        change.latest_fingerprint = result["fingerprint"]
        change.latest_readiness = result["readiness"]
        change.latest_review_id = review.id if review else None
        change.assessment_result = result
        change.status = "ASSESSMENT_REQUIRED"
        db.commit()
        return result

    @app.post("/api/v1/changes/{change_id}/submit", operation_id="submitForApproval")
    def submit(change_id: str, db: Annotated[Session, Depends(get_db)], actor: Annotated[dict, Depends(require_role("sales"))]):
        change = fetch_change(db, change_id)
        order = fetch_order(db, change.order_id)
        review = latest_review(db, order.id)
        if (change.status != "ASSESSMENT_REQUIRED" or change.latest_readiness != "READY_FOR_APPROVAL"
                or review is None or review.id != change.latest_review_id
                or order.revision != change.baseline_revision or review.production_status == "COMPLETED"):
            raise HTTPException(status_code=409, detail="Current, feasible assessment is required")
        current = impact_assessment(order, change, review)
        if current["fingerprint"] != change.latest_fingerprint:
            raise HTTPException(status_code=409, detail="Assessment is stale")
        change.status = "PENDING_APPROVAL"
        db.commit()
        return serialize_change(change)

    @app.post("/api/v1/changes/{change_id}/decision", operation_id="decideChange")
    def decision(change_id: str, payload: DecisionInput, db: Annotated[Session, Depends(get_db)], actor: Annotated[dict, Depends(require_role("approver"))]):
        change = fetch_change(db, change_id)
        order = fetch_order(db, change.order_id)
        review = latest_review(db, order.id)
        if (change.status != "PENDING_APPROVAL" or not review or review.id != change.latest_review_id
                or order.revision != change.baseline_revision or review.production_status == "COMPLETED"):
            raise HTTPException(status_code=409, detail="Change is not in a current approval state")
        current = impact_assessment(order, change, review)
        if (current["fingerprint"] != payload.assessment_fingerprint
                or current["readiness"] != "READY_FOR_APPROVAL"):
            raise HTTPException(status_code=409, detail="Stale or unready assessment")
        record = ApprovalDecision(change_id=change.id, assessment_fingerprint=current["fingerprint"],
                                  reviewer_id=actor["id"], action=payload.action, note=payload.note)
        db.add(record)
        change.status = "INTERNALLY_APPROVED" if payload.action == "APPROVE" else "REJECTED"
        db.commit()
        db.refresh(record)
        return {"change_id": change.id, "action": record.action, "reviewer_id": record.reviewer_id,
                "assessment_fingerprint": record.assessment_fingerprint, "decided_at": record.decided_at}


    def approved_assessment(db: Session, change: Change, order: Order) -> dict:
        """Re-check approval against current order and production before recording or applying."""
        review = latest_review(db, order.id)
        if (change.status != "INTERNALLY_APPROVED"
                or change.baseline_revision != order.revision
                or review is None or review.id != change.latest_review_id
                or review.production_status == "COMPLETED"):
            raise HTTPException(status_code=409, detail="Current internal approval required")
        assessment = impact_assessment(order, change, review)
        approval = db.scalars(select(ApprovalDecision).where(
            ApprovalDecision.change_id == change.id,
            ApprovalDecision.action == "APPROVE",
            ApprovalDecision.assessment_fingerprint == assessment["fingerprint"]
        )).first()
        if (not approval or assessment["readiness"] != "READY_FOR_APPROVAL"
                or assessment["fingerprint"] != change.latest_fingerprint):
            raise HTTPException(status_code=409, detail="Approval no longer matches current terms")
        return assessment

    @app.post("/api/v1/changes/{change_id}/customer-acceptance", status_code=201, operation_id="recordCustomerAcceptance")
    def record_customer_acceptance(change_id: str, payload: CustomerAcceptanceInput,
                                   db: Annotated[Session, Depends(get_db)],
                                   actor: Annotated[dict, Depends(require_role("sales"))]):
        change = fetch_change(db, change_id)
        order = fetch_order(db, change.order_id)
        assessment = approved_assessment(db, change, order)
        expected = (
            assessment["proposed_quantity"],
            change.requested_unit_sales_price_kopeks if change.requested_unit_sales_price_kopeks is not None else order.unit_sales_price_kopeks,
            assessment["proposed_delivery_date"],
        )
        if (payload.quantity, payload.unit_sales_price_kopeks, payload.delivery_date.isoformat()) != expected:
            raise HTTPException(status_code=409, detail="Customer terms differ from internal approval")
        if db.scalars(select(CustomerAcceptance).where(CustomerAcceptance.change_id == change_id)).first():
            raise HTTPException(status_code=409, detail="Acceptance already recorded")
        acceptance = CustomerAcceptance(
            change_id=change_id, assessment_fingerprint=assessment["fingerprint"],
            recorded_by=actor["id"], **payload.model_dump()
        )
        db.add(acceptance)
        db.commit()
        db.refresh(acceptance)
        return {"id": acceptance.id, "change_id": change_id, "recorded_at": acceptance.recorded_at,
                "recorded_by": acceptance.recorded_by, "assessment_fingerprint": acceptance.assessment_fingerprint}

    @app.post("/api/v1/changes/{change_id}/apply", status_code=201, operation_id="applyApprovedChange")
    def apply_approved_change(change_id: str, db: Annotated[Session, Depends(get_db)],
                              actor: Annotated[dict, Depends(require_role("approver"))]):
        change = fetch_change(db, change_id)
        order = fetch_order(db, change.order_id)
        assessment = approved_assessment(db, change, order)
        acceptance = db.scalars(select(CustomerAcceptance).where(
            CustomerAcceptance.change_id == change_id
        )).first()
        if acceptance is None or acceptance.assessment_fingerprint != assessment["fingerprint"]:
            raise HTTPException(status_code=409, detail="Matching customer acceptance required")
        quantity = assessment["proposed_quantity"]
        price = (change.requested_unit_sales_price_kopeks if change.requested_unit_sales_price_kopeks is not None
                 else order.unit_sales_price_kopeks)
        date = change.requested_delivery_date or order.delivery_date
        if (acceptance.quantity, acceptance.unit_sales_price_kopeks, acceptance.delivery_date) != (quantity, price, date):
            raise HTTPException(status_code=409, detail="Customer acceptance no longer matches")
        if order.production_status == "COMPLETED":
            raise HTTPException(status_code=409, detail="Completed orders cannot be revised")
        next_revision = order.revision + 1
        # Compare-and-swap: only one competing writer can advance this baseline.
        result = db.execute(update(Order).where(
            Order.id == order.id, Order.revision == change.baseline_revision,
            Order.production_status != "COMPLETED"
        ).values(
            revision=next_revision, quantity=quantity, unit_sales_price_kopeks=price,
            unit_est_cost_kopeks=(change.requested_unit_est_cost_kopeks
                                  if change.requested_unit_est_cost_kopeks is not None else order.unit_est_cost_kopeks),
            delivery_date=date, approved_source_id=acceptance.id
        ))
        if result.rowcount != 1:
            db.rollback()
            raise HTTPException(status_code=409, detail="Concurrent order revision conflict")
        db.add(OrderRevision(
            order_id=order.id, revision_number=next_revision, product_code=order.product_code,
            quantity=quantity, unit_sales_price_kopeks=price,
            unit_est_cost_kopeks=(change.requested_unit_est_cost_kopeks
                                  if change.requested_unit_est_cost_kopeks is not None else order.unit_est_cost_kopeks),
            delivery_date=date, approved_source_id=acceptance.id, approved_change_id=change.id
        ))
        change.status = "APPLIED"
        # Pending decisions based on prior order revision cannot be used again.
        for other in db.scalars(select(Change).where(
            Change.order_id == order.id, Change.id != change.id,
            Change.status.in_(["ASSESSMENT_REQUIRED", "PENDING_APPROVAL", "INTERNALLY_APPROVED"])
        )):
            other.status = "ASSESSMENT_REQUIRED"
            other.latest_fingerprint = None
            other.latest_readiness = None
            other.latest_review_id = None
            other.assessment_result = None
        db.commit()
        return {"order_id": order.id, "change_id": change.id, "approved_revision": next_revision,
                "approved_source_id": acceptance.id}

    @app.get("/health", include_in_schema=False)
    def health():
        return {"status": "ok"}

    return app


app = create_app()
