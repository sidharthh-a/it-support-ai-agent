"""Production hardening middleware.

- RequestIDMiddleware: assigns an X-Request-ID to every request and response,
  binds it to the logging context.
- SecurityHeadersMiddleware: OWASP-recommended security headers.
- RateLimitMiddleware: lightweight fixed-window per-IP limiter for API routes
  (in-memory; swap for Redis in multi-instance deployments).
"""
import time
import uuid
from collections import defaultdict, deque
from typing import Deque, Dict, Optional, Tuple

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.config import settings
from app.core.logging import logger


class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:16]
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        if settings.ENVIRONMENT.lower() in ("production", "prod"):
            response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Fixed-window per-IP rate limiting for API endpoints.

    Health endpoints and docs are exempt. Limits apply per client IP with a
    sliding window of `window_seconds`; default 120 requests/minute.
    """

    EXEMPT_PATHS = {"/api/v1/health", "/api/v1/live", "/api/v1/ready", "/docs", "/openapi.json", "/redoc", "/"}

    def __init__(self, app, requests_per_minute: Optional[int] = None, window_seconds: int = 60):
        super().__init__(app)
        self.window = window_seconds
        self.limit = requests_per_minute or getattr(settings, "RATE_LIMIT_PER_MINUTE", 120)
        self._hits: Dict[str, Deque[float]] = defaultdict(deque)

    def _client_key(self, request: Request) -> str:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if path in self.EXEMPT_PATHS or settings.ENVIRONMENT.lower() == "test":
            return await call_next(request)

        key = self._client_key(request)
        now = time.monotonic()
        window_start = now - self.window
        hits = self._hits[key]
        while hits and hits[0] < window_start:
            hits.popleft()
        if len(hits) >= self.limit:
            logger.warning("Rate limit exceeded for %s on %s", key, path)
            return Response(
                content='{"detail": "Rate limit exceeded. Try again later."}',
                status_code=429,
                media_type="application/json",
                headers={"Retry-After": str(self.window)},
            )
        hits.append(now)
        return await call_next(request)
