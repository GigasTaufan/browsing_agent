# ADR-0010: Observability minimal tanpa dependency baru

**Status:** Accepted

## Context

Deployment satu host Compose (intranet), tanpa Prometheus/Grafana. Yang dibutuhkan:
menjawab "berapa request, berapa gagal, berapa lama" tanpa menambah service.

## Decision

- `oplog` mencatat satu event JSON per request final (`api.request`) berisi `status`,
  `duration_ms`, dan `key_hash`; semua kegagalan disimpan di `app.state` dengan alasan
  terpisah agar dapat dibaca tanpa log (401 tidak dibedakan per-alasan).
- `/metrics` menyajikan format eksposisi Prometheus yang hand-written: counter
  `browsing_agent_requests_total{outcome}` dan `browsing_agent_request_duration_seconds`
  (ringkasan `count`/`sum`/`max`). Endpoint publik (tanpa auth) seperti `/healthz`.

## Consequences

- Tanpa dependency; format cukup untuk `curl`/scrape sederhana. Tidak ada histogram
  bucket (cukup min/max/avg) — upgrade ke `prometheus_client` bila butuh persentil.
- Metrik in-process: hilang saat restart (cukup untuk intranet satu host).
