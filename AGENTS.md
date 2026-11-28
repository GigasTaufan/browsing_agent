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
di belakang Nginx (Docker Compose). Saat MLflow tersedia, satu request agent dicatat sebagai trace root dengan span LangChain turunannya.

Bahasa utama untuk komentar, docstring, dan dokumentasi adalah **Bahasa Indonesia**.

# Technology Stack

- **Python**: 3.14+ (manajemen dependency: `uv`)
- **LLM Framework**: LangChain 1.x (`langchain`, `langchain-openai`)
- **LLM Provider**: ModelHub (`ChatOpenAI` custom base URL) — **utama**; Azure OpenAI hanya fallback
- **Web Search**: pluggable — `ddgs` (DuckDuckGo) atau SearXNG JSON API (self-hosted), dengan fallback antar provider
- **HTTP Fetch**: `httpx` (primary) + Selenium headless Chrome (fallback, `webdriver-manager`)
- **Content Extraction**: `trafilatura` (primary) / `beautifulsoup4` + `lxml` (fallback)
- **API**: FastAPI + Nginx ingress (API key injection untuk UI)
- **Rate Limit**: Redis (per API key, fixed window, fail-closed — Redis down = 503)
- **Tracing**: MLflow GenAI; `mlflow.langchain.autolog` untuk LangGraph/model, ditambah satu span root per request.
- **Environment**: `python-dotenv`
- **Testing**: `pytest`
- **Quality**: `ruff` (lint + format, line-length 100) dan `mypy` (pydantic plugin)

# Project Structure

```
browsing_agent/
├── main.py                      # CLI entry point: LLM, tracing, system prompt, agent loop
├── api.py                       # FastAPI app factory: auth bearer, rate limit, concurrency cap
├── oplog.py                     # Structured operational log (JSON lines ke stderr)
├── config.py                    # Load .env, fail-fast validation
├── agent/
│   ├── planner.py               # Per-run state (ContextVar): tool limits, evidence, blocked domains
│   ├── research.py              # Plan → select → review loop; kuota per run
│   └── synthesis.py             # Sintesis jawaban + validasi citations
├── tools/
│   ├── search.py                # Search pluggable (DDG/SearXNG) + fallback + atribut span MLflow
│   ├── fetch.py                 # HTTP-first fetcher + Selenium fallback, rate limit, robots
│   └── extract.py               # Ekstraksi konten trafilatura/BS4, Pydantic models
├── policy/
│   ├── guardrails.py            # Blokir query & URL (keyword/domain filter)
│   ├── robots.py                # robots.txt checker (TTL cache, ROBOTS_FAIL_OPEN, 404=allow)
│   ├── rate_limit.py            # Rate limit per domain outbound (time.sleep)
│   └── inbound_rate_limit.py    # Rate limit per API key via Redis (fail-closed)
├── storage/evidence.py          # EvidenceStore: dedup URL & content hash, citations
├── evals/                       # Runner evaluasi offline (schema, scoring, GEPA)
├── scripts/                     # Utility manual (contoh: modelhub.py)
├── frontend/                    # UI statis (tanpa API key; Nginx menyuntik key)
├── nginx/                       # Template Nginx (resolver dinamik, /ui-api/ rewrite)
├── searxng/settings.yml         # Konfigurasi SearXNG (JSON format)
├── tests/                       # pytest (unit + integration nginx)
├── docs/
│   ├── adr/                     # ADR-0001..0010 (state, fetch, nginx, robots, rate limit, SSRF, observability)
│   ├── PRD.md
│   ├── plan_upgrade.md          # Roadmap ADLC
│   └── RUNBOOK.md               # Operasional stack
├── .github/workflows/ci.yml     # GitHub Actions: ruff + mypy + pytest + docker build
├── .gitlab-ci.yml               # GitLab CI: quality + tests
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
    && uv run --no-sync mypy . && uv run --no-sync python -m pytest tests/ -q --cov --cov-fail-under=83
  ```

# Testing Instructions

```bash
uv run python -m pytest tests/
```

- `tests/conftest.py` menonaktifkan async trace queue MLflow agar exit pytest cepat, dan mengisi nilai test untuk variabel wajib (config tanpa default; .env lokal menang).
- `tests/` mencakup config, API, search, fetch/extract, evidence, research/synthesis,
  tracing, frontend, evaluasi, dan integration Nginx. Jalankan seluruh suite;
  test individual ada di `tests/`.

# Security Considerations

- **Kredensial**: Hanya di `.env` (gitignored). Jangan pernah commit/print nilai key.
- **UI key**: Frontend tidak menyimpan key; Nginx menyuntik `UI_TO_API_KEY` (ADR-0003, ADR-0009).
- **Tool call limiting**: Per-run state ContextVar, di-reset tiap query (ADR-0001).
- **robots.txt**: Dicek sebelum fetch; kebijakan fail-open/closed via `ROBOTS_FAIL_OPEN` (ADR-0004).
- **Rate limiting**: Outbound per-domain delay; inbound per-API-key via Redis, fail-closed 503 (ADR-0006).
- **Input validation**: Guardrails (automation/bypass sesuai PRD, URL internal/privat ditolak — ADR-0007/0008) + panjang pertanyaan (`MAX_QUESTION_LENGTH`).
- **Privasi trace**: span `browsing_agent.request` menyimpan pertanyaan dan jawaban akhir mentah di MLflow; batasi akses dan retensi sesuai kebijakan data.
- **Safe crawling policy**: Tidak ada proxy rotation, fingerprint spoofing, CAPTCHA/paywall bypass. Dilarang keras.
- **Browser isolation**: Selenium headless via `ChromeDriverManager`.

# Environment Variables

Semua parameter operasional wajib ada di `.env`; `.env.example` adalah daftar kanonik
(nama, komentar, nilai referensi). `config.py` fail-fast untuk variabel wajib; Azure
OpenAI dan `CHROME_BIN`/`CHROMEDRIVER_PATH` opsional. Kredensial: `MODELHUB_*` (atau
`AZURE_OPENAI_*`), `API_ALLOWED_KEYS`, `UI_API_KEY`, `UI_TO_API_KEY`. Compose juga
mewajibkan `RATE_LIMIT_REDIS_URL`, `SEARXNG_BASE_URL`,
`MLFLOW_CONTAINER_TRACKING_URI`, `MLFLOW_EXPERIMENT_ID`, `SEARCH_PROVIDER`, dan
`NGINX_PORT`.

# Architecture Decision Records

Keputusan arsitektur signifikan didokumentasi di `docs/adr/`:

- ADR-0001 — per-run state berbasis ContextVar
- ADR-0002 — HTTP-first fetch dengan fallback Selenium
- ADR-0003 — Nginx menyuntik UI API key (tidak pernah ke browser)
- ADR-0004 — kebijakan fail-open/closed robots.txt
- ADR-0005 — rate limit API per key via Redis (digantikan ADR-0006)
- ADR-0006 — rate limit fail-closed (Redis down → 503)
- ADR-0007 — cakupan guardrails sesuai PRD (automation, bukan kata)
- ADR-0008 — blokir URL internal/privat (SSRF)
- ADR-0009 — kredensial Nginx terpisah & `/healthz/ready`
- ADR-0010 — observability minimal (`/metrics`, event `api.request`)

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
logging), dan M4 (release hygiene) selesai. Runbook `docs/RUNBOOK.md` dan GitLab CI
`.gitlab-ci.yml` sudah tersedia; lanjutan: backlog.
