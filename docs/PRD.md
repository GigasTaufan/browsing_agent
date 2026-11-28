# Product Requirements Document (PRD) — Browsing Agent

**Versi**: 1.2
**Tanggal**: 2026-11-28
**Status**: Implementasi saat ini (v1.2)
**Bahasa**: Indonesia

---

## 1. Executive Summary

### 1.1 Visi
Membangun agen browsing web yang aman, modular, dan legal-compliant untuk menjawab pertanyaan umum pengguna dengan menyediakan jawaban yang akurat, terverifikasi, dan disertai sumber.

### 1.2 Tujuan
- Mengupgrade aplikasi browsing agent dari **MVP** menjadi **general browsing information agent** yang dapat diandalkan.
- Memastikan setiap jawaban yang dihasilkan mencantumkan sumber (citations).
- Menjaga kepatuhan terhadap kebijakan crawling yang aman (`robots.txt`, rate limit, transparent User-Agent).
- Menyediakan arsitektur yang modular sehingga mudah di-maintain dan di-extend.

### 1.3 Ruang Lingkup
| Termasuk | Tidak Termasuk |
|----------|----------------|
| Pencarian web (pluggable: DuckDuckGo/SearXNG) + browsing halaman | Stealth, proxy rotation, fingerprint spoofing |
| Extract konten halaman web | CAPTCHA bypass |
| Citation/sumber jawaban | Paywall bypass |
| CLI interaktif + mode argumen | Login automation |
| robots.txt & rate limit compliance | Personal data harvesting |

---

## 2. Current State (v1.2)

Aplikasi saat ini telah berkembang dari MVP menjadi **v1.2** dengan arsitektur modular. Semua keterbatasan MVP telah diatasi.

| Aspek | Deskripsi |
|-------|-----------|
| **Entry Point** | `main.py` (modular) |
| **LLM** | ModelHub via `ChatOpenAI` (utama); Azure OpenAI hanya fallback |
| **Search** | Pluggable: DuckDuckGo (`ddgs`) atau SearXNG self-hosted, dengan fallback antar provider |
| **Browser** | Selenium headless Chrome sebagai fallback; HTTP-first via `httpx` |
| **Tools** | `search_web()` dan `browse_tool()` internal; agent tidak memakai tool-calling |
| **Extraction** | `trafilatura` primary, `BeautifulSoup` fallback — title, headings, text |
| **Tool Limit** | Per-run state (`AgentRunState`): counter reset setiap query |
| **CLI** | Mode argumen + mode interaktif + `--verbose` flag |
| **Tests** | Suite `pytest` per modul + E2E agent scripted + kontrak Nginx |
| **Config** | Terpusat di `config.py` + `.env` |
| **Safe Crawling** | `robots.txt`, User-Agent transparan, rate limit per domain, guardrails |
| **Evidence** | Structured `EvidenceStore` dengan SHA256 dedup + citations di jawaban final |
| **Research** | Plan → select → review iteratif; kuota per run |
| **Tracing** | MLflow GenAI; root span `browsing_agent.request`; opsional/non-fatal |
| **Inbound Rate Limit** | Redis per API key; fail-closed 503 |
| **UI** | Frontend statis; Nginx menyuntik key; jawaban dirender Markdown |

---

## 3. Target State (v1.2)

Hasil akhir setelah 11 fase upgrade:

### 3.1 Arsitektur Modular
```
browsing_agent/
├── main.py              # Entry point CLI
├── api.py               # FastAPI app factory + endpoint
├── oplog.py             # Structured operational log
├── config.py            # Environment, settings, constants (fail-fast)
├── agent/
│   ├── planner.py       # State per-query: tool limits, evidence, blocked domains
│   ├── research.py      # Plan → select → review iteratif
│   └── synthesis.py     # Sintesis jawaban + validasi citations
├── tools/
│   ├── search.py        # Pluggable search (DuckDuckGo/SearXNG), ranking
│   ├── fetch.py         # HTTP-first fetcher + fallback browser
│   └── extract.py       # Content extraction (title, headings, text)
├── policy/
│   ├── guardrails.py    # Guardrails query/URL
│   ├── robots.py        # robots.txt checker
│   ├── rate_limit.py    # Rate limiter per domain
│   └── inbound_rate_limit.py  # Rate limit API per key (Redis)
├── storage/
│   └── evidence.py      # Structured evidence store + deduplication
├── evals/               # Evaluasi offline
├── scripts/             # Utility manual
├── frontend/            # UI statis
├── nginx/               # Template ingress
└── tests/               # Unit tests (pytest)
```

### 3.2 Fitur Utama v1.0
| Fitur | Deskripsi |
|-------|-----------|
| **HTTP-first Fetching** | `httpx` sebagai default, Selenium/Playwright fallback untuk JS-heavy pages. |
| **Content Extraction** | Menghasilkan: title, canonical URL, main text, headings, `fetched_at`, `status_code`. |
| **Content Limit** | Konten dipotong ke `FETCH_MAX_CONTENT_CHARS`; tidak ada chunking/retrieval. |
| **Evidence & Citations** | Setiap sumber yang di-fetch disimpan secara terstruktur; jawaban final mencantumkan URL sumber. |
| **Search Ranking** | Skor domain kredibel + dedup URL; freshness belum diimplementasikan. |
| **Safe Crawling** | Cek `robots.txt`, transparent User-Agent, per-domain rate limit, stop pada 403/429; CAPTCHA-like belum diimplementasikan. |
| **Tool Execution Limits** | Counter reset per query; batas maksimum tool calls & URLs per query. |
| **CLI Improvement** | Mode argumen: `uv run main.py "your question" --verbose`; output sumber di akhir. |
| **Testing** | Unit test untuk robots checker, rate limiter, URL normalization, extractor, tool-call limit. |

---

## 4. Functional Requirements

### FR-1: Pencarian Web
- **FR-1.1**: Agen harus dapat melakukan pencarian web memakai provider yang dipilih lewat `SEARCH_PROVIDER` (`duckduckgo` atau `searxng`; template `searxng`).
- **FR-1.2**: Arsitektur harus mendukung penambahan search provider lain (Google Custom Search, Brave Search) tanpa mengubah kode inti.
- **FR-1.3**: Hasil pencarian di-rank memakai skor domain kredibel (`SEARCH_TRUSTED_DOMAINS`) dan dedup URL; freshness belum diimplementasikan.
- **FR-1.4**: Deduplikasi URL berdasarkan canonical URL / content hash.

### FR-2: Fetching Halaman Web
- **FR-2.1**: Fetching default menggunakan HTTP (`httpx`) dengan timeout, retry, dan exponential backoff.
- **FR-2.2**: Selenium/Playwright digunakan hanya sebagai fallback untuk halaman JS-heavy.
- **FR-2.3**: Browser session harus di-reuse (tidak launch baru per URL).
- **FR-2.4**: Skip non-HTML content kecuali diminta secara eksplisit.
- **FR-2.5**: Content-Type harus diperiksa sebelum parsing.

### FR-3: Ekstraksi Konten
- **FR-3.1**: Setiap halaman yang di-fetch harus menghasilkan struktur data berisi:
  - `title`
  - `canonical_url`
  - `main_text`
  - `headings`
  - `fetched_at`
  - `status_code`
- **FR-3.2**: Ekstraksi menggunakan library Readability/trafilatura/BeautifulSoup (bukan `body.text[:1500]`).
- **FR-3.3**: Konten dipotong ke `FETCH_MAX_CONTENT_CHARS`; aplikasi tidak memakai chunking/retrieval.

### FR-4: Evidence & Citations
- **FR-4.1**: Setiap sumber yang di-fetch disimpan sebagai structured evidence:
  - `url`, `title`, `snippet`, `canonical_url`, `fetched_at`
- **FR-4.2**: Jawaban final harus mencantumkan sumber URL.
- **FR-4.3**: Deduplikasi berdasarkan canonical URL dan content hash.
- **FR-4.4**: Prefer multiple sources untuk jawaban faktual.

### FR-5: Safe Crawling Policy
- **FR-5.1**: Cek `robots.txt` menggunakan `urllib.robotparser` sebelum fetch.
- **FR-5.2**: Gunakan User-Agent transparan dari `USER_AGENT`; template `.env.example` memakai `BrowsingAgent/0.1`.
- **FR-5.3**: Implementasi rate limiter per domain.
- **FR-5.4**: Stop atau backoff pada HTTP 403/429 dan robots disallow; deteksi CAPTCHA-like belum diimplementasikan.
- **FR-5.5**: Gunakan guardrails untuk menolak scraping ilegal, login/paywall bypass, dan personal data harvesting.

### FR-6: Tool Execution Control
- **FR-6.1**: Tool-call counter harus di-reset per user query.
- **FR-6.2**: Ganti global counter dengan per-run state.
- **FR-6.3**: Pastikan `max_tool_calls` benar-benar menghentikan eksekusi.
- **FR-6.4**: Batasan saat ini `MAX_URLS_PER_QUERY`; `max_fetch_depth` tidak diimplementasikan.

### FR-7: Agent Behavior
- **FR-7.1**: Agen harus mengikuti alur:
  ```
  User query → plan search terms → search → filter/rank URLs → policy check → fetch → extract → synthesize answer with citations
  ```
- **FR-7.2**: Agen harus berhenti ketika informasi sudah cukup atau terkena blokir.

### FR-8: CLI
- **FR-8.1**: Pertahankan CLI interaktif (`input()` loop) sebagai mode default.
- **FR-8.2**: Tambah mode argumen: `uv run main.py "your question" --verbose`.
- **FR-8.3**: Cetak daftar sumber yang digunakan di akhir jawaban.

---

## 5. Non-Functional Requirements

### NFR-1: Keamanan
- **NFR-1.1**: Kredensial LLM (ModelHub/Azure) dan search provider disimpan di `.env` (tidak di-commit).
- **NFR-1.2**: Tidak ada logging kredensial ke stdout/file.
- **NFR-1.3**: Input pengguna tidak langsung dieksekusi sebagai kode.

### NFR-2: Legal Compliance
- **NFR-2.1**: Tidak implementasi proxy rotation, fingerprint spoofing, CAPTCHA bypass, atau paywall bypass.
- **NFR-2.2**: Patuh `robots.txt` dan kebijakan rate limit.
- **NFR-2.3**: User-Agent transparan yang dapat diidentifikasi.

### NFR-3: Maintainability
- **NFR-3.1**: Kode menggunakan type hints dan Pydantic models / dataclasses.
- **NFR-3.2**: Fungsi-fungsi memiliki tanggung jawab tunggal.
- **NFR-3.3**: Komentar, docstring, dan UI string menggunakan Bahasa Indonesia.

### NFR-4: Testing
- **NFR-4.1**: Unit test untuk: robots checker, rate limiter, URL normalization, extractor, tool-call limit reset.
- **NFR-4.2**: Mocked fetch tests, tidak mengakses website nyata di CI.

### NFR-5: Performance
- **NFR-5.1**: Browser session di-reuse untuk mengurangi overhead.
- **NFR-5.2**: HTTP-first fetching mengurangi latency untuk halaman statis.

---

## 6. Architecture Overview

### 6.1 Diagram Alur Kerja v1.0
```mermaid
flowchart TD
    subgraph User
        A["User memberikan pertanyaan via CLI"]
    end

    subgraph Agent
        B["main.py: parse query & config"]
        C["research.py: susun rencana pencarian"]
        D["search.py: pencarian SearXNG/DuckDuckGo"]
        E["Filter/Rank URLs"]
        F["policy/robots.py: cek robots.txt"]
        G["policy/rate_limit.py: cek rate limit"]
        H["fetch.py: HTTP-first / fallback browser"]
        I["extract.py: ekstrak konten terstruktur"]
        J["storage/evidence.py: simpan evidence"]
        K["synthesis.py: sintesis jawaban + citations"]
    end

    subgraph Output
        L["Cetak jawaban final + daftar sumber"]
    end

    A --> B
    B --> C
    C --> D
    D --> E
    E --> F
    F --> G
    G --> H
    H --> I
    I --> J
    J --> K
    K --> L
```

### 6.2 Modul & Tanggung Jawab

| Modul | Tanggung Jawab |
|-------|----------------|
| `main.py` | Entry point, inisialisasi, CLI loop/argparse. |
| `api.py` | FastAPI app factory: auth, rate limit, concurrency, endpoint. |
| `oplog.py` | Structured operational log (JSON lines). |
| `config.py` | Load `.env`, settings, validasi fail-fast. |
| `agent/planner.py` | State management per-query: tool limits, evidence, blocked domains. |
| `agent/research.py` | Loop plan → select → review; kuota per run. |
| `agent/synthesis.py` | Sintesis jawaban dari evidence + validasi citations. |
| `tools/search.py` | Interface search provider (DuckDuckGo/SearXNG), ranking hasil. |
| `tools/fetch.py` | HTTP fetcher (`httpx`), browser fallback (Selenium), session reuse, retry. |
| `tools/extract.py` | Parsing HTML, ekstraksi terstruktur (tanpa links/chunking). |
| `policy/robots.py` | Cek `robots.txt`, parsing kebijakan situs. |
| `policy/rate_limit.py` | Rate limiter per domain, backoff strategy. |
| `storage/evidence.py` | Structured evidence store, deduplication, retrieval untuk citations. |

---

## 7. Implementation Phases

Proyek dikerjakan dalam **11 fase** sesuai roadmap.

### Phase 1 — Refactor Structure
- **Goal**: Pecah monolith menjadi modul-modul terpisah.
- **Deliverables**:
  - Buat direktori: `agent/`, `tools/`, `policy/`, `storage/`, `tests/`.
  - Pindahkan logika ke file yang sesuai:
    - `browsing_agent_selenium.py` → `main.py`, `agent/planner.py`
    - `conf/tool_selenium.py` → `tools/search.py`, `tools/fetch.py`, `tools/extract.py`
  - Tambah `config.py` untuk settings.
- **Acceptance Criteria**:
  - Tidak ada logic botak di root selain `main.py`.
  - Import berfungsi tanpa circular dependency.

### Phase 2 — Fix Tool Execution Limits
- **Goal**: Perbaiki bug counter global.
- **Deliverables**:
  - Ganti global counter dengan per-run state (dataclass / dict).
  - Reset counter setiap kali `run_agent()` dipanggil.
  - Pastikan eksekusi berhenti saat `max_tool_calls` tercapai.
  - Tambahkan batasan `MAX_URLS_PER_QUERY`; `max_fetch_depth` tidak diimplementasikan.
- **Acceptance Criteria**:
  - Tool-call counter = 0 untuk setiap query baru.
  - Agent berhenti ketika limit tercapai.

### Phase 3 — Safe Crawling Policy
- **Goal**: Tambahkan kebijakan crawling yang aman.
- **Deliverables**:
  - `policy/robots.py`: Cek `robots.txt` via `urllib.robotparser`.
  - `policy/rate_limit.py`: Rate limiter per domain (in-memory / simple dict).
  - User-Agent transparan.
  - Handling HTTP 403/429; deteksi CAPTCHA-like belum diimplementasikan.
- **Acceptance Criteria**:
  - robots.txt dicek sebelum setiap fetch.
  - Rate limit aktif per domain.
  - Tidak implementasi proxy rotation / spoofing.

### Phase 4 — Improve Fetching
- **Goal**: Optimasi fetching dengan HTTP-first strategy.
- **Deliverables**:
  - `tools/fetch.py`: Implementasi `httpx` dengan timeout, retry exponential backoff.
  - Reuse browser session (Selenium) untuk fallback.
  - Content-type filtering.
  - Skip non-HTML default.
- **Acceptance Criteria**:
  - Halaman statis di-fetch via `httpx`.
  - Browser hanya digunakan untuk JS-heavy pages.
  - Session browser di-reuse.

### Phase 5 — Improve Extraction
- **Goal**: Ekstraksi konten yang lebih baik dan terstruktur.
- **Deliverables**:
  - `tools/extract.py`: Gunakan BeautifulSoup / Readability / trafilatura.
  - Output berisi: title, canonical URL, main text, headings, fetched_at, status_code.
  - Truncate konten ke `FETCH_MAX_CONTENT_CHARS`; tidak ada chunking.
- **Acceptance Criteria**:
  - Output extraction terstruktur (Pydantic model).
  - Konten dipotong ke `FETCH_MAX_CONTENT_CHARS`.

### Phase 6 — Evidence and Citations
- **Goal**: Setiap jawaban disertai sumber.
- **Deliverables**:
  - `storage/evidence.py`: Simpan setiap fetch sebagai evidence.
  - Field: url, title, snippet, canonical_url, fetched_at.
  - Deduplication: canonical URL + content hash.
  - Final answer mencantumkan sumber URL.
- **Acceptance Criteria**:
  - Evidence tersimpan untuk setiap fetch.
  - Jawaban final mencantumkan daftar sumber.
  - Sumber duplikat di-filter.

### Phase 7 — Search and Ranking
- **Goal**: Peningkatan kualitas pencarian.
- **Deliverables**:
  - Interface pluggable search provider:
    - DuckDuckGo
    - Google Custom Search (planned)
    - Brave Search (planned)
  - Rank URLs: skor domain kredibel + deduplication; freshness belum diimplementasikan.
- **Acceptance Criteria**:
  - Provider dapat diganti via config tanpa ubah kode utama.
  - Ranking bekerja sesuai kriteria.

### Phase 8 — Agent Behavior & Guardrails
- **Goal**: Alur agen yang konsisten dan aman.
- **Deliverables**:
  - Alur baku: query → plan → search → filter/rank → policy check → fetch → extract → synthesize + citations.
  - Guardrails:
    - Tolak illegal scraping.
    - No login/paywall bypass.
    - No personal data harvesting.
    - Stop ketika diblokir.
- **Acceptance Criteria**:
  - Agen mengikuti alur baku secara konsisten.
  - Guardrails aktif dan dapat diverifikasi.

### Phase 9 — Config and Environment
- **Goal**: Sentralisasi konfigurasi.
- **Deliverables**:
  - `config.py`: Load `.env`, validasi settings.
  - Update `.env.example` sebagai daftar kanonik.
  - Kelola dependensi di `pyproject.toml` dan kunci versinya di `uv.lock`.
  - Semua parameter operasional wajib di `.env`; `EVAL_*` hanya untuk runner evaluasi offline.
- **Acceptance Criteria**:
  - `config.py` fail-fast untuk variabel wajib.
  - `.env.example` menjadi referensi nama/komentar/nilai.
  - Dependencies di-pin.

### Phase 10 — Tests
- **Goal**: Menambahkan test suite.
- **Deliverables**:
  - `tests/` dengan `pytest`.
  - Unit test untuk:
    - config, guardrails, robots, rate limit
    - search provider, fetch/extract, evidence
    - research/synthesis, tracing, frontend, evaluasi
  - Mocked fetch tests (tidak mengakses website nyata).
- **Acceptance Criteria**:
  - Test suite dapat dijalankan dengan `pytest`.
  - Semua test lolos.

### Phase 11 — CLI Improvements
- **Goal**: Meningkatkan pengalaman CLI.
- **Deliverables**:
  - Mode argumen: `uv run main.py "your question"`.
  - Flag `--verbose`.
  - Output daftar sumber di akhir.
  - Pertahankan mode interaktif.
- **Acceptance Criteria**:
  - `uv run main.py "query"` menghasilkan jawaban.
  - `--verbose` menunjukkan log detail.
  - Mode interaktif tetap berfungsi.

---

## 8. User Stories / Use Cases

### US-1: Pengguna Umum
> Sebagai pengguna umum, saya ingin mengetik pertanyaan di terminal dan mendapat jawaban akurat dengan sumber, agar saya bisa mempercayai informasi tersebut.

**Skenario**:
1. Pengguna menjalankan: `uv run main.py "Siapa penemu telepon?"`
2. Agen mencari via provider sesuai `SEARCH_PROVIDER` (template SearXNG).
3. Agen memilih URL terbaik, cek robots.txt, dan fetch.
4. Agen menyusun jawaban: "Penemu telepon adalah Alexander Graham Bell."
5. Agen mencantumkan sumber: `https://example.com/biography/bell`

### US-2: Pengguna Mode Verbose
> Sebagai pengguna teknis, saya ingin melihat proses yang dilakukan agen (search, fetch, policy check) agar saya bisa memahami dan debug jika terjadi masalah.

**Skenario**:
1. Pengguna menjalankan: `uv run main.py "query" --verbose`
2. Terminal menampilkan log tiap step: search terms, URLs yang di-rank, robots.txt status, fetch result, evidence stored.

### US-3: Developer Maintainer
> Sebagai developer, saya ingin menambahkan search provider baru tanpa mengubah kode inti, agar integrasi lebih mudah.

**Skenario**:
1. Developer membuat class baru yang mengimplementasikan interface `SearchProvider`.
2. Daftarkan di `config.py`.
3. Agen otomatis menggunakan provider baru tanpa ubah `planner.py`.

---

## 9. Dependencies & Tech Stack

### 9.1 Core Dependencies
| Library | Kegunaan |
|---------|----------|
| `python-dotenv` | Load variabel lingkungan dari `.env` |
| `langchain` | Framework LLM & agent |
| `langchain-openai` | Integrasi OpenAI-compatible (ModelHub utama, Azure fallback) |
| `langchain-core` | Komponen inti LangChain |
| `ddgs` | Pencarian DuckDuckGo |

### 9.2 Web & Browser
| Library | Kegunaan |
|---------|----------|
| `httpx` | HTTP-first fetching (Phase 4) |
| `selenium` | Browser automation (fallback) |
| `webdriver-manager` | Manajemen ChromeDriver |

### 9.3 Parsing & Extraction
| Library | Kegunaan |
|---------|----------|
| `lxml` | Parsing HTML/XML |
| `beautifulsoup4` | Ekstraksi konten (Phase 5) |
| `readability-lxml` atau `trafilatura` | Ekstraksi artikel bersih (Phase 5) |

### 9.4 Data & Config
| Library | Kegunaan |
|---------|----------|
| `pydantic` | Validasi settings & models (Phase 1/9) |

### 9.5 Testing
| Library | Kegunaan |
|---------|----------|
| `pytest` | Test runner (Phase 10) |
| `pytest-mock` atau `unittest.mock` | Mocking fetch (Phase 10) |

### 9.6 Environment Variables

Semua parameter operasional wajib di `.env`; `.env.example` adalah daftar kanonik.
`config.py` fail-fast untuk variabel wajib. Azure OpenAI dan path Chrome opsional;
variabel Compose (`RATE_LIMIT_REDIS_URL`, `SEARXNG_BASE_URL`,
`MLFLOW_CONTAINER_TRACKING_URI`, `MLFLOW_EXPERIMENT_ID`, `SEARCH_PROVIDER`,
`NGINX_PORT`) wajib untuk stack Compose. `EVAL_*` hanya untuk runner evaluasi offline.

---

## 10. Acceptance Criteria (Keseluruhan)

Aplikasi telah memenuhi semua acceptance criteria:

- [x] Agen dapat menjawab pertanyaan informasi umum menggunakan search + browsing.
- [x] Setiap jawaban yang dirilis memiliki citation valid; tanpa bukti, agen menolak menjawab tanpa citation.
- [x] `robots.txt` dicek sebelum setiap fetch.
- [x] Rate limiter aktif per domain.
- [x] Tool-call counter di-reset per user query.
- [x] Browser di-reuse atau hanya digunakan sebagai fallback.
- [x] Tidak ada stealth, proxy rotation, CAPTCHA bypass, atau paywall bypass.
- [x] CLI mendukung mode argumen dan mode interaktif.
- [x] Quality gate hijau: `ruff`, `mypy`, `pytest`; coverage ≥83%.
- [x] Parameter runtime terpusat di `config.py`/`.env`; parameter evaluasi di `evals/schema.py`/`EVAL_*`.

---

## 11. Risks & Constraints

### Risks
| Risiko | Mitigasi |
|--------|----------|
| DuckDuckGo mengubah format output | Abstraksi interface search provider (Phase 7). |
| Website blokir User-Agent agen | Gunakan User-Agent transparan dan patuh robots.txt; tidak bypass. |
| Selenium overhead tinggi | HTTP-first + reuse session (Phase 4). |
| LangChain breaking changes | Kunci versi di `uv.lock` (Phase 9). |

### Constraints
- Tidak boleh mengimplementasikan: proxy rotation, fingerprint spoofing, CAPTCHA bypass, paywall bypass.
- Tidak boleh melakukan personal data harvesting.
- Tidak boleh mengotomatisasi login.
- Semua kode harus menggunakan Bahasa Indonesia untuk komentar/docstring/UI.
