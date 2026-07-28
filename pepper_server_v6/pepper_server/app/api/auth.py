"""
╔════════════════════════════════════════════════════════════════════╗
║  PEPPER CLINICAL V6 — Auth Router (trial · login · refresh)       ║
╚════════════════════════════════════════════════════════════════════╝
"""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session

from app.core.database import get_db, User, Child
from app.core.security import (
    hash_secret, verify_secret, generate_pin,
    create_access_token, create_refresh_token, decode_token,
    encrypt_field, rate_limiter,
)
from app.core.config import settings
from app.models.schemas import (
    TrialRequest, TrialResponse, LoginRequest, TokenResponse,
    RefreshRequest, UserOut,
)

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


def _client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


@router.post("/trial", response_model=TrialResponse, status_code=status.HTTP_201_CREATED)
def start_trial(body: TrialRequest, request: Request, db: Session = Depends(get_db)):
    # Rate limit by IP
    ip = _client_ip(request)
    if not rate_limiter.record_attempt(f"trial:{ip}", 10, 60, 300):
        raise HTTPException(status_code=429, detail="Too many requests. Try again later.")

    existing = db.query(User).filter(User.email == body.email.lower()).first()
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered. Please log in.")

    pin = generate_pin()
    expires = datetime.now(timezone.utc) + timedelta(days=settings.TRIAL_DAYS)

    user = User(
        email=body.email.lower(),
        full_name=body.full_name,
        pin_hash=hash_secret(pin),
        plan="trial",
        lang=body.lang,
        expires_at=expires,
        is_active=True,
    )
    db.add(user)
    db.flush()

    child = Child(
        parent_id=user.id,
        name_enc=encrypt_field(body.child_name),
        age=body.child_age,
        diagnosis_enc=encrypt_field(""),
    )
    db.add(child)
    db.commit()

    return TrialResponse(
        user_id=user.id,
        pin=pin,
        expires_at=expires,
        message="Trial created. Save your PIN — it will not be shown again.",
    )


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, request: Request, db: Session = Depends(get_db)):
    ip = _client_ip(request)
    key = f"login:{ip}:{body.email.lower()}"

    if rate_limiter.is_locked(key):
        raise HTTPException(status_code=429,
                            detail=f"Too many failed attempts. Locked for {settings.LOGIN_LOCKOUT_MINUTES} min.")

    user = db.query(User).filter(User.email == body.email.lower()).first()

    if not user or not verify_secret(body.pin, user.pin_hash):
        rate_limiter.record_attempt(key, settings.LOGIN_RATE_LIMIT, 60,
                                    settings.LOGIN_LOCKOUT_MINUTES * 60)
        if user:
            user.failed_logins += 1
            db.commit()
        raise HTTPException(status_code=401, detail="Invalid email or PIN")

    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account disabled")

    # Check trial/subscription expiry
    if user.expires_at:
        exp = user.expires_at
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        if exp < datetime.now(timezone.utc) and user.plan == "trial":
            raise HTTPException(status_code=402, detail="Trial expired. Please subscribe.")

    rate_limiter.reset(key)
    user.failed_logins = 0
    user.last_login = datetime.now(timezone.utc)
    db.commit()

    access = create_access_token({"sub": user.id, "email": user.email})
    refresh = create_refresh_token({"sub": user.id})

    return TokenResponse(
        access_token=access,
        refresh_token=refresh,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=UserOut.model_validate(user),
    )


@router.post("/refresh", response_model=TokenResponse)
def refresh_token(body: RefreshRequest, db: Session = Depends(get_db)):
    payload = decode_token(body.refresh_token)
    if payload is None or payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    user = db.query(User).filter(User.id == payload.get("sub"), User.is_active == True).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    access = create_access_token({"sub": user.id, "email": user.email})
    refresh = create_refresh_token({"sub": user.id})

    return TokenResponse(
        access_token=access,
        refresh_token=refresh,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=UserOut.model_validate(user),
    )
