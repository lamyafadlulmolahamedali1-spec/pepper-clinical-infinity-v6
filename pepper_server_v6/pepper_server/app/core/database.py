"""
╔════════════════════════════════════════════════════════════════════╗
║  PEPPER CLINICAL V6 — Database (SQLAlchemy + connection pooling)  ║
╚════════════════════════════════════════════════════════════════════╝
"""
import uuid
from datetime import datetime, timezone
from contextlib import contextmanager

from sqlalchemy import (
    create_engine, Column, String, Integer, Float, Boolean,
    DateTime, ForeignKey, Text, Index
)
from sqlalchemy.orm import declarative_base, sessionmaker, relationship, Session
from sqlalchemy.pool import QueuePool, StaticPool

from app.core.config import settings

# ── Engine ────────────────────────────────────────────────────────────
_is_sqlite = settings.DATABASE_URL.startswith("sqlite")

if _is_sqlite:
    engine = create_engine(
        settings.DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool if ":memory:" in settings.DATABASE_URL else QueuePool,
    )
else:
    engine = create_engine(
        settings.DATABASE_URL,
        pool_size=settings.DB_POOL_SIZE,
        max_overflow=settings.DB_MAX_OVERFLOW,
        pool_pre_ping=True,
        pool_recycle=3600,
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ── Models ────────────────────────────────────────────────────────────
class User(Base):
    __tablename__ = "users"
    id = Column(String, primary_key=True, default=_uuid)
    email = Column(String, unique=True, nullable=False, index=True)
    full_name = Column(String, nullable=False)
    pin_hash = Column(String, nullable=False)            # bcrypt-hashed PIN
    plan = Column(String, default="trial")               # trial | monthly | annual | enterprise
    lang = Column(String, default="en")
    expires_at = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    failed_logins = Column(Integer, default=0)
    last_login = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=_now)

    children = relationship("Child", back_populates="parent", cascade="all, delete-orphan")
    sessions = relationship("TherapySession", back_populates="user", cascade="all, delete-orphan")


class Child(Base):
    __tablename__ = "children"
    id = Column(String, primary_key=True, default=_uuid)
    parent_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name_enc = Column(String, nullable=False)            # encrypted at rest
    age = Column(Integer, default=6)
    diagnosis_enc = Column(String, default="")           # encrypted at rest
    skill_motor = Column(Float, default=50.0)
    skill_cognitive = Column(Float, default=50.0)
    skill_verbal = Column(Float, default=50.0)
    skill_math = Column(Float, default=50.0)
    skill_social = Column(Float, default=50.0)
    total_sessions = Column(Integer, default=0)
    total_score = Column(Integer, default=0)
    created_at = Column(DateTime, default=_now)

    parent = relationship("User", back_populates="children")
    sessions = relationship("TherapySession", back_populates="child", cascade="all, delete-orphan")


class TherapySession(Base):
    __tablename__ = "sessions"
    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    child_id = Column(String, ForeignKey("children.id", ondelete="CASCADE"), index=True)
    started_at = Column(DateTime, default=_now)
    ended_at = Column(DateTime, nullable=True)
    duration_sec = Column(Integer, default=0)
    score = Column(Integer, default=0)
    tasks_total = Column(Integer, default=0)
    tasks_success = Column(Integer, default=0)
    tasks_fail = Column(Integer, default=0)
    tasks_mastered = Column(Integer, default=0)
    avg_attention = Column(Float, default=0.0)
    dominant_emotion = Column(String, default="")
    protocol = Column(String, default="ABA-DTT")

    user = relationship("User", back_populates="sessions")
    child = relationship("Child", back_populates="sessions")


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, nullable=True, index=True)
    action = Column(String, nullable=False)
    ip_address = Column(String, default="")
    detail = Column(Text, default="")
    timestamp = Column(DateTime, default=_now)


Index("ix_sessions_child_ended", TherapySession.child_id, TherapySession.ended_at)


# ── Init + session helpers ────────────────────────────────────────────
def init_db():
    import os
    os.makedirs("data", exist_ok=True)
    os.makedirs("logs", exist_ok=True)
    Base.metadata.create_all(bind=engine)


def get_db():
    """FastAPI dependency — yields a DB session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def db_session():
    """Context-manager DB session for non-request code."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
