"""In-process per-client-IP token-bucket rate limiting for the public API."""

import json
import math
import os
import time
from collections.abc import Awaitable, Callable, Mapping

RATE_LIMIT_ENV = "JMA_RATE_LIMIT_PER_MINUTE"
DEFAULT_RATE_LIMIT_PER_MINUTE = 120
_BUCKET_CAPACITY = 10_000
_STALE_SECONDS = 300.0


def configured_rate_limit(
    environment: Mapping[str, str] | None = None,
) -> int | None:
    """Resolve the limit; explicit ``0`` disables it for local operation."""

    source = os.environ if environment is None else environment
    raw = source.get(RATE_LIMIT_ENV, "").strip()
    if not raw:
        return DEFAULT_RATE_LIMIT_PER_MINUTE
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{RATE_LIMIT_ENV} must be a non-negative integer") from exc
    if value < 0:
        raise ValueError(f"{RATE_LIMIT_ENV} must be a non-negative integer")
    return value or None


class _Bucket:
    __slots__ = ("tokens", "refilled_at")

    def __init__(self, tokens: float, refilled_at: float) -> None:
        self.tokens = tokens
        self.refilled_at = refilled_at


class RateLimitMiddleware:
    """Pure ASGI token-bucket limiter keyed by client IP.

    The API always runs behind a trusted local reverse proxy in production,
    so ``X-Forwarded-For`` is honored when present; direct local development
    falls back to the socket peer address. One process-wide bucket store is
    safe because ASGI middleware dispatch runs on a single event loop.
    """

    def __init__(
        self,
        app: object,
        *,
        requests_per_minute: int,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.app = app
        self.capacity = float(requests_per_minute)
        self.refill_per_second = requests_per_minute / 60.0
        self.clock = clock
        self._buckets: dict[str, _Bucket] = {}

    def take_token(self, client_ip: str) -> tuple[bool, int]:
        """Consume one token; return ``(allowed, retry_after_seconds)``."""

        now = self.clock()
        bucket = self._buckets.get(client_ip)
        if bucket is None:
            if len(self._buckets) >= _BUCKET_CAPACITY:
                self._prune(now)
            bucket = _Bucket(self.capacity - 1.0, now)
            self._buckets[client_ip] = bucket
            return True, 0

        bucket.tokens = min(
            self.capacity,
            bucket.tokens + (now - bucket.refilled_at) * self.refill_per_second,
        )
        bucket.refilled_at = now
        if bucket.tokens >= 1.0:
            bucket.tokens -= 1.0
            return True, 0
        retry_after = math.ceil((1.0 - bucket.tokens) / self.refill_per_second)
        return False, max(retry_after, 1)

    def _prune(self, now: float) -> None:
        stale = [
            ip
            for ip, bucket in self._buckets.items()
            if now - bucket.refilled_at > _STALE_SECONDS
        ]
        for ip in stale:
            del self._buckets[ip]
        if len(self._buckets) >= _BUCKET_CAPACITY and self._buckets:
            # Extreme abuse fallback: drop everything rather than grow.
            self._buckets.clear()

    async def __call__(
        self,
        scope: dict,
        receive: Callable[[], Awaitable[dict]],
        send: Callable[[dict], Awaitable[None]],
    ) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        if path == "/api/health":
            await self.app(scope, receive, send)
            return

        client_ip = _client_ip(scope)
        allowed, retry_after = self.take_token(client_ip)
        if allowed:
            await self.app(scope, receive, send)
            return
        await _send_rate_limited(
            send,
            retry_after,
            request_id=str(scope.get("state", {}).get("request_id", "unknown")),
        )


def _client_ip(scope: dict) -> str:
    forwarded = b""
    for name, value in scope.get("headers", []):
        if name == b"x-forwarded-for":
            forwarded = value
            break
    if forwarded:
        first = forwarded.decode("latin-1").split(",")[0].strip()
        if first:
            return first
    client = scope.get("client")
    if client:
        return str(client[0])
    return "unknown"


async def _send_rate_limited(
    send: Callable[[dict], Awaitable[None]],
    retry_after: int,
    *,
    request_id: str,
) -> None:
    payload = {
        "error": {
            "code": "rate_limited",
            "message": "Too many requests. Slow down and retry shortly.",
        },
        "request_id": str(request_id),
    }
    body = json.dumps(payload).encode("utf-8")
    headers = [
        (b"content-type", b"application/json"),
        (b"cache-control", b"no-store"),
        (b"retry-after", str(retry_after).encode("ascii")),
        (b"x-request-id", str(request_id).encode("ascii")),
    ]
    await send(
        {
            "type": "http.response.start",
            "status": 429,
            "headers": headers,
        }
    )
    await send({"type": "http.response.body", "body": body})
