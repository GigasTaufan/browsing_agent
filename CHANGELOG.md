# Changelog

Semua perubahan signifikan pada proyek ini didokumentasikan di file ini.
Format mengikuti [Keep a Changelog](https://keepachangelog.com/id/1.1.0/),
dan proyek mengikuti [Semantic Versioning](https://semver.org/).

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
