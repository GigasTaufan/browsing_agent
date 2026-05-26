<!--
  This file is the single source of truth for AI coding agents working on this project.
  It is authoritative for all directories beneath the project root unless overridden
  by a deeper AGENTS.md.

  Behavioral guidelines to reduce common LLM coding mistakes.

  **Tradeoff:** These guidelines bias toward caution over speed. For trivial tasks,
  use your own judgment.
-->

# Project Overview

`browsing_agent` adalah agen browsing web yang aman, modular, dan legal-compliant untuk menjawab pertanyaan umum pengguna dengan informasi dari web. Agen menggunakan DuckDuckGo untuk pencarian, `httpx` untuk fetch (dengan Selenium sebagai fallback), dan Azure OpenAI sebagai LLM. Setiap jawaban mencantumkan sumber (citations).

Bahasa utama yang digunakan dalam kode, komentar, dan dokumentasi adalah **Bahasa Indonesia**.

# Technology Stack

- **Python**: 3.11+
- **LLM Framework**: LangChain 1.3+ (`langchain`, `langchain-openai`, `langchain-community`, `langchain-core`, `langchainhub`, `langchain-text-splitters`)
- **LLM Provider**: Azure OpenAI (`AzureChatOpenAI`)
- **Web Search**: DuckDuckGo (`DuckDuckGoSearchResults` via `ddgs` package)
- **HTTP Fetch**: `httpx` (primary)
- **Browser Fallback**: Selenium + `webdriver-manager` (headless Chrome)
- **Content Extraction**: `trafilatura` (primary) / `beautifulsoup4` + `lxml` (fallback)
- **Environment**: `python-dotenv`
- **Testing**: `pytest`

# Project Structure

```
browsing_agent/
├── main.py              # Entry point CLI — orkestrasi LLM, tools, agent loop
├── config.py            # Load .env, konstanta, settings
├── agent/
│   └── planner.py       # Per-run state: tool limits, evidence store, blocked domains
├── tools/
│   ├── search.py        # DuckDuckGo search dengan retry (lite→auto), ranking, dedup
│   ├── fetch.py         # HTTP-first fetcher + Selenium fallback, rate limit, robots
│   └── extract.py       # Content extraction via trafilatura/BS4, Pydantic models
├── policy/
│   ├── guardrails.py    # Query & URL blocking (keyword / domain filter)
│   ├── robots.py        # robots.txt checker dengan 1-hour TTL cache
│   └── rate_limit.py    # Per-domain rate limiter (time.sleep)
├── storage/
│   └── evidence.py      # EvidenceStore: dedup by URL & content hash, citations
├── tests/               # Unit tests (pytest)
│   ├── test_evidence.py
│   ├── test_extract.py
│   ├── test_limits.py
│   ├── test_rate_limit.py
│   └── test_robots.py
├── docs/
│   ├── plan_upgrade.md  # Roadmap upgrade 11 fase (sebagian besar completed)
│   └── PRD.md           # Product Requirements Document
├── .env / .env.example  # Variabel lingkungan (kredensial Azure OpenAI & settings)
└── .vscode/settings.json # Konfigurasi VS Code
```

# Build and Run Commands

Tidak ada build system formal (tidak ada `pyproject.toml`, `setup.py`, `Makefile`).

**Instalasi:**
```bash
pip install -r requirements.txt
```

**Menjalankan agen:**
```bash
python main.py "pertanyaan Anda"
# atau mode interaktif:
python main.py
```

**Menjalankan dengan verbose:**
```bash
python main.py "pertanyaan Anda" --verbose
```

**Menjalankan tests:**
```bash
pytest tests/
```

# Code Style Guidelines

- **Bahasa**: Komentar, docstring, dan string UI menggunakan Bahasa Indonesia.
- **Penamaan**: `snake_case` untuk fungsi dan variabel.
- **Struktur**: Kode dipecah menjadi fungsi-fungsi dengan tanggung jawab tunggal.
- **Tools**: Didekorasi dengan `@tool` dari LangChain. Deskripsi `tool` harus jelas untuk LLM.
- **Error handling**: Gunakan blok `try/except` sederhana dengan `print` ke stdout. Tidak ada logging framework.
- **Konfigurasi**: Terpusat di `config.py` + `.env` (tidak ada magic numbers di file lain).
- **Import grouping**: Impor bawaan Python → library pihak ketiga → modul lokal (`agent/`, `tools/`, `policy/`, `storage/`).

# Testing Instructions

Test suite ada di direktori `tests/` menggunakan `pytest`.

```bash
pytest tests/
```

Cakupan test:
- `test_evidence.py` — deduplication by URL & content hash, citation formatting
- `test_extract.py` — HTML extraction structure, main text, chunking
- `test_limits.py` — counter increment, reset per query, ToolLimitReached
- `test_rate_limit.py` — domain rate limit, no-wait on first request
- `test_robots.py` — allow/disallow, fetch error fail-open

# Security Considerations

- **Kredensial**: Simpan di file `.env` (sudah termasuk di `.gitignore`). Jangan commit kredensial ke repository.
- **Tool call limiting**: Menggunakan per-run state (`AgentRunState`) yang direset sebelum setiap query. Tidak ada global counter.
- **robots.txt**: Diperiksa sebelum setiap fetch (`policy/robots.py`).
- **Rate limiting**: Delay antar request ke domain yang sama (`policy/rate_limit.py`).
- **Input validation**: Query dicek oleh guardrails sebelum diproses.
- **Browser isolation**: Selenium menggunakan mode headless dengan `ChromeDriverManager`.
- **Safe crawling policy**: Tidak ada proxy rotation, fingerprint spoofing, CAPTCHA bypass, atau paywall bypass. Dilarang keras.

# Environment Variables

Wajib diisi di file `.env` (salin dari `.env.example`):

| Variable | Wajib | Default | Keterangan |
|----------|-------|---------|------------|
| `AZURE_OPENAI_ENDPOINT` | Ya | — | Endpoint Azure OpenAI |
| `AZURE_OPENAI_API_KEY` | Ya | — | API Key Azure OpenAI |
| `AZURE_OPENAI_DEPLOYMENT_NAME` | Tidak | `gpt-4o-mini` | Deployment model |
| `AZURE_OPENAI_PREVIEW_API_VERSION` | Ya | — | Versi API preview |
| `MAX_TOOL_CALLS` | Tidak | `5` | Batas tool calls per query |
| `MAX_URLS_PER_QUERY` | Tidak | `3` | Batas URL fetch per query |
| `MAX_SEARCH_RESULTS` | Tidak | `5` | Maksimum hasil pencarian |
| `REQUEST_TIMEOUT` | Tidak | `30` | Timeout HTTP (detik) |
| `BROWSER_FALLBACK_ENABLED` | Tidak | `true` | Aktifkan Selenium fallback |
| `USER_AGENT` | Tidak | `BrowsingAgent/0.1` | User-Agent string |
| `RATE_LIMIT_PER_DOMAIN_SECONDS` | Tidak | `1.0` | Delay antar domain (detik) |
| `CHUNK_SIZE` | Tidak | `2000` | Ukuran chunk konten |

# Upgrade Roadmap

Proyek ini berstatus **post-MVP / v1.0-ready**. roadmap lengkap ada di `docs/plan_upgrade.md`.

Fase 1–10 (modularisasi, tool limits, safe crawling, fetching, extraction, evidence, search, guardrails, config, tests) sudah **largely implemented**.

Fase 11 (CLI improvements) juga sudah diimplementasi.

---

# 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them — don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

# 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

# 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it — don't delete it.

When your changes create orphans:
- Remove imports / variables / functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

# 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work")
require constant clarification.
