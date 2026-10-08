"""
Passwordless login: email a 6-digit code to an allowed address, exchange it for a session cookie.

Flow:
  POST /auth/request-code {email}        -> emails a code
  POST /auth/verify       {email, code}  -> sets the session cookie, creates the user on first login
  GET  /auth/me                          -> current user, or 401
  POST /auth/logout                      -> deletes the session
"""
import hashlib
import hmac
import logging
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from db import get_db
from email_sender import send_login_code
from tables import LoginCode, User, UserSession

SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY or SECRET_KEY == "change-me":
    raise RuntimeError("SECRET_KEY is missing. See backend/.env.example for how to generate one")

ALLOWED_EMAIL_DOMAINS = {
    d.strip().lower() for d in os.getenv("ALLOWED_EMAIL_DOMAINS", "u.nus.edu").split(",") if d.strip()
}
# Secure cookies are only sent over HTTPS; keep false for local http dev
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "false").lower() == "true"

SESSION_COOKIE = "session"
CODE_TTL = timedelta(minutes=10)
SESSION_TTL = timedelta(days=30)
MAX_ATTEMPTS = 5
RESEND_COOLDOWN = timedelta(seconds=60)
MAX_CODES_PER_HOUR = 5

router = APIRouter(prefix="/auth", tags=["auth"])
logger = logging.getLogger("uvicorn.error")


class RequestCodeIn(BaseModel):
    email: str = Field(min_length=3, max_length=254)


class VerifyIn(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    code: str = Field(min_length=6, max_length=6)


def now() -> datetime:
    return datetime.now(timezone.utc)


def normalize_email(raw: str) -> str:
    email = raw.strip().lower()
    local, _, domain = email.rpartition("@")
    if not local or domain not in ALLOWED_EMAIL_DOMAINS:
        allowed = ", ".join(f"@{d}" for d in sorted(ALLOWED_EMAIL_DOMAINS))
        raise HTTPException(status_code=400, detail=f"Please use your NUS email ({allowed})")
    return email


def hash_code(email: str, code: str) -> str:
    # Keyed hash: a leaked database alone isn't enough to brute-force the 6 digits
    return hmac.new(SECRET_KEY.encode(), f"{email}:{code}".encode(), hashlib.sha256).hexdigest()


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def user_to_dict(user: User) -> dict:
    return {"id": user.id, "email": user.email}


@router.post("/request-code")
def request_code(payload: RequestCodeIn, db: Session = Depends(get_db)):
    email = normalize_email(payload.email)
    t = now()

    recent = db.scalars(
        select(LoginCode.created_at)
        .where(LoginCode.email == email, LoginCode.created_at > t - timedelta(hours=1))
        .order_by(LoginCode.created_at.desc())
    ).all()
    if recent and recent[0] > t - RESEND_COOLDOWN:
        raise HTTPException(status_code=429, detail="Please wait a minute before requesting another code")
    if len(recent) >= MAX_CODES_PER_HOUR:
        raise HTTPException(status_code=429, detail="Too many codes requested. Try again in an hour")

    # Only the newest code works; retire any earlier ones
    db.execute(
        update(LoginCode)
        .where(LoginCode.email == email, LoginCode.consumed_at.is_(None))
        .values(consumed_at=t)
    )
    # Housekeeping: codes older than a day are useless
    db.execute(delete(LoginCode).where(LoginCode.created_at < t - timedelta(days=1)))

    code = f"{secrets.randbelow(1_000_000):06d}"
    login_code = LoginCode(email=email, code_hash=hash_code(email, code), expires_at=t + CODE_TTL)
    db.add(login_code)
    db.commit()

    try:
        send_login_code(email, code, int(CODE_TTL.total_seconds() // 60))
    except Exception:
        logger.exception("Sending login code to %s failed", email)
        # Don't let a failed send count towards the resend cooldown
        db.delete(login_code)
        db.commit()
        raise HTTPException(status_code=502, detail="Couldn't send the email. Please try again")

    return {"ok": True}


@router.post("/verify")
def verify(payload: VerifyIn, response: Response, db: Session = Depends(get_db)):
    email = normalize_email(payload.email)
    t = now()

    login_code = db.scalars(
        select(LoginCode)
        .where(LoginCode.email == email, LoginCode.consumed_at.is_(None), LoginCode.expires_at > t)
        .order_by(LoginCode.created_at.desc())
        .limit(1)
        .with_for_update()  # two simultaneous guesses can't both slip past the attempt count
    ).first()
    if login_code is None:
        raise HTTPException(status_code=400, detail="This code has expired. Request a new one")

    if not hmac.compare_digest(login_code.code_hash, hash_code(email, payload.code.strip())):
        login_code.attempts += 1
        if login_code.attempts >= MAX_ATTEMPTS:
            login_code.consumed_at = t
            db.commit()
            raise HTTPException(status_code=400, detail="Too many wrong attempts. Request a new code")
        db.commit()
        raise HTTPException(status_code=400, detail="Incorrect code")

    login_code.consumed_at = t

    user = db.scalars(select(User).where(User.email == email)).first()
    if user is None:
        user = User(email=email)
        db.add(user)
    user.last_login_at = t
    db.flush()

    token = secrets.token_urlsafe(32)
    db.add(UserSession(token_hash=hash_token(token), user_id=user.id, expires_at=t + SESSION_TTL))
    db.commit()

    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=int(SESSION_TTL.total_seconds()),
        httponly=True,  # JavaScript can't read it, so XSS can't steal it
        secure=COOKIE_SECURE,
        samesite="lax",
        path="/",
    )
    return user_to_dict(user)


def get_current_user_optional(
    session: Optional[str] = Cookie(default=None, alias=SESSION_COOKIE),
    db: Session = Depends(get_db),
) -> Optional[User]:
    if not session:
        return None
    row = db.scalars(
        select(UserSession).where(
            UserSession.token_hash == hash_token(session), UserSession.expires_at > func.now()
        )
    ).first()
    return row.user if row else None


def get_current_user(user: Optional[User] = Depends(get_current_user_optional)) -> User:
    """Dependency for endpoints that require login."""
    if user is None:
        raise HTTPException(status_code=401, detail="Please log in first")
    return user


@router.get("/me")
def me(user: User = Depends(get_current_user)):
    return user_to_dict(user)


@router.post("/logout")
def logout(
    response: Response,
    session: Optional[str] = Cookie(default=None, alias=SESSION_COOKIE),
    db: Session = Depends(get_db),
):
    if session:
        db.execute(delete(UserSession).where(UserSession.token_hash == hash_token(session)))
        db.commit()
    response.delete_cookie(SESSION_COOKIE, path="/", secure=COOKIE_SECURE, samesite="lax")
    return {"ok": True}
