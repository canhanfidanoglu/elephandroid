"""Application middleware: rate limiting, request logging."""

import logging
import time
from collections import defaultdict

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from src.config import settings

logger = logging.getLogger(__name__)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Simple in-memory sliding window rate limiter per IP.

    Not suitable for multi-process deployments — use Redis-based
    rate limiting (e.g. slowapi) in that case.
    """

    def __init__(self, app, rpm: int = 120):
        super().__init__(app)
        self.rpm = rpm
        self.window = 60.0  # 1 minute window
        self._hits: dict[str, list[float]] = defaultdict(list)

    def _client_ip(self, request: Request) -> str:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    def _is_limited(self, ip: str) -> bool:
        now = time.monotonic()
        timestamps = self._hits[ip]
        # Evict old entries
        cutoff = now - self.window
        self._hits[ip] = [t for t in timestamps if t > cutoff]
        if len(self._hits[ip]) >= self.rpm:
            return True
        self._hits[ip].append(now)
        return False

    async def dispatch(self, request: Request, call_next):
        # Skip rate limiting for static/health endpoints
        if request.url.path in ("/", "/docs", "/openapi.json", "/ai/health"):
            return await call_next(request)

        ip = self._client_ip(request)
        if self._is_limited(ip):
            logger.warning("Rate limit exceeded for %s on %s", ip, request.url.path)
            return Response(
                content='{"detail":"Rate limit exceeded. Try again later."}',
                status_code=429,
                media_type="application/json",
                headers={"Retry-After": "60"},
            )
        return await call_next(request)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log request method, path, status, and duration."""

    async def dispatch(self, request: Request, call_next):
        start = time.monotonic()
        response = await call_next(request)
        duration_ms = (time.monotonic() - start) * 1000

        # Skip noisy endpoints
        if request.url.path not in ("/ai/health", "/docs", "/openapi.json"):
            logger.info(
                "%s %s → %d (%.0fms)",
                request.method,
                request.url.path,
                response.status_code,
                duration_ms,
            )
        return response
