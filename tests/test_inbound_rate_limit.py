"""Unit test policy/inbound_rate_limit.py dengan fake Redis client (tanpa Redis nyata)."""

import asyncio
import sys
from types import SimpleNamespace

import config
from policy.inbound_rate_limit import RateLimitDecision, RedisRateLimiter, build_rate_limiter


class FakeRedis:
    """Fake client async dengan perilaku incr/expire yang bisa diinspeksi."""

    def __init__(self, fail: bool = False):
        self.counts: dict[str, int] = {}
        self.expired: list[tuple[str, int]] = []
        self.fail = fail

    async def incr(self, key: str) -> int:
        if self.fail:
            raise ConnectionError("redis down")
        self.counts[key] = self.counts.get(key, 0) + 1
        return self.counts[key]

    async def expire(self, key: str, ttl: int) -> None:
        self.expired.append((key, ttl))


def test_under_limit_allowed():
    client = FakeRedis()
    limiter = RedisRateLimiter(client, limit=3)

    results = [asyncio.run(limiter.check("key-a")) for _ in range(3)]

    assert results == [RateLimitDecision.ALLOWED] * 3


def test_over_limit_blocked():
    client = FakeRedis()
    limiter = RedisRateLimiter(client, limit=2)

    results = [asyncio.run(limiter.check("key-a")) for _ in range(3)]

    assert results == [
        RateLimitDecision.ALLOWED,
        RateLimitDecision.ALLOWED,
        RateLimitDecision.LIMITED,
    ]


def test_expire_set_only_on_first_request_in_window():
    client = FakeRedis()
    limiter = RedisRateLimiter(client, limit=5)

    asyncio.run(limiter.check("key-a"))
    asyncio.run(limiter.check("key-a"))

    assert len(client.expired) == 1
    assert (
        client.expired[0][1]
        == config.RATE_LIMIT_WINDOW_SECONDS * config.RATE_LIMIT_BUCKET_TTL_FACTOR
    )


def test_redis_error_fails_closed():
    """ADR-0006: Redis error -> UNAVAILABLE (API membalas 503), bukan diizinkan."""
    client = FakeRedis(fail=True)
    limiter = RedisRateLimiter(client, limit=1)

    assert asyncio.run(limiter.check("key-a")) is RateLimitDecision.UNAVAILABLE


def test_keys_are_hashed_not_stored_raw():
    client = FakeRedis()
    limiter = RedisRateLimiter(client, limit=5)

    asyncio.run(limiter.check("secret-api-key"))

    bucket = list(client.counts)[0]
    prefix, digest, _window = bucket.split(":")
    assert prefix == config.RATE_LIMIT_BUCKET_PREFIX
    assert len(digest) == config.RATE_LIMIT_KEY_HASH_CHARS
    assert "secret-api-key" not in bucket


def test_build_rate_limiter_disabled_when_url_unset(monkeypatch):
    monkeypatch.setattr(config, "RATE_LIMIT_REDIS_URL", None)

    assert build_rate_limiter() is None


def test_build_rate_limiter_enabled_when_url_set(monkeypatch):
    monkeypatch.setattr(config, "RATE_LIMIT_REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setattr(config, "RATE_LIMIT_REQUESTS_PER_MINUTE", 7)

    limiter = build_rate_limiter()

    assert isinstance(limiter, RedisRateLimiter)
    assert limiter._limit == 7
    asyncio.run(limiter.aclose())


def test_build_rate_limiter_passes_only_supported_client_options(monkeypatch):
    """Regresi: opsi klien ilegal baru gagal saat koneksi -> semua request 503 (dulu `wait_for_connection`)."""
    captured = {}

    class FakeRedis:
        @staticmethod
        def from_url(url, **kwargs):
            captured.update(kwargs)
            return object()

    monkeypatch.setitem(sys.modules, "redis.asyncio", SimpleNamespace(Redis=FakeRedis))
    monkeypatch.setattr(config, "RATE_LIMIT_REDIS_URL", "redis://localhost:6379/0")

    assert isinstance(build_rate_limiter(), RedisRateLimiter)
    assert captured == {
        "socket_timeout": config.RATE_LIMIT_REDIS_TIMEOUT,
        "socket_connect_timeout": config.RATE_LIMIT_REDIS_TIMEOUT,
    }
