<!--
  This file is the single source of truth for AI coding agents working on this project.
  It is authoritative for all directories beneath the project root unless overridden
  by a deeper AGENTS.md.

  Behavioral guidelines to reduce common LLM coding mistakes.

  **Tradeoff:** These guidelines bias toward caution over speed. For trivial tasks,
  use your own judgment.
-->

# Project Overview

`browsing_agent` adalah implementasi sederhana dari agen browsing web (MVP) yang dibangun menggunakan Python, framework LangChain, dan terhubung ke Azure OpenAI. Agen dapat mencari informasi di web menggunakan DuckDuckGo dan membaca konten halaman web menggunakan Selenium (headless Chrome) untuk menjawab pertanyaan pengguna.

Bahasa utama yang digunakan dalam kode, komentar, dan dokumentasi adalah **Bahasa Indonesia**.

# Technology Stack

- **Python**: 3.8+ (notebook menggunakan kernel `dev` dengan Python 3.12.11)
- **LLM Framework**: LangChain (`langchain`, `langchain-openai`, `langchain-community`, `langchain-core`, `langchainhub`)
- **LLM Provider**: Azure OpenAI (`AzureChatOpenAI`)
- **Web Search**: DuckDuckGo (`DuckDuckGoSearchResults` dari `langchain_community`)
- **Web Browser**: Selenium + `webdriver-manager` (Chrome headless)
- **Environment**: `python-dotenv`
- **Parsing**: `lxml`
- **Notebook**: Jupyter (file `.ipynb` tersedia)

# Project Structure

```
browsing_agent_selenium.py   # Entry point utama — orkestrasi LLM, tools, dan loop interaktif
conf/
  tool_selenium.py           # Definisi tools: search_tool (DuckDuckGo) & browse_tool (Selenium)
  tool_beatiful_soup.py      # Contoh minimal fetching dengan requests (tidak aktif)
  tool_tavily.py             # Contoh minimal integrasi Tavily (tidak aktif)
  tool_beatiful_soup.ipynb   # Notebook terkait BeautifulSoup
docs/
  PENJELASAN_KODE.md         # Penjelasan rinci kode browsing_agent.py
  plan_upgrade.md            # Roadmap upgrade 11 fase dari MVP ke general browsing agent
  note.md                    # Diagram Mermaid proses bisnis (tidak berkaitan langsung dengan kode agen)
testing_create_agent.ipynb   # Notebook kosong (tidak digunakan)
requirements.txt             # Daftar dependensi (tidak ada versi yang dipin)
.env / .env.example          # Variabel lingkungan untuk kredensial Azure OpenAI & Tavily
.vscode/settings.json        # Konfigurasi VS Code (conda default env manager)
```

# Build and Run Commands

Tidak ada build system formal (tidak ada `pyproject.toml`, `setup.py`, `Makefile`, atau konfigurasi serupa).

**Instalasi:**
```bash
pip install -r requirements.txt
```

**Menjalankan agen:**
```bash
python browsing_agent_selenium.py
```

Script akan memuat variabel lingkungan dari `.env`, menginisialisasi LLM dan tools, lalu meminta pertanyaan via terminal. Ketik `exit` atau `quit` untuk keluar.

**Menjalankan notebook:**
```bash
jupyter notebook testing_create_agent.ipynb
# atau
jupyter notebook conf/tool_beatiful_soup.ipynb
```

# Code Style Guidelines

- **Bahasa**: Komentar, docstring, dan string UI menggunakan Bahasa Indonesia.
- **Penamaan**: `snake_case` untuk fungsi dan variabel.
- **Struktur**: Kode dipecah menjadi fungsi-fungsi dengan tanggung jawab tunggal (`load_llm`, `define_agent`, `run_agent`, `main`).
- **Tools**: Didekorasi dengan `@tool` dari LangChain. Deskripsi `tool` harus jelas untuk LLM.
- **Error handling**: Gunakan blok `try/except` sederhana dengan `print` ke stdout. Tidak ada logging framework.
- **Konfigurasi**: Saat ini tersebar (magic numbers di file, variabel global untuk counter pemanggilan tool).
- **Import grouping**: Impor bawaan Python → library pihak ketiga → modul lokal (`conf/`).

# Testing Instructions

**Saat ini tidak ada test suite.** Tidak ada direktori `tests/`, file test, atau konfigurasi CI/CD.

File `testing_create_agent.ipynb` adalah notebook kosong dan tidak berisi test.

Jika menambahkan test, gunakan `pytest` dan ikuti roadmap di `docs/plan_upgrade.md` (Phase 10).

# Security Considerations

- **Kredensial**: Simpan di file `.env` (sudah termasuk di `.gitignore`). Jangan commit kredensial Azure OpenAI atau Tavily ke repository.
- **Tool call limiting**: Saat ini menggunakan variabel global sederhana (`max_tool_calls = 5`) yang tidak reset antar query. Ini adalah keterbatasan yang diketahui, tercatat di `docs/plan_upgrade.md` Phase 2.
- **No robots.txt checking**: Agen membuka URL apapun yang diberikan tanpa memeriksa `robots.txt`.
- **No rate limiting**: Tidak ada throttling per domain.
- **No input validation**: Query pengguna diteruskan langsung ke LLM dan search tools tanpa sanitasi.
- **Browser isolation**: Selenium menggunakan mode headless dengan `ChromeDriverManager` yang mengunduh driver Chrome secara otomatis.
- **Safe crawling policy**: Dokumen `docs/plan_upgrade.md` secara eksplisit melarang implementasi proxy rotation, fingerprint spoofing, CAPTCHA bypass, atau paywall bypass (Phase 3 dan 8).

# Environment Variables

Wajib diisi di file `.env` (salin dari `.env.example`):

| Variable | Keterangan |
|----------|-----------|
| `AZURE_OPENAI_ENDPOINT` | Endpoint Azure OpenAI |
| `AZURE_OPENAI_API_KEY` | API Key Azure OpenAI |
| `AZURE_OPENAI_DEPLOYMENT_NAME` | Nama deployment model (default: `gpt-4o-mini`) |
| `AZURE_OPENAI_PREVIEW_API_VERSION` | Versi API preview Azure OpenAI |
| `TavilyClient` | API Key Tavily (opsional, hanya jika menggunakan `conf/tool_tavily.py`) |

# Upgrade Roadmap

Proyek ini berstatus **MVP**. roadmap upgrade lengkap ada di `docs/plan_upgrade.md` dengan 11 fase meliputi:
1. Refactor struktur modular
2. Fix tool execution limits
3. Safe crawling policy (robots.txt, rate limit, user-agent)
4. Improve fetching (HTTP-first, fallback browser)
5. Improve content extraction
6. Evidence and citations
7. Search and ranking
8. Agent behavior & guardrails
9. Config and environment
10. Tests
11. CLI improvements

Sebelum mengimplementasikan fitur baru, periksa roadmap di `docs/plan_upgrade.md` untuk memastikan tidak bertabrakan dengan rencana yang sudah ada.

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
