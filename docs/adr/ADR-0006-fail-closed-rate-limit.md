# ADR-0006: Rate limit API fail-closed saat Redis tidak tersedia

**Status:** Accepted (menggantikan ADR-0005)

## Context

ADR-0005 memakai **fail-open**: error Redis apa pun → request diizinkan. Konsekuensinya
adalah rate limit bisa nonaktif tanpa terlihat (cukup Redis mati atau URL kosong), dan UI
publik berbagi satu `UI_API_KEY` sehingga satu caller bisa menghabiskan kuota seluruh UI.

Deployment target saat ini adalah satu host Compose (intranet), bukan cluster, sehingga
perlindungan abuse per caller tetap dibutuhkan tanpa HA Redis.

## Decision

- `RedisRateLimiter.check()` mengembalikan `RateLimitDecision`: `ALLOWED`, `LIMITED`, atau
  `UNAVAILABLE` (Redis error/timeout).
- API memetakan `UNAVAILABLE` → **HTTP 503** `{"error":{"code":"dependency_unavailable"}}`
  dan mencatat `rate_limit.redis_error` di log operasional.
- `LIMITED` → HTTP 429 `rate_limited` (tidak berubah).
- `RATE_LIMIT_REDIS_URL` kosong = limiter nonaktif (hanya dev/CLI). Di Compose URL selalu
  diisi, sehingga mode ini tidak dapat terjadi pada deployment.

## Consequences

- Redis down membuat API menolak `ask` (bukan diam-diam tanpa rate limit). Endpoint
  `/healthz` tetap 200; pemulihan = `docker compose start redis`.
- Burst 2x di batas fixed window tetap mungkin (sama dengan ADR-0005).
- Test lama `test_redis_error_fails_open` diganti menjadi test fail-closed.
