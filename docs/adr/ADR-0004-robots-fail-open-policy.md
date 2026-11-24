# ADR-0004: Kebijakan fail-open/fail-closed robots.txt (ROBOTS_FAIL_OPEN)

**Status:** Accepted

## Context

Saat robots.txt tidak bisa di-fetch (timeout, 5xx, DNS), agen harus memilih: izinkan
(fail-open) atau tolak (fail-closed). Fail-open menjaga pengalaman pengguna tapi
berisiko melanggar preferensi crawler situs; fail-closed paling hormat tapi satu
situs yang error bisa memblokir seluruh penelusuran. RFC 9309: 404 (robots.txt tidak
ada) berarti semua boleh — ini bukan "error".

## Decision

Perilaku dikendalikan `ROBOTS_FAIL_OPEN` (default `true`):

- 404 → selalu diizinkan (RFC 9309), terlepas dari mode.
- Error lain (timeout, 5xx, DNS) → `true`: izinkan; `false`: tolak.
- Error parsing `can_fetch` → ikut nilai `ROBOTS_FAIL_OPEN`.

## Consequences

- Default tetap fail-open: agen tidak lumpuh saat jaringan bermasalah.
- Operator intranet/regulated bisa set `false` untuk kepatuhan maksimal, dengan risiko coverage.
- Kedua mode di-unit-test di `tests/test_robots.py`.
