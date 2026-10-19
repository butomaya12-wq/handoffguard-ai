"""Reviewer-gated, same-origin educational cloud entrypoint.

No production identity provider, user isolation or tenant separation is offered.
The ordinary local FastAPI app and Docker Compose stack remain untouched.
"""
import hmac
import json
import os
from collections import defaultdict, deque
from pathlib import Path
from time import monotonic
from urllib.parse import parse_qs

from fastapi import Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from sqlalchemy.engine.url import make_url
from starlette.staticfiles import StaticFiles

from .main import create_app


COOKIE_NAME = "handoffguard_demo_access"
SESSION_MAX_AGE_SECONDS = 7200
MAX_FAILED_LOGINS = 10
FAIL_WINDOW_SECONDS = 60

LOGIN_PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>HandoffGuard AI — Reviewer Access</title></head>
<body style="font:16px system-ui;max-width:28rem;margin:12vh auto;padding:1.5rem">
<h1>HandoffGuard AI</h1><p>Private educational demo. Synthetic orders only.
Not a production identity system.</p>
<form action="/demo/login" method="post">
<label>Reviewer access key<br/>
<input type="password" name="access_key" required autocomplete="off"
style="width:100%;padding:.7rem;box-sizing:border-box"/></label>
<p><button type="submit" style="padding:.7rem 1.4rem">Continue</button></p>
</form><p><small>Request access credentials from the project owner privately.</small></p>
</body></html>"""


def create_cloud_app(
    *,
    static_directory: str | Path | None = None,
    _testing_database_url: str | None = None,
):
    """ASGI factory; production requires explicit Postgres + strong secrets.

    _testing_database_url is injectable only by isolated test code, never
    read from an environment variable or network request.
    """
    raw_url = _testing_database_url or os.environ.get("HANDOFFGUARD_DATABASE_URL", "")
    if not raw_url:
        raise RuntimeError("Cloud startup blocked: persistent database is not configured")
    if _testing_database_url is None:
        try:
            dialect = make_url(raw_url).drivername
        except Exception as exc:
            raise RuntimeError("Cloud startup blocked: malformed database configuration") from exc
        if dialect != "postgresql+psycopg":
            raise RuntimeError("Cloud startup blocked: managed PostgreSQL is required")

    access_key = os.getenv("HANDOFFGUARD_DEMO_ACCESS_KEY", "")
    cookie_secret = os.getenv("HANDOFFGUARD_DEMO_COOKIE_SECRET", "")
    if len(access_key) < 32 or len(cookie_secret) < 32:
        raise RuntimeError("Cloud startup blocked: secure demo access secrets are missing")
    if hmac.compare_digest(access_key, cookie_secret):
        raise RuntimeError("Cloud startup blocked: access key and cookie signing secret must differ")

    try:
        configured_roles = json.loads(os.getenv("HANDOFFGUARD_AUTH_TOKENS", ""))
    except (ValueError, TypeError) as exc:
        raise RuntimeError("Cloud startup blocked: role-token configuration is malformed") from exc
    if not isinstance(configured_roles, dict) or len(configured_roles) != 3:
        raise RuntimeError("Cloud startup blocked: exactly three distinct role tokens are required")
    if any(
        not isinstance(token, str)
        or len(token) < 32
        or token in {"demo-sales", "demo-production", "demo-approver",
                     "test-sales-token", "test-production-token", "test-approver-token"}
        or (_testing_database_url is None and
            token.lower().startswith(("demo-", "test-", "ci-", "local-")))
        or not isinstance(actor, dict)
        or not isinstance(actor.get("id"), str)
        or not actor["id"]
        or actor.get("role") not in {"sales", "production", "approver"}
        for token, actor in configured_roles.items()
    ):
        raise RuntimeError("Cloud startup blocked: invalid cloud-only role credentials")
    if {actor["role"] for actor in configured_roles.values()} != {"sales", "production", "approver"}:
        raise RuntimeError("Cloud startup blocked: one identity per business role is required")

    static_path = Path(static_directory) if static_directory is not None else Path("/app/static")
    if not (static_path / "index.html").is_file():
        raise RuntimeError("Cloud startup blocked: compiled frontend/index.html is missing")

    signer = URLSafeTimedSerializer(cookie_secret, salt="handoffguard-reviewer-gate-v1")
    failures = defaultdict(deque)
    app = create_app(raw_url)
    # Explicitly identify the protected cloud entrypoint for startup-only diagnostic.
    app.state.cloud_mode = True

    @app.middleware("http")
    async def require_demo_access(request: Request, call_next):
        path = request.url.path
        if path in {"/health", "/demo/login"}:
            return await call_next(request)

        cookie = request.cookies.get(COOKIE_NAME, "")
        try:
            permitted = signer.loads(cookie, max_age=SESSION_MAX_AGE_SECONDS) == "reviewer"
        except (BadSignature, SignatureExpired):
            permitted = False

        if not permitted:
            if path.startswith("/api/") or path in {"/openapi.json", "/docs", "/redoc"}:
                return JSONResponse(
                    {"detail": "Reviewer access required"},
                    status_code=401,
                    headers={"Cache-Control": "no-store"},
                )
            return RedirectResponse("/demo/login", status_code=302)

        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.get("/demo/login", include_in_schema=False)
    async def reviewer_login_page():
        return HTMLResponse(LOGIN_PAGE, headers={"Cache-Control": "no-store"})

    @app.post("/demo/login", include_in_schema=False)
    async def reviewer_login(request: Request):
        address = request.client.host if request.client else "unknown"
        now = monotonic()
        attempts = failures[address]
        while attempts and now - attempts[0] > FAIL_WINDOW_SECONDS:
            attempts.popleft()
        if len(attempts) >= MAX_FAILED_LOGINS:
            return HTMLResponse("Too many attempts. Try again later.", status_code=429)

        raw_body = await request.body()
        if len(raw_body) > 4096:
            return HTMLResponse("Request too large", status_code=413)
        try:
            form = parse_qs(raw_body.decode("utf-8"), keep_blank_values=True)
            supplied_key = form.get("access_key", [""])[0]
        except UnicodeDecodeError:
            supplied_key = ""
        if not hmac.compare_digest(supplied_key, access_key):
            attempts.append(now)
            return HTMLResponse("Invalid reviewer access key", status_code=401,
                                headers={"Cache-Control": "no-store"})

        attempts.clear()
        response = RedirectResponse("/", status_code=303)
        response.set_cookie(
            COOKIE_NAME, signer.dumps("reviewer"),
            max_age=SESSION_MAX_AGE_SECONDS, secure=True,
            httponly=True, samesite="lax", path="/",
        )
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.post("/demo/logout", include_in_schema=False)
    async def reviewer_logout():
        response = RedirectResponse("/demo/login", status_code=303)
        response.delete_cookie(COOKIE_NAME, path="/", secure=True, httponly=True, samesite="lax")
        return response

    # Mount last: API endpoints, login and health must be dispatched before static.
    app.mount("/", StaticFiles(directory=str(static_path), html=True), name="frontend")
    return app
