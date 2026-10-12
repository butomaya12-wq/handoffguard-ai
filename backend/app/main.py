"""HandoffGuard API — Gate 01: create, propose, assess and enforce role boundaries."""
import json
import os
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from .logic import impact_assessment
from .models import Base, Order, ProductionReview, Change, ApprovalDecision
from .schemas import CreateOrder, ProductionReviewInput, ChangeInput, DecisionInput


def create_app(database_url: str | None = None) -> FastAPI:
    database_url = database_url or os.getenv("HANDOFFGUARD_DATABASE_URL", "sqlite:///./handoffguard.db")
    engine = create_engine(database_url, connect_args={"check_same_thread": False} if database_url.startswith("sqlite") else {}, pool_pre_ping=True)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        Base.metadata.create_all(engine)
        yield
        engine.dispose()

    app = FastAPI(title="HandoffGuard AI API", version="0.3.0-gate01", lifespan=lifespan)

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

    @app.post("/api/v1/orders", status_code=201, operation_id="createOrder")
    def create_order(payload: CreateOrder, db: Annotated[Session, Depends(get_db)], actor: Annotated[dict, Depends(require_role("sales"))]):
        order = Order(**payload.model_dump())
        db.add(order)
        db.commit()
        db.refresh(order)
        return serialize_order(order)

    @app.get("/api/v1/orders/{order_id}", operation_id="getOrder")
    def get_order(order_id: str, db: Annotated[Session, Depends(get_db)], actor: Annotated[dict, Depends(current_actor)]):
        return serialize_order(fetch_order(db, order_id))

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

    @app.get("/health", include_in_schema=False)
    def health():
        return {"status": "ok"}

    return app


app = create_app()
