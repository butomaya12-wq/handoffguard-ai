# Lesson: OrderRevision — step 1 (draft PR)

## Why

An approved order should retain its complete history. A proposed or rejected change is not an approved revision. A future approved change will append V2 rather than rewriting V1.

## Scope of this pull request

1. SQLAlchemy model `OrderRevision` with a unique `(order_id, revision_number)` constraint and basic numeric DB checks.
2. New order creation writes `Order` and its V1 snapshot in **one database transaction** using `db.flush()` and `db.commit()`.
3. Authenticated `GET /api/v1/orders/{order_id}/revisions` lists approved snapshots (oldest first).
4. Four added API tests for creation, proposal, rejection and missing order.
5. OpenAPI draft updated with the new read endpoint and schema.

## Critical distinction

**This is NOT Gate 02 completion.** No V2 application, customer acceptance, historic backfill, audit event stream or concurrent apply is implemented. Production-grade immutability is not guaranteed by this simple table: the application must prohibit updates/deletes and tests must cover that flow; additional database protections are future hardening.

## Database migration warning

SQLAlchemy `Base.metadata.create_all()` creates the new table if it does not exist, but **does not backfill V1 snapshots for orders that were already in the local database**. All newly created orders obtain V1. Existing databases require a deliberate migration/backfill before use; never reset real data to work around this. Gate 01 local tests use new temporary databases.

## Test expectations

New order => `order_revisions` contains V1.
Draft 120 => V1 only.
Rejected 130 => V1 only; rejected proposal remains in `changes`.
Missing order => 404.

GitHub Actions should run the existing 11 tests plus 4 new tests (15 total). See CI log for independently observed pass/fail.

## Next lesson

How to enforce an immutable approved V2 and guard against two concurrent changes to a stale baseline, with matching customer acceptance and atomic application.
