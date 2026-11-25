<!--
  This file is the single source of truth for AI coding agents working on this project.
  It is authoritative for all directories beneath the project root unless overridden
  by a deeper AGENTS.md.

  Behavioral guidelines to reduce common LLM coding mistakes.

  **Tradeoff:** These guidelines bias toward caution over speed. For trivial tasks,
  use your own judgment.
-->

# Project Overview

`browsing_agent` adalah agen browsing web yang aman, modular, dan legal-compliant
untuk menjawab pertanyaan umum pengguna dengan informasi dari web, lengkap dengan
citations. Agen memakai pencarian web pluggable (DuckDuckGo / self-hosted SearXNG),
fetch HTTP-first (fallback Selenium), dan LLM via **ModelHub (utama)** dengan fallback
Azure OpenAI. Dikemas sebagai CLI, API FastAPI ter-autentikasi, dan frontend statis
di belakang Nginx (Docker Compose). Setiap run di-trace ke MLflow GenAI tracing.

Bahasa utama untuk komentar, docstring, dan dokumentasi adalah **Bahasa Indonesia**.

# Technology Stack

- **Python**: 3.14+ (manajemen dependency: `uv`)
- **LLM Framework**: LangChain 1.x (`langchain`, `langchain-openai`)
- **LLM Provider**: ModelHub (`ChatOpenAI` custom base URL) — **utama**; Azure OpenAI hanya fallback
- **Web Search**: pluggable — `ddgs` (DuckDuckGo) atau SearXNG JSON API (self-hosted), dengan fallback antar provider
- **HTTP Fetch**: `httpx` (primary) + Selenium headless Chrome (fallback, `webdriver-manager`)
- **Content Extraction**: `trafilatura` (primary) / `beautifulsoup4` + `lxml` (fallback)
- **API**: FastAPI + Nginx ingress (API key injection untuk UI)
- **Rate Limit**: Redis (per API key, fixed window, fail-open)
- **Tracing**: MLflow GenAI (`mlflow.langchain.autolog`)
- **Environment**: `python-dotenv`
- **Testing**: `pytest`
- **Quality**: `ruff` (lint + format, line-length 100) dan `mypy` (pydantic plugin)

# Project Structure

```
browsing_agent/
├── main.py                      # CLI entry point: LLM, tracing, system prompt, agent loop
├── api.py                       # FastAPI app factory: auth bearer, rate limit, concurrency cap
├── config.py                    # Load .env, defaults, fail-fast helpers
├── agent/planner.py             # Per-run state (ContextVar): tool limits, evidence, blocked domains
├── tools/
│   ├── search.py                # Search pluggable (DDG/SearXNG) + fallback + atribut span MLflow
│   ├── fetch.py                 # HTTP-first fetcher + Selenium fallback, rate limit, robots
│   └── extract.py               # Ekstraksi konten trafilatura/BS4, Pydantic models
├── policy/
│   ├── guardrails.py            # Blokir query & URL (keyword/domain filter)
│   ├── robots.py                # robots.txt checker (TTL cache, ROBOTS_FAIL_OPEN, 404=allow)
│   ├── rate_limit.py            # Rate limit per domain outbound (time.sleep)
│   └── inbound_rate_limit.py    # Rate limit per API key via Redis (fail-open)
├── storage/evidence.py          # EvidenceStore: dedup URL & content hash, citations
├── frontend/                    # UI statis (tanpa API key; Nginx menyuntik key)
├── nginx/                       # Template Nginx (resolver dinamik, /ui-api/ rewrite)
├── searxng/settings.yml         # Konfigurasi SearXNG (JSON format)
├── tests/                       # pytest (unit + integration nginx)
├── docs/
│   ├── adr/                     # ADR-0001..0005 (state, fetch, nginx key, robots, rate limit)
│   ├── PRD.md
│   └── plan_upgrade.md          # Roadmap ADLC
├── .github/workflows/ci.yml     # CI: ruff + mypy + pytest + docker build
├── compose.yaml                 # api, searxng, redis, nginx
├── pyproject.toml               # Deps + config ruff/mypy/pytest
└── .env / .env.example          # Kredensial & settings (jangan commit .env)
```

# Build and Run Commands

```bash
# Instalasi
uv sync

# Menjalankan agen (CLI)
uv run python main.py "pertanyaan Anda"
uv run python main.py                # mode interaktif
uv run python main.py "..." --verbose

# Full stack (API + UI + SearXNG + Redis + Nginx) di http://localhost:8080
docker compose up -d --build

# Menjalankan tests
uv run python -m pytest tests/
```

# Code Style Guidelines

- **Bahasa**: Komentar, docstring, dan string UI pakai Bahasa Indonesia.
- **Penamaan**: `snake_case` untuk fungsi dan variabel.
- **Tools**: Didekorasi `@tool` LangChain; deskripsi jelas untuk LLM.
- **Error handling**: `try/except` sederhana; UX via `print` ke stdout, log operasional via `oplog.log_event` (JSON lines ke stderr).
- **Konfigurasi**: `config.py` hanya membaca dan memvalidasi `.env` (fail-fast, tanpa default hardcoded); semua parameter operasional wajib di `.env` (`.env.example` adalah template kanonik); tidak ada magic numbers di modul lain.
- **Import grouping**: stdlib → pihak ketiga → modul lokal; ruff (`I`) menegakkan urutan ini.
- **Quality gate** (wajib hijau sebelum commit):
  ```bash
  uv run --no-sync ruff check . && uv run --no-sync ruff format --check . \
    && uv run --no-sync mypy . && uv run --no-sync python -m pytest tests/ -q
  ```

# Testing Instructions

```bash
uv run python -m pytest tests/
```

- `tests/conftest.py` menonaktifkan async trace queue MLflow agar exit pytest cepat, dan mengisi nilai test untuk variabel wajib (config tanpa default; .env lokal menang).
- `tests/test_api.py` — kontrak API (auth, error envelope, rate limit 429, concurrency 429, panjang pertanyaan) tanpa LLM/network.
- `tests/test_inbound_rate_limit.py` — limiter Redis dengan fake client (fail-open, hashing, window).
- `tests/test_search_provider.py` — seleksi provider, fallback, atribut span MLflow.
- `tests/test_robots.py` — allow/disallow, fail-open & fail-closed, 404=allow (RFC 9309).
- `tests/integration/test_nginx_config.py` — kontrak ingress Nginx (smoke via Docker bila tersedia).
- Test lain: evidence dedup, extraction, tool limits, rate limit outbound, config, tracing, LLM.

# Security Considerations

- **Kredensial**: Hanya di `.env` (gitignored). Jangan pernah commit/print nilai key.
- **UI key**: Frontend tidak menyimpan key; Nginx menyuntik `UI_API_KEY` (ADR-0003).
- **Tool call limiting**: Per-run state ContextVar, di-reset tiap query (ADR-0001).
- **robots.txt**: Dicek sebelum fetch; kebijakan fail-open/closed via `ROBOTS_FAIL_OPEN` (ADR-0004).
- **Rate limiting**: Outbound per-domain delay; inbound per-API-key via Redis, fail-open (ADR-0005).
- **Input validation**: Guardrails + panjang pertanyaan (`MAX_QUESTION_LENGTH`).
- **Safe crawling policy**: Tidak ada proxy rotation, fingerprint spoofing, CAPTCHA/paywall bypass. Dilarang keras.
- **Browser isolation**: Selenium headless via `ChromeDriverManager`.

# Environment Variables

Salin dari `.env.example` (template kanonik — `config.py` tanpa default; variabel wajib
yang hilang memfail-fast startup). Kredensial wajib: `MODELHUB_API_KEY` (atau kredensial
Azure untuk fallback) dan `API_ALLOWED_KEYS` + `UI_API_KEY`. Nilai referensi variabel
operasional ada di `.env.example` — ringkasan:

| Variable | Default | Keterangan |
|----------|---------|------------|
| `MODELHUB_API_KEY` / `MODELHUB_BASE_URL` / `MODELHUB_MODEL_NAME` | — / ModelHub / `gpt-4o-mini` | Provider LLM utama |
| `AZURE_OPENAI_*` | — | Fallback (opsional) |
| `LLM_TEMPERATURE` / `LLM_MAX_TOKENS` / `LLM_TIMEOUT` / `LLM_MAX_RETRIES` | `0.7` / `1500` / `60` / `2` | Parameter inferensi LLM |
| `API_ALLOWED_KEYS`, `UI_API_KEY` | — | Auth API & UI |
| `SEARCH_PROVIDER` | `duckduckgo` | `duckduckgo` \| `searxng` |
| `SEARXNG_BASE_URL` | `http://searxng:8080` (Compose) | JSON API SearXNG |
| `SEARCH_FALLBACK_ENABLED` | `true` | Fallback antar provider |
| `MLFLOW_TRACING_ENABLED` / `MLFLOW_TRACKING_URI` / `MLFLOW_EXPERIMENT_NAME` | `true` / — / `browsing-agent-dev` | GenAI tracing |
| `MLFLOW_HTTP_TIMEOUT` / `MLFLOW_PREFLIGHT_TIMEOUT` | `5` / `2.0` | Timeout REST MLflow & pre-flight TCP (detik) |
| `RATE_LIMIT_REDIS_URL` | `redis://redis:6379/0` (Compose) | Kosong = nonaktif |
| `RATE_LIMIT_REQUESTS_PER_MINUTE` | `10` | Per API key per menit |
| `RATE_LIMIT_REDIS_TIMEOUT` / `RATE_LIMIT_WINDOW_SECONDS` | `1.0` / `60` | Timeout socket Redis & window (detik) |
| `MAX_CONCURRENT_AGENT_RUNS` | `4` | Konkurensi agent; sisanya 429 |
| `MAX_QUESTION_LENGTH` | `2000` | Panjang pertanyaan maks |
| `ROBOTS_FAIL_OPEN` | `true` | robots.txt gagal (non-404): izinkan/tolak |
| `ROBOTS_CACHE_TTL_SECONDS` | `3600` | TTL cache robots.txt (detik) |
| `MAX_TOOL_CALLS` / `MAX_URLS_PER_QUERY` / `MAX_SEARCH_RESULTS` | `5` / `3` / `5` | Tool limits |
| `REQUEST_TIMEOUT` / `BROWSER_FALLBACK_ENABLED` | `30` / `true` | Fetching |
| `FETCH_MAX_RETRIES` / `BROWSER_WAIT_TIMEOUT` / `FETCH_MAX_CONTENT_CHARS` | `3` / `10` / `3000` | Retry fetch, wait Selenium, truncation konten |
| `USER_AGENT` / `RATE_LIMIT_PER_DOMAIN_SECONDS` | `BrowsingAgent/0.1` / `1.0` | Safe crawling |
| `CHUNK_SIZE` | `2000` | Ukuran chunk konten |

# Architecture Decision Records

Keputusan arsitektur signifikan didokumentasi di `docs/adr/`:

- ADR-0001 — per-run state berbasis ContextVar
- ADR-0002 — HTTP-first fetch dengan fallback Selenium
- ADR-0003 — Nginx menyuntik UI API key (tidak pernah ke browser)
- ADR-0004 — kebijakan fail-open/closed robots.txt
- ADR-0005 — rate limit API per key via Redis (fail-open)

# Release Process

1. Pastikan quality gate hijau dan `CHANGELOG.md` sudah mencantumkan perubahan rilis.
2. Bump `version` di `pyproject.toml` (semver), lalu jalankan `uv lock` agar `uv.lock`
   mencatat versi baru (tanpa ini, `uv sync --locked` di Docker build CI akan gagal).
3. Merge `development` → `main`.
4. Tag annotated di `main`: `git tag -a vX.Y.Z -m "..." && git push origin vX.Y.Z`.

Hook lokal (opsional tapi disarankan): `uv run pre-commit install` — menjalankan
ruff check/format + hygiene check pada setiap commit.

# Upgrade Roadmap

Status dan rencana ada di `docs/plan_upgrade.md`. Fase 1–11 (MVP modular) selesai;
ADLC M1 (config robustness, ruff+mypy, CI), M2 (rate limit Redis, robots policy,
docs/ADR, nginx resolver), M3 (coverage/E2E, frontend CI, deps cleanup, structured
logging), dan M4 (release hygiene) selesai. Lanjutan: runbook, GitLab CI, backlog.
