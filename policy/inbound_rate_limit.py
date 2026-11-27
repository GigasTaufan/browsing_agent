"""
Rate limit inbound per API key, dibackend Redis (fixed-window per menit).
Fail-closed: jika Redis tidak terjangkau, API membalas 503 (ADR-0006).
Identitas key di-hash (SHA-256) agar API key mentah tidak pernah disimpan di Redis.
"""

import hashlib
import time
from enum import Enum
from typing import Protocol

import config
import oplog


class RateLimitDecision(Enum):
    """Keputusan limiter untuk satu request."""

    ALLOWED = "allowed"
    LIMITED = "limited"
    UNAVAILABLE = "unavailable"


class RateLimiterProtocol(Protocol):
    """Interface rate limiter yang dipakai API (memudahkan stub di test)."""

    async def check(self, api_key: str) -> RateLimitDecision: ...

    async def aclose(self) -> None: ...


class RedisRateLimiter:
    """
    Fixed-window rate limiter per key.

    Bucket Redis: "ratelimit:{sha256(key)[:16]}:{window_index}".
    INCR + EXPIRE (hanya saat bucket baru) — cukup atomik untuk fixed window.
    """

    def __init__(self, client, limit: int, window_seconds: int | None = None):
        self._client = client
        self._limit = limit
        self._window_seconds = (
            window_seconds if window_seconds is not None else config.RATE_LIMIT_WINDOW_SECONDS
        )

    async def check(self, api_key: str) -> RateLimitDecision:
        """
        Kembalikan keputusan untuk request ini.
        Fail-closed: error Redis apa pun -> UNAVAILABLE (dengan log).
        """
        digest = hashlib.sha256(api_key.encode("utf-8")).hexdigest()[:16]
        window_index = int(time.time()) // self._window_seconds
        bucket = f"ratelimit:{digest}:{window_index}"

        try:
            count = await self._client.incr(bucket)
            if count == 1:
                await self._client.expire(bucket, self._window_seconds * 2)
        except Exception as e:
            oplog.log_event("rate_limit.redis_error", error=str(e), fail_closed=True)
            return RateLimitDecision.UNAVAILABLE

        return RateLimitDecision.ALLOWED if count <= self._limit else RateLimitDecision.LIMITED

    async def aclose(self) -> None:
        """Tutup koneksi Redis (dipanggil saat app shutdown)."""
        try:
            await self._client.aclose()
        except Exception:
            pass


def build_rate_limiter():
    """
    Bangun RedisRateLimiter dari config; return None jika dinonaktifkan (dev/CLI).
    Timeout socket pendek agar fail-closed cepat saat Redis down.
    """
    if not config.RATE_LIMIT_REDIS_URL:
        return None

    from redis.asyncio import Redis

    client = Redis.from_url(
        config.RATE_LIMIT_REDIS_URL,
        socket_timeout=config.RATE_LIMIT_REDIS_TIMEOUT,
        socket_connect_timeout=config.RATE_LIMIT_REDIS_TIMEOUT,
    )
    return RedisRateLimiter(client, limit=config.RATE_LIMIT_REQUESTS_PER_MINUTE)
