"""
╔════════════════════════════════════════════════════════════════════╗
║  PEPPER CLINICAL V6 — Security: JWT · Hashing · Encryption        ║
╚════════════════════════════════════════════════════════════════════╝
"""
import time
import hmac
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any

from jose import jwt, JWTError
import bcrypt
from cryptography.fernet import Fernet
import base64

from app.core.config import settings


# ── Password / PIN hashing (direct bcrypt — no passlib version conflict) ──
def hash_secret(plain: str) -> str:
    """Hash a password or PIN with bcrypt. Truncated to 72 bytes (bcrypt limit)."""
    pw = plain.encode("utf-8")[:72]
    salt = bcrypt.gensalt(rounds=settings.BCRYPT_ROUNDS)
    return bcrypt.hashpw(pw, salt).decode("utf-8")


def verify_secret(plain: str, hashed: str) -> bool:
    """Verify a password or PIN against its bcrypt hash."""
    try:
        pw = plain.encode("utf-8")[:72]
        return bcrypt.checkpw(pw, hashed.encode("utf-8"))
    except Exception:
        return False


# ── PIN generation ────────────────────────────────────────────────────
def generate_pin(length: int = None) -> str:
    """Cryptographically secure numeric PIN."""
    length = length or settings.PIN_LENGTH
    return "".join(secrets.choice("0123456789") for _ in range(length))


# ── JWT tokens ────────────────────────────────────────────────────────
def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire, "type": "access", "iat": datetime.now(timezone.utc)})
    return jwt.encode(to_encode, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(data: Dict[str, Any]) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh", "iat": datetime.now(timezone.utc)})
    return jwt.encode(to_encode, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> Optional[Dict[str, Any]]:
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        return payload
    except JWTError:
        return None


# ── Field-level encryption (data at rest) ─────────────────────────────
def _get_fernet() -> Fernet:
    # Derive a 32-byte urlsafe key from the configured encryption key
    raw = hashlib.sha256(settings.ENCRYPTION_KEY.encode()).digest()
    key = base64.urlsafe_b64encode(raw)
    return Fernet(key)


def encrypt_field(plaintext: str) -> str:
    if not plaintext:
        return ""
    return _get_fernet().encrypt(plaintext.encode()).decode()


def decrypt_field(ciphertext: str) -> str:
    if not ciphertext:
        return ""
    try:
        return _get_fernet().decrypt(ciphertext.encode()).decode()
    except Exception:
        return ""


# ── Rate limiting / brute-force protection (in-memory) ────────────────
class RateLimiter:
    def __init__(self):
        self._hits: Dict[str, list] = {}
        self._lockouts: Dict[str, float] = {}

    def is_locked(self, key: str) -> bool:
        until = self._lockouts.get(key)
        if until and time.time() < until:
            return True
        if until:
            self._lockouts.pop(key, None)
        return False

    def record_attempt(self, key: str, max_attempts: int, window: int, lockout: int) -> bool:
        """Returns True if allowed, False if rate-limited."""
        now = time.time()
        if self.is_locked(key):
            return False
        hits = [t for t in self._hits.get(key, []) if now - t < window]
        hits.append(now)
        self._hits[key] = hits
        if len(hits) > max_attempts:
            self._lockouts[key] = now + lockout
            return False
        return True

    def reset(self, key: str):
        self._hits.pop(key, None)
        self._lockouts.pop(key, None)


rate_limiter = RateLimiter()


# ── Integrity fingerprint (anti-tamper) ───────────────────────────────
def sign_payload(payload: str) -> str:
    return hmac.new(settings.SECRET_KEY.encode(), payload.encode(), hashlib.sha256).hexdigest()


def verify_signature(payload: str, signature: str) -> bool:
    expected = sign_payload(payload)
    return hmac.compare_digest(expected, signature)
