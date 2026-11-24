# ADR-0005: Rate limit API per key via Redis (fixed window, fail-open)

**Status:** Accepted

## Context

API publik (via Nginx) butuh perlindungan abuse per caller. Rate limiter in-process
tidak berlaku lintas instance dan hilang saat restart. Namun Redis adalah dependency
operasional baru: jika Redis down, API tidak boleh menjadi total down.

## Decision

Rate limit inbound diimplementasi di `policy/inbound_rate_limit.py`:

- Fixed window per menit, bucket Redis `ratelimit:{sha256(key)[:16]}:{window_index}`,
  via `INCR` + `EXPIRE` (expire hanya saat bucket baru).
- API key tidak pernah disimpan mentah di Redis — hanya digest SHA-256.
- **Fail-open**: error Redis apa pun → request diizinkan (dengan log). Socket timeout
  1s agar fail-open cepat.
- Nonaktif jika `RATE_LIMIT_REDIS_URL` kosong.
- Ditambah: cap konkurensi agent (`MAX_CONCURRENT_AGENT_RUNS`, semaphore) dan cap
  panjang pertanyaan (`MAX_QUESTION_LENGTH`) — keduanya 429/422 eksplisit.

## Consequences

- Perlindungan abuse tersedia di compose (service `redis`), tanpa single point of failure.
- Fixed window memungkinkan burst 2x di batas window — acceptable untuk use case ini.
- Unit test memakai stub/fake Redis; integration live via compose.