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

**Prasyarat:** [uv](https://docs.astral.sh/uv/getting-started/installation/). Python 3.14+; uv dapat mengunduh Python jika belum tersedia.

```bash
# 1. Clone repo
git clone https://github.com/GigasTaufan/browsing_agent.git
cd browsing_agent

# 2. Buat .venv dan install dependensi aplikasi + pengujian dari uv.lock
uv sync --locked

# 3. Setup kredensial (Linux/Mac)
cp .env.example .env
# Windows PowerShell: Copy-Item .env.example .env
# Edit .env dan isi kredensial Azure OpenAI Anda
```

Dependensi dikelola di `pyproject.toml`; `uv.lock` mengunci versinya agar instalasi konsisten. `uv run` memakai `.venv` otomatis, tanpa aktivasi manual. Untuk instalasi tanpa dependensi pengujian, gunakan `uv sync --locked --no-dev`.

## Cara Menjalankan

### Mode argumen (one-shot)
```bash
uv run main.py "Siapa CEO Telkom Indonesia saat ini?"
```

### Mode interaktif
```bash
uv run main.py
```

### Mode verbose (log detail setiap step)
```bash
uv run main.py "pertanyaan Anda" --verbose
```

### Jalankan tests
```bash
uv run python -m pytest tests/
```

## Konfigurasi Environment

| Variabel | Default | Keterangan |
|----------|---------|------------|
| `AZURE_OPENAI_ENDPOINT` | — (wajib untuk Azure) | Endpoint Azure OpenAI |
| `AZURE_OPENAI_API_KEY` | — (wajib untuk Azure) | API Key Azure OpenAI |
| `AZURE_OPENAI_DEPLOYMENT_NAME` | `gpt-4o-mini` | Nama deployment model Azure |
| `AZURE_OPENAI_PREVIEW_API_VERSION` | — (wajib untuk Azure) | Versi API preview |
| `MODELHUB_API_KEY` | — (opsional) | Jika diisi, aplikasi memilih ModelHub alih-alih Azure |
| `MODELHUB_BASE_URL` | `https://api-modelhub.aiplayground.id/v1` | Endpoint OpenAI-compatible ModelHub |
| `MODELHUB_MODEL_NAME` | `gpt-4o-mini` | Nama model ModelHub |
| `MAX_TOOL_CALLS` | `5` | Batas pemanggilan tool per query |
| `MAX_URLS_PER_QUERY` | `3` | Batas URL unik yang dicoba di-fetch per query; gagal tetap dihitung, URL yang sama tidak menambah kuota |
| `MAX_SEARCH_RESULTS` | `5` | Maksimum hasil search yang ditampilkan |
| `REQUEST_TIMEOUT` | `30` | Timeout HTTP request (detik) |
| `BROWSER_FALLBACK_ENABLED` | `true` | Aktifkan Selenium fallback |
| `USER_AGENT` | `BrowsingAgent/0.1` | User-Agent untuk pengambilan halaman web |
| `RATE_LIMIT_PER_DOMAIN_SECONDS` | `1.0` | Delay antar request ke domain sama (detik) |
| `CHUNK_SIZE` | `2000` | Ukuran chunk konten halaman |

Untuk menjalankan contoh penggunaan API ModelHub secara langsung:
```bash
uv run docs/modelhub.py
```

## API melalui Docker Compose

API dijalankan hanya di jaringan internal Compose; Nginx menerbitkan UI dan API pada port `8080` host. Buat `.env` lokal dari `.env.example`, lalu ganti semua nilai placeholder dengan nilai acak/rahasia milik Anda. `API_ALLOWED_KEYS` menerima daftar key caller yang dipisahkan koma; masukkan `UI_API_KEY` ke daftar tersebut. Simpan `.env` dengan izin akses terbatas dan jangan commit atau membagikan isinya.

```bash
cp .env.example .env
# Edit .env: set API_ALLOWED_KEYS dan UI_API_KEY yang unik serta kredensial provider.
docker compose up --build -d
docker compose ps
docker compose down
```

Buka halaman uji pada <http://localhost:8080/>. Form UI mengirim permintaan ke `/ui-api/v1/ask`; key UI diberikan Nginx ke API dan tidak ditanamkan di HTML/JavaScript. Siapa pun yang dapat mengakses halaman uji dapat memakai key UI melalui halaman tersebut, sehingga batasi akses jaringan ke UI. Jangan publikasikan port ini ke internet. Nginx pada konfigurasi ini hanya HTTP; sediakan HTTPS pada reverse proxy/terminasi TLS yang tepercaya untuk trafik intranet, dan batasi akses ke jaringan yang memang diizinkan.

Caller API mengirim bearer key sendiri melalui endpoint Nginx `/api/v1/ask`:

```bash
curl --fail-with-body -X POST http://localhost:8080/api/v1/ask \
  -H 'Authorization: Bearer GANTI_DENGAN_CALLER_KEY' \
  -H 'Content-Type: application/json' \
  -d '{"question":"Apa perkembangan terbaru energi surya?"}'
```

Sukses menghasilkan JSON berisi `answer` dan `citations` (array citation dengan `id`, `url`, dan `snippet`). Key hilang/tidak sah menghasilkan HTTP `401`; pertanyaan kosong menghasilkan HTTP `422`. Respons kegagalan agent menggunakan HTTP `500` dengan envelope `{"error":{"code":"internal_error","message":"Terjadi kesalahan internal."}}`. Endpoint health publik Nginx tersedia pada `/healthz`.

Jangan gunakan kredensial provider nyata dalam pengujian. Tes unit API memakai agent stub dan tidak menghubungi provider.

### Batasan keamanan

- Jaringan API tidak dipublikasikan langsung ke host; akses caller dilakukan lewat Nginx.
- `/api/` meneruskan header `Authorization` caller apa adanya, sedangkan `/ui-api/` menggunakan `UI_API_KEY` dari environment Nginx.
- Halaman UI merupakan halaman uji, bukan autentikasi pengguna. Semua pengakses dapat memakai akses API yang diberikan key UI.
- Jangan mengekspos port HTTP `8080` ke jaringan yang tidak tepercaya. HTTPS intranet wajib disediakan oleh reverse proxy atau terminasi TLS di depan Nginx.

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
