"""Local account sessions; no registration, email or external identity side effects."""

import secrets
import uuid
from datetime import timedelta
from typing import Literal

from fastapi import APIRouter, Body, Depends, HTTPException, Request, Response
from pwdlib import PasswordHash
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError

from app.auth.security import (
    Principal,
    authorize_request,
    check_origin,
    cookie_name,
    digest,
    load_session,
    record_event,
    require_csrf,
    secure_cookies,
    session_factory,
    throttle,
)
from app.database.models import AuthSession, User, utc_now_naive

router = APIRouter(dependencies=[Depends(authorize_request)])
passwords = PasswordHash.recommended()
DUMMY_HASH = passwords.hash(secrets.token_hex(32))


class Login(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=128)


class NewUser(Login):
    password: str = Field(min_length=12, max_length=128)
    role: Literal["employee", "reviewer", "admin"]
    display_name: str = Field(default="", max_length=100)

    @field_validator("display_name")
    @classmethod
    def clean_name(cls, value):
        value = value.strip()
        if any(ord(char) < 32 or ord(char) == 127 for char in value):
            raise ValueError("Names cannot contain control characters.")
        return value


class ProfileUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    display_name: str = Field(min_length=1, max_length=100)

    @field_validator("display_name")
    @classmethod
    def clean_name(cls, value):
        value = NewUser.clean_name(value)
        if not value:
            raise ValueError("A name is required.")
        return value


class PasswordChange(BaseModel):
    model_config = ConfigDict(extra="forbid")
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=12, max_length=128)


def issue_session(db, response: Response, user_id: str | None = None) -> str:
    token, csrf = secrets.token_hex(32), secrets.token_hex(32)
    now = utc_now_naive()
    duration = 3600 * 8 if user_id else 600
    db.add(
        AuthSession(
            token_hash=digest(token),
            user_id=user_id,
            csrf_hash=digest(csrf),
            expires_at=now + timedelta(seconds=duration),
            last_seen=now,
        )
    )
    db.commit()
    response.set_cookie(
        cookie_name(),
        token,
        httponly=True,
        secure=secure_cookies(),
        samesite="lax",
        max_age=duration,
        path="/",
    )
    response.headers["Cache-Control"] = "no-store"
    return csrf


@router.get("/auth/csrf")
def csrf(request: Request, response: Response):
    check_origin(request)
    with session_factory(request)() as db:
        throttle(
            db, "csrf:" + (request.client.host if request.client else "unknown"), 60
        )
        try:
            session = load_session(request, db)
        except HTTPException:
            return {"csrf_token": issue_session(db, response)}
        value = secrets.token_hex(32)
        session.csrf_hash = digest(value)
        db.commit()
        response.headers["Cache-Control"] = "no-store"
        return {"csrf_token": value}


@router.post("/auth/login")
def login(payload: Login, request: Request, response: Response):
    with session_factory(request)() as db:
        session = load_session(request, db)
        require_csrf(request, session)
        email = payload.email.strip().lower()
        throttle(
            db,
            "login-ip:" + (request.client.host if request.client else "unknown"),
            20,
            300,
        )
        throttle(db, "login-account:" + email, 10, 300)
        user = db.scalar(select(User).where(User.email == email))
        try:
            valid = passwords.verify(
                payload.password, user.password_hash if user else DUMMY_HASH
            )
        except (ValueError, TypeError):
            valid = False
        if not valid or user is None or not user.active:
            record_event(db, "login_failed")
            raise HTTPException(401, "Invalid credentials.")
        # Rotate the credential and revoke the pre-login session (session fixation).
        db.delete(session)
        db.commit()
        value = issue_session(db, response, user.id)
        record_event(db, "login", Principal(user.id, user.organization_id, user.role))
        return {"csrf_token": value, "user": public_user(user)}


def public_user(user):
    return {
        "id": user.id,
        "email": user.email,
        "display_name": user.display_name,
        "role": user.role,
        "organization_id": user.organization_id,
        "active": user.active,
    }


@router.get("/auth/me")
def me(request: Request):
    with session_factory(request)() as db:
        return public_user(db.get(User, request.state.actor.id))


@router.get("/auth/profile")
def profile(request: Request):
    from app.auth.profiles import personal_stats

    with session_factory(request)() as db:
        return {
            "user": public_user(db.get(User, request.state.actor.id)),
            "stats": personal_stats(db, request.state.actor),
        }


@router.post("/auth/profile")
def update_profile(payload: ProfileUpdate, request: Request):
    with session_factory(request)() as db:
        user = db.get(User, request.state.actor.id)
        user.display_name = payload.display_name
        db.commit()
        record_event(db, "profile_updated", request.state.actor)
        return public_user(user)


@router.post("/auth/change-password")
def change_password(payload: PasswordChange, request: Request, response: Response):
    with session_factory(request)() as db:
        throttle(db, "password-change:" + request.state.actor.id, 5, 300)
        user = db.get(User, request.state.actor.id)
        previous_hash = user.password_hash
        if not passwords.verify(payload.current_password, previous_hash):
            record_event(db, "password_change_failed", request.state.actor)
            raise HTTPException(400, "Current password is incorrect.")
        if payload.new_password == payload.current_password:
            raise HTTPException(400, "Choose a different new password.")
        changed = db.execute(
            update(User)
            .where(User.id == user.id, User.password_hash == previous_hash)
            .values(password_hash=passwords.hash(payload.new_password))
        ).rowcount
        if changed != 1:
            db.rollback()
            raise HTTPException(409, "Password changed concurrently. Sign in again.")
        db.execute(delete(AuthSession).where(AuthSession.user_id == user.id))
        db.commit()
        # Keep this browser signed in with a fresh credential; revoke every old session.
        csrf = issue_session(db, response, user.id)
        record_event(db, "password_changed", request.state.actor)
        return {"status": "password_changed", "csrf_token": csrf}


@router.post("/auth/logout")
def logout(request: Request, response: Response):
    with session_factory(request)() as db:
        db.delete(load_session(request, db))
        db.commit()
        record_event(db, "logout", request.state.actor)
    response.delete_cookie(
        cookie_name(), secure=secure_cookies(), httponly=True, samesite="lax", path="/"
    )
    return {"status": "signed_out"}


@router.get("/admin/users")
def users(request: Request):
    with session_factory(request)() as db:
        return [
            public_user(u)
            for u in db.scalars(
                select(User).where(
                    User.organization_id == request.state.actor.organization_id
                )
            ).all()
        ]


@router.post("/admin/users", status_code=201)
def create_user(payload: NewUser, request: Request):
    with session_factory(request)() as db:
        email = payload.email.strip().lower()
        if db.scalar(select(User.id).where(User.email == email)):
            raise HTTPException(409, "Account cannot be created.")
        user = User(
            id=str(uuid.uuid4()),
            organization_id=request.state.actor.organization_id,
            email=email,
            display_name=payload.display_name,
            role=payload.role,
            password_hash=passwords.hash(payload.password),
        )
        db.add(user)
        try:
            db.commit()
        except IntegrityError as error:
            db.rollback()
            raise HTTPException(409, "Account cannot be created.") from error
        record_event(db, "user_created", request.state.actor, user.id)
        return public_user(user)


@router.post("/admin/users/{user_id}/status")
def account_status(
    user_id: str, request: Request, active: bool = Body(..., embed=True, strict=True)
):
    with session_factory(request)() as db:
        user = db.get(User, user_id)
        if user is None or user.organization_id != request.state.actor.organization_id:
            raise HTTPException(404, "Account not found.")
        if user.id == request.state.actor.id:
            raise HTTPException(409, "Cannot disable your own account.")
        user.active = active
        if not active:
            for session in db.scalars(
                select(AuthSession).where(AuthSession.user_id == user.id)
            ).all():
                db.delete(session)
        db.commit()
        record_event(
            db,
            "user_enabled" if active else "user_disabled",
            request.state.actor,
            user.id,
        )
        return public_user(user)


@router.post("/admin/users/{user_id}/profile")
def admin_update_profile(user_id: str, payload: ProfileUpdate, request: Request):
    with session_factory(request)() as db:
        user = db.get(User, user_id)
        if user is None or user.organization_id != request.state.actor.organization_id:
            raise HTTPException(404, "Account not found.")
        user.display_name = payload.display_name
        db.commit()
        record_event(db, "user_profile_updated", request.state.actor, user.id)
        return public_user(user)
