"""
Rate limit inbound per API key, dibackend Redis (fixed-window per menit).
Fail-open: jika Redis tidak terjangkau, request diizinkan.
Identitas key di-hash (SHA-256) agar API key mentah tidak pernah disimpan di Redis.
"""

import hashlib
import time
from typing import Protocol

import config
import oplog


class RateLimiterProtocol(Protocol):
    """Interface rate limiter yang dipakai API (memudahkan stub di test)."""

    async def check(self, api_key: str) -> bool: ...

    async def aclose(self) -> None: ...


class RedisRateLimiter:
    """
    Fixed-window rate limiter per key.

    Bucket Redis: "ratelimit:{sha256(key)[:16]}:{window_index}".
    INCR + EXPIRE (hanya saat bucket baru) — cukup atomik untuk fixed window.
    """

    def __init__(self, client, limit: int, window_seconds: int = 60):
        self._client = client
        self._limit = limit
        self._window_seconds = window_seconds

    async def check(self, api_key: str) -> bool:
        """
        Return True jika request diizinkan.
        Fail-open: error Redis apa pun diizinkan (dengan log).
        """
        digest = hashlib.sha256(api_key.encode("utf-8")).hexdigest()[:16]
        window_index = int(time.time()) // self._window_seconds
        bucket = f"ratelimit:{digest}:{window_index}"

        try:
            count = await self._client.incr(bucket)
            if count == 1:
                await self._client.expire(bucket, self._window_seconds * 2)
        except Exception as e:
            oplog.log_event("rate_limit.redis_error", error=str(e), fail_open=True)
            return True

        return count <= self._limit

    async def aclose(self) -> None:
        """Tutup koneksi Redis (dipanggil saat app shutdown)."""
        try:
            await self._client.aclose()
        except Exception:
            pass


def build_rate_limiter():
    """
    Bangun RedisRateLimiter dari config; return None jika dinonaktifkan.
    Timeout socket pendek agar fail-open cepat saat Redis down.
    """
    if not config.RATE_LIMIT_REDIS_URL:
        return None

    from redis.asyncio import Redis

    client = Redis.from_url(
        config.RATE_LIMIT_REDIS_URL,
        socket_timeout=1,
        socket_connect_timeout=1,
    )
    return RedisRateLimiter(client, limit=config.RATE_LIMIT_REQUESTS_PER_MINUTE)
