# Changelog

Semua perubahan signifikan pada proyek ini didokumentasikan di file ini.
Format mengikuti [Keep a Changelog](https://keepachangelog.com/id/1.1.0/),
dan proyek mengikuti [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- Validasi startup `config.py`: `API_ALLOWED_KEYS` & `UI_API_KEY` wajib dan `UI_API_KEY` harus tercantum di `API_ALLOWED_KEYS`; minimal satu provider LLM (ModelHub lengkap atau Azure lengkap) wajib terkonfigurasi (ADR-0002, ADR-0003).
- Blokir URL internal/privat (SSRF): hostname tanpa titik, `localhost`, IP privat/loopback/link-local/reserved (termasuk bentuk desimal, hex, IPv4-mapped IPv6), dan hostname yang gagal di-resolve (ADR-0008).
- ADR-0006 (rate limit fail-closed), ADR-0007 (cakupan guardrails), ADR-0008 (SSRF).
- Compose tanpa profile menjalankan seluruh stack secara default; staging berjalan dengan `COMPOSE_PROJECT_NAME` dan `NGINX_PORT=8081` terpisah.
- Coverage gate `--cov-fail-under=83` di CI GitHub Actions & GitLab CI.
- `UI_TO_API_KEY`: key service Nginx→API terpisah dari `UI_API_KEY` browser; keduanya wajib terdaftar di `API_ALLOWED_KEYS` (ADR-0009).
- Nginx `/healthz/ready` (proxy ke API) + healthcheck container Nginx; port staging diatur melalui `NGINX_PORT`.
- Observability minimal: endpoint `/metrics` (format Prometheus) dan event log `api.request` dengan `outcome`/`status`/`duration_ms`; Nginx `safe_access` menambahkan `rt=` (ADR-0010).
- `tests/test_api.py`: test 503 fail-closed, `/metrics`, satu event per request.
- `tests/test_compose.py`: kontrak default stack, provider pencarian, port staging, dan key Nginx dengan env-file sintetis.
- Route Nginx `location = /api/metrics` (proxy ke API `/metrics`).
- Test regresi: opsi klien Redis yang diteruskan `build_rate_limiter` (opsi ilegal = 503).

### Changed

- **BREAKING**: rate limit inbound kini fail-closed (ADR-0006) — Redis tidak terjangkau membuat `POST /api/v1/ask` membalas HTTP 503 `dependency_unavailable`; limiter mengembalikan `RateLimitDecision`, bukan `bool`.
- **BREAKING (perilaku)**: guardrails mengikuti PRD (ADR-0007) — pertanyaan umum yang memuat "password"/"login" tidak lagi diblokir; domain sensitif dicocokkan per label dan entri duplikat/`bank` dihapus.
- `SEARCH_PROVIDER` kini divalidasi di `config.py` (fail-fast saat startup, bukan saat tool dipanggil).
- `pip-audit` kini blocking di CI (sebelumnya `continue-on-error`); CI memakai `pip-audit` tanpa `--skip-editable`.
- Test memaksa nilai env test (menimpa `.env` lokal) agar hasil suite tidak bergantung konfigurasi developer.
- Pipeline pencarian bertipe: provider mengembalikan `list[SearchResult]`; format string untuk LLM dihasilkan satu kali (tidak lagi regex-extract dari teks).
- Fetch HTTP diserialkan per request (`_fetcher_lock`) agar satu `httpx.Client` tidak dipakai bersamaan; HTML diparse sekali (`extract_page`) sebelum deteksi JS-heavy.
- Guardrails URL dicek sebelum kuota tool terpakai, sehingga URL internal yang ditolak tidak menghabiskan kuota.
- Tes Compose memakai salinan konfigurasi dan `.env` sintetis, sehingga kegagalan assertion tidak menampilkan kredensial lokal.
- Tes Nginx memakai aset sementara; mount prod/staging memakai SELinux shared `:z` agar tes atau staging tidak menyebabkan UI prod 403.
- Retrieval wajib sebelum sintesis LLM; model tidak bisa melewati pencarian/fetch. Jawaban tanpa nomor referensi valid tidak ditampilkan; halaman kosong/error tidak menjadi citations. Nomor inline disinkronkan dengan id citations API.

### Removed

- Pemeriksaan kelengkapan ModelHub/Azure di `main.load_llm` (dipindah ke `config.py`).
- `searxng/settings.yml`: `secret_key` dari environment `SEARXNG_SECRET` (Compose mewajibkannya), tidak lagi nilai dev ter-commit.
- Dead code: `EvidenceStore.get_citations`/`get_citations_text`, `load_dotenv()` ganda di `main.main`, cabang `isinstance(args.question, list)` yang tidak mungkin, ekstraksi canonical duplikat di `tools/extract.py`.

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
