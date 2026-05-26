# Agen Browsing Web dengan LangChain

Agen browsing web yang aman, modular, dan legal-compliant untuk menjawab pertanyaan pengguna dengan informasi terkini dari web — lengkap dengan sumber (citations).

## Fitur Utama

- **LLM dengan Azure OpenAI** — `AzureChatOpenAI` sebagai otak agen untuk perencanaan dan analisis.
- **Pencarian Web** — DuckDuckGo dengan retry multi-backend (`lite` → `auto`) dan ranking berbasis kualitas domain.
- **HTTP-First Fetching** — `httpx` sebagai default; browser Selenium hanya jadi fallback untuk halaman JS-heavy.
- **Extract Konten Terstruktur** — Menggunakan `trafilatura` / `BeautifulSoup` untuk ekstrak judul, headings, teks utama, dan link.
- **Evidence & Citations** — Setiap sumber yang di-fetch disimpan secara terstruktur; jawaban akhir mencantumkan URL sumber.
- **Safe Crawling** — Cek `robots.txt`, User-Agent transparan, rate limit per domain, dan stop pada 403/429.
- **Tool Execution Limits** — Counter tool calls reset per query, dengan batas maksimum tool calls & URLs per query.
- **CLI Interaktif + Mode Argumen** — Jalankan sekali dengan argumen atau pakai mode interaktif.

## Arsitektur

```
browsing_agent/
├── main.py              # Entry point CLI
├── config.py            # Environment & settings
├── agent/
│   └── planner.py       # Per-run state: tool limits, evidence store
├── tools/
│   ├── search.py        # DuckDuckGo search dengan retry & ranking
│   ├── fetch.py         # HTTP-first fetcher + Selenium fallback
│   └── extract.py       # Content extraction (trafilatura / BS4)
├── policy/
│   ├── guardrails.py    # Keyword & domain blocking
│   ├── robots.py        # robots.txt checker dengan cache
│   └── rate_limit.py    # Per-domain rate limiter
├── storage/
│   └── evidence.py      # Structured evidence store + dedup
└── tests/               # Unit tests (pytest)
```

## Cara Kerja

1. Pengguna memberikan pertanyaan via CLI (argumen atau interaktif).
2. Agen menyusun rencana — biasanya search dulu menggunakan DuckDuckGo.
3. Hasil search di-rank dan di-deduplikasi berdasarkan kualitas domain.
4. Agen memilih URL menjanjikan → cek guardrails → cek `robots.txt` → rate limit → fetch.
5. Fetcher menggunakan HTTP dulu; jika halaman JS-heavy, fallback ke Selenium.
6. Konten diekstrak secara terstruktur (judul, headings, teks) dan disimpan sebagai evidence.
7. Agen menyusun jawaban akhir dengan menampilkan citations (sumber URL).

## Instalasi

**Prasyarat:** Python 3.11+

```bash
# 1. Clone repo
git clone https://github.com/GigasTaufan/browsing_agent.git
cd browsing_agent

# 2. Buat virtual environment (opsional tapi dianjurkan)
uv venv --python 3.11
.venv\Scripts\activate  # Windows
# atau: source .venv/bin/activate  # Linux/Mac

# 3. Install dependensi
uv pip install -r requirements.txt

# 4. Setup environment
copy .env.example .env
# Edit .env dan isi kredensial Azure OpenAI Anda
```

## Cara Menjalankan

### Mode argumen (one-shot)
```bash
python main.py "Siapa CEO Telkom Indonesia saat ini?"
```

### Mode interaktif
```bash
python main.py
```

### Mode verbose (log detail setiap step)
```bash
python main.py "your question" --verbose
```

### Jalankan tests
```bash
pytest tests/
```

## Konfigurasi Environment

| Variabel | Default | Keterangan |
|----------|---------|------------|
| `AZURE_OPENAI_ENDPOINT` | — (wajib) | Endpoint Azure OpenAI |
| `AZURE_OPENAI_API_KEY` | — (wajib) | API Key Azure OpenAI |
| `AZURE_OPENAI_DEPLOYMENT_NAME` | `gpt-4o-mini` | Nama deployment model |
| `AZURE_OPENAI_PREVIEW_API_VERSION` | — (wajib) | Versi API preview |
| `MAX_TOOL_CALLS` | `5` | Batas pemanggilan tool per query |
| `MAX_URLS_PER_QUERY` | `3` | Batas URL yang difetch per query |
| `MAX_SEARCH_RESULTS` | `5` | Maksimum hasil search yang ditampilkan |
| `REQUEST_TIMEOUT` | `30` | Timeout HTTP request (detik) |
| `BROWSER_FALLBACK_ENABLED` | `true` | Aktifkan Selenium fallback |
| `USER_AGENT` | `BrowsingAgent/0.1` | User-Agent string |
| `RATE_LIMIT_PER_DOMAIN_SECONDS` | `1.0` | Delay antar request ke domain sama (detik) |
| `CHUNK_SIZE` | `2000` | Ukuran chunk konten halaman |

## Kepatuhan & Batasan

- ** robots.txt** — Diperiksa sebelum setiap fetch.
- **Rate Limit** — Delay antar request ke domain yang sama.
- **Guardrails** — Blokir query dan URL yang mencurigakan (bypass, paywall, login, dll).
- **No Stealth** — Tidak ada proxy rotation, fingerprint spoofing, CAPTCHA bypass, atau paywall bypass.

## Tech Stack

| Komponen | Library |
|----------|---------|
| LLM | `langchain` 1.3+, `langchain-openai` |
| Search | `duckduckgo-search` (via `ddgs`) |
| HTTP Fetch | `httpx` |
| Browser Fallback | `selenium` + `webdriver-manager` |
| Content Extraction | `trafilatura`, `beautifulsoup4`, `lxml` |
| Testing | `pytest` |
| Environment | `python-dotenv` |
