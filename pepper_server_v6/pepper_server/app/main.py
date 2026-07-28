"""
╔════════════════════════════════════════════════════════════════════╗
║  PEPPER CLINICAL INFINITY V6 — Main FastAPI Application           ║
║  © 2026 Lamya Fadlulmola Hamed Ali — All Rights Reserved          ║
║  Production-grade · Secure · Server-ready                         ║
╚════════════════════════════════════════════════════════════════════╝
"""
import time
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import settings
from app.core.database import init_db
from app.core.security import rate_limiter
from app.api import auth, children, sessions

# ── Logging ───────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO if settings.is_production else logging.DEBUG,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    handlers=[logging.FileHandler("logs/pepper.log"), logging.StreamHandler()],
)
logger = logging.getLogger("pepper")


# ── Lifespan ──────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Pepper Clinical Infinity V6...")
    init_db()
    logger.info("Database initialized.")
    yield
    logger.info("Shutting down Pepper Clinical V6.")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="AI-powered autism therapy platform — secure backend API.",
    docs_url="/docs" if not settings.is_production else None,
    redoc_url=None,
    openapi_url="/openapi.json" if not settings.is_production else None,
    lifespan=lifespan,
)


# ── Security headers middleware ───────────────────────────────────────
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(self), microphone=(), geolocation=()"
        if settings.is_production:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; img-src 'self' data: https:; "
            "style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; "
            "connect-src 'self' https:; frame-src https://www.youtube.com;"
        )
        return response


# ── Global rate limiting middleware ───────────────────────────────────
class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path.startswith("/api/"):
            ip = request.headers.get("x-forwarded-for", "")
            ip = ip.split(",")[0].strip() if ip else (request.client.host if request.client else "unknown")
            key = f"global:{ip}"
            if not rate_limiter.record_attempt(key, settings.RATE_LIMIT_PER_MINUTE, 60, 60):
                return JSONResponse(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    content={"detail": "Rate limit exceeded. Please slow down."},
                )
        return await call_next(request)


# ── Request timing / logging ──────────────────────────────────────────
class TimingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start = time.perf_counter()
        response = await call_next(request)
        elapsed = (time.perf_counter() - start) * 1000
        response.headers["X-Process-Time-ms"] = f"{elapsed:.1f}"
        return response


# ── Register middleware (order matters: last added = outermost) ───────
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(TimingMiddleware)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(GZipMiddleware, minimum_size=1000)

if settings.hosts_list != ["*"]:
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.hosts_list)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    max_age=600,
)


# ── Exception handler ─────────────────────────────────────────────────
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled error on {request.url.path}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error" if settings.is_production else str(exc)},
    )


# ── Routers ───────────────────────────────────────────────────────────
app.include_router(auth.router)
app.include_router(children.router)
app.include_router(sessions.router)


# ── Health + root ─────────────────────────────────────────────────────
@app.get("/health", tags=["System"])
def health():
    return {"status": "healthy", "version": settings.APP_VERSION}


@app.get("/", tags=["System"])
def root():
    return {
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "running",
        "docs": "/docs" if not settings.is_production else "disabled in production",
    }


# ── Serve frontend (static) ───────────────────────────────────────────
import os
if os.path.isdir("app/static"):
    app.mount("/app", StaticFiles(directory="app/static", html=True), name="static")
