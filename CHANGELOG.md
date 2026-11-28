# Changelog

Semua perubahan signifikan pada proyek ini didokumentasikan di file ini.
Format mengikuti [Keep a Changelog](https://keepachangelog.com/id/1.1.0/),
dan proyek mengikuti [Semantic Versioning](https://semver.org/).

## [2.0.0] - 2026-11-28

### Added

- Evaluator offline `python -m evals validate/run`: baseline LangChain, sintesis DSPy 3.5 dan optimasi GEPA, dataset snapshot train/validation/test, budget seluruh inference, serta laporan privat di `eval-results/`. Group `eval` opsional pada Python 3.14; CLI/API produksi tetap LangChain. Seed 18 kasus sintetis hanya menguji harness, bukan membuktikan kualitas produksi.
- Pemakaian: `uv sync --locked --group eval`, lalu `uv run --no-sync --group eval python -m evals validate --dataset evals/data/synthesis_seed.jsonl`. Run berbayar: isi variabel `EVAL_*` dari `.env.example`, lalu `python -m evals run --dataset PATH --output DIREKTORI_BARU [--smoke]`; smoke memakai satu kasus per split dan tidak menghasilkan verdict peningkatan kualitas.
- Error inference provider/auth yang ditelan GEPA tetap tercatat pada ledger bersama dan mencegah penyimpanan program serta evaluasi holdout. Parsing kandidat yang gagal tetap dapat dinilai nol; pesan exception/credential tidak ikut laporan.
- Tracing aplikasi LangChain diarahkan ke server MLflow dan experiment ID yang sudah ada (`MLFLOW_EXPERIMENT_ID`); `setup_tracing` tidak membuat experiment berdasarkan nama. Default template memakai `http://localhost:5000` dan ID `1`.
- Satu root span `browsing_agent.request` mengelompokkan invokasi LangGraph/model per request; input berisi pertanyaan dan output berisi jawaban akhir, keduanya mentah. Akses/retensi MLflow harus memperlakukan trace sebagai data pengguna.
- Kontrak keluaran judge diperjelas: enam field wajib, array boolean JSON dengan panjang/urutan gold yang tepat, dan `unsupported_claims=[]` wajib saat kosong. Validasi tetap ketat; tidak menambah retry atau mengganti provider.
- Evaluator GEPA memakai `skip_perfect_score=False` agar refleksi tetap dicoba pada minibatch berskor sempurna; opsi ini dicatat dalam manifest run.
- Evaluator GEPA menerima proposal dengan skor meningkat atau seri (`acceptance_criterion=improvement_or_equal`); seleksi akhir tetap berbasis validation dan opsi dicatat dalam manifest.
- Judge evaluator meminta `json_schema` ketat dengan field wajib dan panjang array sesuai gold tiap kasus; provider harus mendukung structured output. Tidak ada native tool calling, retry/fallback, atau padding jawaban. Kegagalan scoring pertama (termasuk saat GEPA menelan exception) disimpan dalam `scoring_failure.json` tanpa respons provider mentah; sintesis/refleksi tetap ChatAdapter.
- Audit kandidat GEPA di `gepa_audit.json`: proposal, penerimaan/penolakan/skip, skor validation per kasus, prompt tiap kandidat, dan indeks pemenang; tanpa LM, credential atau respons refleksi mentah.
- Pemetaan ID audit GEPA memakai valset terfilter yang sama dengan compile; kasus validation tanpa evidence tetap dievaluasi oleh runner tetapi tidak menggeser label skor kandidat dalam audit.
- Audit GEPA menyimpan setiap proposal sebelum filter AllImprovements, skor subsampel sebelum/sesudah, hasil acceptance criterion, indeks kandidat yang diterima, serta alasan penolakan dari callback GEPA.
- Prompt produksi CLI/API memakai kandidat 2 dari audit GEPA; tanggal dinamis, batas tool, validasi citation, dan aturan mengabaikan instruksi dalam evidence tetap dipertahankan. Backend produksi tetap LangChain.
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

- **BREAKING**: seluruh parameter tuning operasional kini wajib di `.env` dan tidak lagi hardcoded di kode: header ModelHub, skor/domain ranking pencarian, retry DDG, `safesearch`, backoff/ambang JS fetch, batas heading, panjang hash/snippet evidence, prefix/hash/TTL bucket Redis, serta daftar domain/segmen path guardrails. `compose.yaml` juga tidak lagi menyediakan fallback; URL service, experiment ID, provider, dan `NGINX_PORT` wajib diisi di `.env` (lihat `.env.example`).
- **BREAKING**: rate limit inbound kini fail-closed (ADR-0006) — Redis tidak terjangkau membuat `POST /api/v1/ask` membalas HTTP 503 `dependency_unavailable`; limiter mengembalikan `RateLimitDecision`, bukan `bool`.
- **BREAKING (perilaku)**: guardrails mengikuti PRD (ADR-0007) — pertanyaan umum yang memuat "password"/"login" tidak lagi diblokir; domain sensitif dicocokkan per label dan entri duplikat/`bank` dihapus.
- `SEARCH_PROVIDER` kini divalidasi di `config.py` (fail-fast saat startup, bukan saat tool dipanggil).
- `pip-audit` kini blocking di CI (sebelumnya `continue-on-error`); CI memakai `pip-audit` tanpa `--skip-editable`.
- Test memaksa nilai env test (menimpa `.env` lokal) agar hasil suite tidak bergantung konfigurasi developer.
- Pipeline pencarian bertipe: provider dan `search_web()` mengembalikan `list[SearchResult]`; tidak ada lagi format string untuk LLM.
- Fetch HTTP diserialkan per request (`_fetcher_lock`) agar satu `httpx.Client` tidak dipakai bersamaan; HTML diparse sekali (`extract_page`) sebelum deteksi JS-heavy.
- Guardrails URL dicek sebelum kuota tool terpakai, sehingga URL internal yang ditolak tidak menghabiskan kuota.
- Tes Compose memakai salinan konfigurasi dan `.env` sintetis, sehingga kegagalan assertion tidak menampilkan kredensial lokal.
- Tes Nginx memakai aset sementara; mount prod/staging memakai SELinux shared `:z` agar tes atau staging tidak menyebabkan UI prod 403.
- Retrieval wajib sebelum sintesis LLM; model tidak bisa melewati pencarian/fetch. Jawaban tanpa nomor referensi valid tidak ditampilkan; halaman kosong/error tidak menjadi citations. Nomor inline disinkronkan dengan id citations API.
- Riset adaptif: reformulasi query sesuai intent/wilayah, seleksi kandidat oleh LLM, evaluasi isi halaman, pencarian lanjutan untuk kekurangan bukti, dedup lintas query dan prioritas lintas domain. Semua tetap dibatasi kuota per run.
- `SEARCH_CANDIDATE_LIMIT` wajib di `.env` (referensi 20, >= `MAX_SEARCH_RESULTS`) agar kandidat tidak dipotong sebelum evaluasi relevansi.

### Removed

- Pemeriksaan kelengkapan ModelHub/Azure di `main.load_llm` (dipindah ke `config.py`).
- `searxng/settings.yml`: `secret_key` dari environment `SEARXNG_SECRET` (Compose mewajibkannya), tidak lagi nilai dev ter-commit.
- Dead code: `EvidenceStore.get_citations`/`get_citations_text`, `load_dotenv()` ganda di `main.main`, cabang `isinstance(args.question, list)` yang tidak mungkin, ekstraksi canonical duplikat di `tools/extract.py`.
- Wrapper pencarian `search_tool`/`_format_results`; `ExtractedPage.links`/`text_chunks` dan `_chunk_text`; `EvidenceItem.content_hash`; `DomainRateLimiter.reset`; `clear_robots_cache`; env `CHUNK_SIZE` dan `SEARCH_LOG_TOP_RESULTS`.

### Fixed

- UI merender jawaban Markdown menjadi elemen DOM aman (bold, italic, heading, list, code, blockquote, link http/https) tanpa `innerHTML`; marker `**`/`*` tidak lagi tampil literal.
- Guardrail SSRF memblokir semua host publik IPv4-only di container karena lookup AAAA `EAI_NODATA` dianggap kegagalan total. Kegagalan satu family DNS kini diabaikan; host tetap diblokir bila tidak ada alamat sama sekali atau salah satu alamat hasil resolve privat.
- Dedup evidence memakai hash isi tanpa canonical URL, sehingga konten identik di URL berbeda tidak tersimpan ganda.

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
