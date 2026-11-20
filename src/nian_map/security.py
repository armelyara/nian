"""Security middleware and guards: headers, rate limiting, optional token."""
from __future__ import annotations

import hmac
import time
from collections import OrderedDict

from fastapi import HTTPException, Request
from starlette.middleware.base import BaseHTTPMiddleware

from .config import settings

# Strict CSP: scripts, styles and fonts are self-hosted (static/vendor), no inline JS.
CSP = "; ".join([
    "default-src 'self'",
    "script-src 'self'",
    "style-src 'self'",
    "img-src 'self' data: https://i.ytimg.com",
    "media-src 'self' https://media.w3.org https://interactive-examples.mdn.mozilla.net",
    "frame-src https://www.youtube-nocookie.com",
    "connect-src 'self'",
    "object-src 'none'",
    "base-uri 'none'",
    "form-action 'self'",
    "frame-ancestors 'none'",
])

SECURITY_HEADERS = {
    "Content-Security-Policy": CSP,
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "geolocation=(), camera=(), microphone=(), payment=()",
    "Cross-Origin-Opener-Policy": "same-origin",
    "X-Frame-Options": "DENY",
}


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        for k, v in SECURITY_HEADERS.items():
            response.headers.setdefault(k, v)
        if request.url.scheme == "https":
            response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        if request.url.path.startswith("/api/"):
            response.headers.setdefault("Cache-Control", "no-store")
        return response


class RateLimiter:
    """Sliding-window limiter keyed by client IP, bounded memory (LRU).
    Per-process only: use Redis or the reverse proxy for multi-instance."""

    def __init__(self, per_minute: int, max_keys: int = 10_000):
        self.per_minute = per_minute
        self.max_keys = max_keys
        self._hits: OrderedDict[str, list[float]] = OrderedDict()

    def check(self, key: str) -> bool:
        now = time.monotonic()
        window = [t for t in self._hits.pop(key, []) if now - t < 60]
        allowed = len(window) < self.per_minute
        if allowed:
            window.append(now)
        self._hits[key] = window
        while len(self._hits) > self.max_keys:
            self._hits.popitem(last=False)
        return allowed


search_limiter = RateLimiter(settings.search_rate_per_minute)


def client_ip(request: Request) -> str:
    # request.client honours X-Forwarded-For only when uvicorn runs with
    # --proxy-headers --forwarded-allow-ips=<proxy>, so it cannot be spoofed.
    return request.client.host if request.client else "unknown"


def require_token(request: Request) -> None:
    """Optional shared-secret gate for costly endpoints (private deployments)."""
    if not settings.api_token:
        return
    supplied = request.headers.get("x-nian-token", "")
    if not hmac.compare_digest(supplied.encode(), settings.api_token.encode()):
        raise HTTPException(status_code=401, detail="Invalid token.")


def limit_search(request: Request) -> None:
    if not search_limiter.check(client_ip(request)):
        raise HTTPException(status_code=429, detail="Too many searches, try again in a minute.",
                            headers={"Retry-After": "60"})
