"""
╔════════════════════════════════════════════════════════════════════╗
║  PEPPER CLINICAL INFINITY V6 — Core Configuration                 ║
║  © 2026 Lamya Fadlulmola Hamed Ali — All Rights Reserved          ║
╚════════════════════════════════════════════════════════════════════╝
"""
import os
import secrets
from functools import lru_cache
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # ── App ───────────────────────────────────────────────────────────
    APP_NAME: str = "Pepper Clinical Infinity V6"
    APP_VERSION: str = "6.0.0"
    ENV: str = "production"           # production | development
    DEBUG: bool = False

    # ── Security ──────────────────────────────────────────────────────
    SECRET_KEY: str = secrets.token_urlsafe(48)
    JWT_SECRET: str = secrets.token_urlsafe(48)
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24          # 24 hours
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    PIN_LENGTH: int = 6
    BCRYPT_ROUNDS: int = 12
    TRIAL_DAYS: int = 15

    # ── Rate limiting ─────────────────────────────────────────────────
    RATE_LIMIT_PER_MINUTE: int = 60
    LOGIN_RATE_LIMIT: int = 5            # login attempts per minute
    LOGIN_LOCKOUT_MINUTES: int = 15

    # ── Database ──────────────────────────────────────────────────────
    DATABASE_URL: str = "sqlite:///./data/pepper.db"
    DB_POOL_SIZE: int = 20
    DB_MAX_OVERFLOW: int = 10

    # ── CORS ──────────────────────────────────────────────────────────
    ALLOWED_ORIGINS: str = "*"
    ALLOWED_HOSTS: str = "*"

    # ── Encryption (data at rest) ─────────────────────────────────────
    ENCRYPTION_KEY: str = secrets.token_urlsafe(32)

    # ── Server ────────────────────────────────────────────────────────
    HOST: str = "127.0.0.1"
    PORT: int = 8000
    WORKERS: int = 4

    # ── Email (optional) ──────────────────────────────────────────────
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = "noreply@pepperclinical.com"

    @property
    def origins_list(self) -> List[str]:
        if self.ALLOWED_ORIGINS == "*":
            return ["*"]
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",") if o.strip()]

    @property
    def hosts_list(self) -> List[str]:
        if self.ALLOWED_HOSTS == "*":
            return ["*"]
        return [h.strip() for h in self.ALLOWED_HOSTS.split(",") if h.strip()]

    @property
    def is_production(self) -> bool:
        return self.ENV.lower() == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
