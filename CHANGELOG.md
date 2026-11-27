# Changelog

Semua perubahan signifikan pada proyek ini didokumentasikan di file ini.
Format mengikuti [Keep a Changelog](https://keepachangelog.com/id/1.1.0/),
dan proyek mengikuti [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- Validasi startup `config.py`: `API_ALLOWED_KEYS` & `UI_API_KEY` wajib dan `UI_API_KEY` harus tercantum di `API_ALLOWED_KEYS`; minimal satu provider LLM (ModelHub lengkap atau Azure lengkap) wajib terkonfigurasi (ADR-0002, ADR-0003).
- Blokir URL internal/privat (SSRF): hostname tanpa titik, `localhost`, IP privat/loopback/link-local/reserved (termasuk bentuk desimal, hex, IPv4-mapped IPv6), dan hostname yang gagal di-resolve (ADR-0008).
- ADR-0006 (rate limit fail-closed), ADR-0007 (cakupan guardrails), ADR-0008 (SSRF).
- Profil Compose `prod`/`staging`; staging berjalan dengan `NGINX_PORT=8081` pada host yang sama.
- Coverage gate `--cov-fail-under=83` di CI GitHub Actions & GitLab CI.

### Changed

- **BREAKING**: rate limit inbound kini fail-closed (ADR-0006) — Redis tidak terjangkau membuat `POST /api/v1/ask` membalas HTTP 503 `dependency_unavailable`; limiter mengembalikan `RateLimitDecision`, bukan `bool`.
- **BREAKING (perilaku)**: guardrails mengikuti PRD (ADR-0007) — pertanyaan umum yang memuat "password"/"login" tidak lagi diblokir; domain sensitif dicocokkan per label dan entri duplikat/`bank` dihapus.
- `SEARCH_PROVIDER` kini divalidasi di `config.py` (fail-fast saat startup, bukan saat tool dipanggil).

### Removed

- Pemeriksaan kelengkapan ModelHub/Azure di `main.load_llm` (dipindah ke `config.py`).

## [1.2.0] - 2026-11-25

### Added

- Parameter operasional baru di `.env` (menggantikan nilai hardcoded): `LLM_TEMPERATURE`, `LLM_MAX_TOKENS`, `LLM_TIMEOUT`, `LLM_MAX_RETRIES`, `MLFLOW_HTTP_TIMEOUT`, `MLFLOW_PREFLIGHT_TIMEOUT`, `FETCH_MAX_RETRIES`, `BROWSER_WAIT_TIMEOUT`, `FETCH_MAX_CONTENT_CHARS`, `ROBOTS_CACHE_TTL_SECONDS`, `RATE_LIMIT_REDIS_TIMEOUT`, `RATE_LIMIT_WINDOW_SECONDS`.

### Changed

- **BREAKING**: `config.py` kini strict reader/validator tanpa default hardcoded — semua parameter operasional wajib di `.env` (salin dari `.env.example`); yang hilang memfail-fast startup dengan pesan error. Grup MLflow hanya wajib jika tracing aktif.
- `--version` CLI kini dibaca dari `pyproject.toml` (via `tomllib`), tidak lagi hardcoded.
- PRD dan deskripsi `pyproject.toml` di-refresh sesuai stack ModelHub-primary.

### Removed

- Spec pra-ADLC `docs/superpowers/` (tidak lagi direferensikan).
- Smoke script ModelHub dipindah ke `scripts/modelhub.py` (path README diperbarui).

## [1.1.0] - 2026-11-24

### Added

- CI GitHub Actions: ruff, mypy, pytest+coverage, build image Docker, audit dependency (pip-audit, non-blocking).
- Tracing MLflow GenAI untuk setiap run agent (span atribut `search.provider` / `search.fallback_used`).
- Pencarian web pluggable: DuckDuckGo atau SearXNG self-hosted (`SEARCH_PROVIDER`) dengan fallback antar provider.
- Rate limit API per key via Redis (fixed window, fail-open, key di-hash) + service `redis` di Compose.
- Cap konkurensi agent (`MAX_CONCURRENT_AGENT_RUNS`, 429) dan panjang pertanyaan (`MAX_QUESTION_LENGTH`, 422).
- Kebijakan robots.txt fail-open/fail-closed (`ROBOTS_FAIL_OPEN`); 404 selalu diizinkan (RFC 9309).
- Log operasional terstruktur `oplog.log_event` (JSON lines ke stderr) untuk lifecycle API dan error Redis.
- Test E2E agent loop (LLM scripted), contract test frontend, dan coverage config (83%).
- ADR-0001..0005 (ContextVar state, HTTP-first fetch, Nginx key injection, robots policy, rate limit).

### Changed

- Provider LLM utama menjadi ModelHub; Azure OpenAI hanya fallback.
- `config.py` memiliki default untuk semua variabel operasional + fail-fast untuk kredensial wajib.
- System prompt date-aware: jawaban di-grounding pada evidence tool, bukan knowledge cutoff LLM.
- AGENTS.md ditulis ulang sesuai arsitektur terkini.

### Fixed

- Nginx 502 stale-IP setelah rebuild container api (resolver Docker DNS + upstream variabel).
- Image Docker kini menyertakan `oplog.py`.

## [1.0.0]

- Rilis awal: agen browsing modular (search DDG, fetch HTTP-first + Selenium fallback, extract, evidence, citations), CLI, API FastAPI, frontend statis di belakang Nginx, Docker Compose.
