"""
╔════════════════════════════════════════════════════════════════════╗
║  PEPPER CLINICAL V6 — Pydantic Schemas (request/response validation)║
╚════════════════════════════════════════════════════════════════════╝
"""
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, EmailStr, Field, field_validator


# ── Auth ──────────────────────────────────────────────────────────────
class TrialRequest(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=100)
    email: EmailStr
    child_name: str = Field(..., min_length=1, max_length=100)
    child_age: int = Field(default=6, ge=2, le=18)
    lang: str = Field(default="en")

    @field_validator("lang")
    @classmethod
    def valid_lang(cls, v):
        return v if v in ("en", "ar") else "en"


class TrialResponse(BaseModel):
    user_id: str
    pin: str
    expires_at: datetime
    message: str


class LoginRequest(BaseModel):
    email: EmailStr
    pin: str = Field(..., min_length=4, max_length=12)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: "UserOut"


class RefreshRequest(BaseModel):
    refresh_token: str


# ── User ──────────────────────────────────────────────────────────────
class UserOut(BaseModel):
    id: str
    email: str
    full_name: str
    plan: str
    lang: str
    expires_at: Optional[datetime]
    is_active: bool

    model_config = {"from_attributes": True}


# ── Child ─────────────────────────────────────────────────────────────
class ChildCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    age: int = Field(default=6, ge=2, le=18)
    diagnosis: str = Field(default="", max_length=500)


class ChildOut(BaseModel):
    id: str
    name: str
    age: int
    diagnosis: str
    skill_motor: float
    skill_cognitive: float
    skill_verbal: float
    skill_math: float
    skill_social: float
    total_sessions: int
    total_score: int


# ── Session ───────────────────────────────────────────────────────────
class SessionStart(BaseModel):
    child_id: str
    protocol: str = Field(default="ABA-DTT")


class SessionEnd(BaseModel):
    session_id: str
    duration_sec: int = Field(default=0, ge=0)
    score: int = Field(default=0, ge=0)
    tasks_total: int = Field(default=0, ge=0)
    tasks_success: int = Field(default=0, ge=0)
    tasks_fail: int = Field(default=0, ge=0)
    tasks_mastered: int = Field(default=0, ge=0)
    avg_attention: float = Field(default=0.0, ge=0, le=100)
    dominant_emotion: str = Field(default="")


class SessionOut(BaseModel):
    id: str
    started_at: datetime
    ended_at: Optional[datetime]
    duration_sec: int
    score: int
    tasks_total: int
    tasks_success: int
    tasks_mastered: int
    avg_attention: float
    protocol: str


# ── Tasks ─────────────────────────────────────────────────────────────
class TaskRequest(BaseModel):
    domain: Optional[str] = None
    level: int = Field(default=1, ge=1, le=3)
    count: int = Field(default=20, ge=1, le=100)


TokenResponse.model_rebuild()
