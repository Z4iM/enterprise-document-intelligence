"""Session authentication and deny-by-default resource permissions."""

import hashlib
import os
import re
import secrets
import time
from dataclasses import dataclass
from datetime import timedelta
from typing import Annotated

from fastapi import Depends, HTTPException, Request
from sqlalchemy import case, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from app.database import database
from app.database.models import (
    AuthSession,
    Document,
    PolicyDocument,
    RequestLimit,
    SecurityEvent,
    User,
    utc_now_naive,
)

PUBLIC = {"/", "/health", "/ready", "/auth/csrf", "/auth/login"}


@dataclass(frozen=True)
class Principal:
    id: str
    organization_id: str
    role: str


def session_factory(request: Request):
    return getattr(request.app.state, "resource_session_factory", database.SessionLocal)


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def secure_cookies() -> bool:
    return os.getenv("EDI_ENV") != "development"


def cookie_name() -> str:
    return "__Host-edi_session" if secure_cookies() else "edi_session"


def check_origin(request: Request) -> None:
    defaults = (
        "http://127.0.0.1:3000,http://127.0.0.1:8000" if not secure_cookies() else ""
    )
    origins = {
        x.strip()
        for x in os.getenv("EDI_ALLOWED_ORIGINS", defaults).split(",")
        if x.strip()
    }
    if secure_cookies() and (
        not origins or any(not x.startswith("https://") for x in origins)
    ):
        raise HTTPException(503, "Configure HTTPS application origins.")
    if request.headers.get("sec-fetch-site") == "cross-site":
        raise HTTPException(403, "Cross-site request denied.")
    origin = request.headers.get("origin")
    if origin and origin not in origins:
        raise HTTPException(403, "Request origin denied.")


def record_event(
    db, action: str, actor: Principal | None = None, resource_id: str | None = None
):
    db.add(
        SecurityEvent(
            action=action,
            resource_id=resource_id,
            actor_id=actor.id if actor else None,
            organization_id=actor.organization_id if actor else None,
        )
    )
    db.commit()


def throttle(db, key: str, maximum: int, seconds: int = 60):
    """Atomic, persistent fixed windows across workers/restarts (SQLite backend)."""
    window = int(time.time()) // seconds
    key = digest(key)
    insert = pg_insert if db.get_bind().dialect.name == "postgresql" else sqlite_insert
    statement = insert(RequestLimit).values(key=key, window=window, count=1)
    statement = statement.on_conflict_do_update(
        index_elements=[RequestLimit.key],
        set_={
            "window": window,
            "count": case(
                (RequestLimit.window == window, RequestLimit.count + 1), else_=1
            ),
        },
        where=RequestLimit.window <= window,
    ).returning(RequestLimit.count)
    count = db.execute(statement).scalar_one_or_none()
    db.commit()
    if count is None or count > maximum:
        raise HTTPException(
            429, "Too many requests.", headers={"Retry-After": str(seconds)}
        )


def load_session(request: Request, db):
    raw = request.cookies.get(cookie_name(), "")
    if not re.fullmatch(r"[a-f0-9]{64}", raw):
        raise HTTPException(401, "Sign in required.")
    session = db.get(AuthSession, digest(raw))
    now = utc_now_naive()
    if (
        session is None
        or session.expires_at <= now
        or session.last_seen + timedelta(minutes=30) <= now
    ):
        raise HTTPException(401, "Sign in required.")
    return session


def require_csrf(request: Request, session: AuthSession):
    check_origin(request)
    value = request.headers.get("x-csrf-token", "")
    if len(value) != 64 or not secrets.compare_digest(digest(value), session.csrf_hash):
        raise HTTPException(403, "CSRF validation failed.")


def require_actor(request: Request) -> Principal | None:
    if request.url.path in PUBLIC:
        return None
    with session_factory(request)() as db:
        session = load_session(request, db)
        user = db.get(User, session.user_id) if session.user_id else None
        if (
            user is None
            or not user.active
            or user.role not in {"employee", "reviewer", "admin"}
        ):
            raise HTTPException(401, "Sign in required.")
        actor = Principal(user.id, user.organization_id, user.role)
        if request.method not in {"GET", "HEAD", "OPTIONS"}:
            try:
                require_csrf(request, session)
            except HTTPException:
                record_event(db, "csrf_denied", actor)
                raise
        throttle(db, "user:" + actor.id, 120)
        session.last_seen = utc_now_naive()
        db.commit()
        return actor


def require_reviewer(actor: Principal):
    if actor.role not in {"reviewer", "admin"}:
        raise HTTPException(403, "Reviewer permission required.")


def document_filter(actor: Principal):
    conditions = [Document.organization_id == actor.organization_id]
    if actor.role == "employee":
        conditions.append(Document.owner_id == actor.id)
    return conditions


def require_document(db, document_id: str, actor: Principal):
    if not isinstance(document_id, str) or not re.fullmatch(
        r"[A-Za-z0-9_-]{1,128}", document_id
    ):
        raise HTTPException(404, "Document not found.")
    doc = db.get(Document, document_id)
    if (
        doc is None
        or doc.organization_id != actor.organization_id
        or (actor.role == "employee" and doc.owner_id != actor.id)
    ):
        raise HTTPException(404, "Document not found.")
    return doc


def require_policy(db, policy_id: str, actor: Principal):
    if not isinstance(policy_id, str) or not re.fullmatch(
        r"[A-Za-z0-9_-]{1,128}", policy_id
    ):
        raise HTTPException(404, "Policy not found.")
    policy = db.get(PolicyDocument, policy_id)
    if policy is None or policy.organization_id != actor.organization_id:
        raise HTTPException(404, "Policy not found.")
    return policy


def authorized_scope(db, actor: Principal) -> tuple[set[str], set[str]]:
    return (
        set(db.scalars(select(Document.id).where(*document_filter(actor))).all()),
        set(
            db.scalars(
                select(PolicyDocument.id).where(
                    PolicyDocument.organization_id == actor.organization_id
                )
            ).all()
        ),
    )


def authorize_request(
    request: Request, actor: Annotated[Principal | None, Depends(require_actor)]
):
    if request.url.path in PUBLIC:
        return
    if actor is None:
        raise HTTPException(401, "Sign in required.")
    request.state.actor = actor
    from app.observability.tracing import bind_organization
    bind_organization(actor.organization_id)
    parts = request.url.path.strip("/").split("/")
    with session_factory(request)() as db:
        try:
            if parts[0] == "documents" and len(parts) > 1 and parts[1] != "upload":
                require_document(db, parts[1], actor)
                if parts[-1] == "review":
                    require_reviewer(actor)
            if parts[0] == "reviews":
                require_reviewer(actor)
            if parts[0] == "policies":
                if request.method != "GET":
                    require_reviewer(actor)
                if len(parts) > 1 and parts[1] != "upload":
                    require_policy(db, parts[1], actor)
            if (
                parts[0] == "admin"
                or (request.url.path == "/auth/profile" and request.method == "POST")
            ) and actor.role != "admin":
                raise HTTPException(403, "Administrator permission required.")
        except HTTPException:
            record_event(db, "access_denied", actor)
            raise
