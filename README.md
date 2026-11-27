# Agen Browsing Web dengan LangChain

Agen browsing web yang aman, modular, dan legal-compliant untuk menjawab pertanyaan pengguna dengan informasi terkini dari web — lengkap dengan sumber (citations).

## Fitur Utama

- **LLM dengan ModelHub (utama) / Azure OpenAI (fallback)** — `ChatOpenAI` OpenAI-compatible untuk ModelHub; `AzureChatOpenAI` hanya jika kredensial Azure diisi.
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

### Flow Aplikasi

```mermaid
flowchart TD
    A["Pertanyaan pengguna<br/>(CLI argumen / interaktif / API)"] --> B{"Query lolos<br/>guardrails?"}
    B -->|Diblokir| C["Kembalikan alasan<br/>penolakan"]
    B -->|Lolos| D["Agent loop (LangChain)<br/>LLM: ModelHub (utama) / Azure OpenAI (fallback)"]
    D --> E{"Kuota tool call<br/>atau URL habis?"}
    E -->|Ya| K["Susun jawaban akhir"]
    E -->|Tidak| F{"LLM memilih tool"}
    F -->|search_tool| G["DuckDuckGo search<br/>rank + dedup hasil"]
    F -->|browse_tool| H{"URL lolos guardrails,<br/>robots.txt, rate limit?"}
    H -->|Tidak| D
    H -->|Ya| I["Fetch via httpx<br/>(HTTP-first)"]
    I --> J{"Halaman JS-heavy?"}
    J -->|Ya| J2["Fallback Selenium<br/>(headless Chrome)"]
    J2 --> L["Extract konten<br/>(trafilatura / BeautifulSoup)"]
    J -->|Tidak| L
    L --> M["Simpan ke EvidenceStore<br/>dedup URL + content hash"]
    G --> D
    M --> D
    K --> N["Output: jawaban + citations<br/>(CLI / JSON)"]
```

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
# Edit .env dan isi MODELHUB_API_KEY Anda (provider utama)
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

Semua parameter operasional wajib ada di `.env` — salin dari `.env.example`. `config.py` tidak menyimpan nilai default; variabel yang hilang membuat startup gagal cepat (fail-fast) dengan pesan error yang menyebut nama variabelnya. Kolom "Default" di bawah adalah nilai referensi dari `.env.example`.

| Variabel | Default | Keterangan |
|----------|---------|------------|
| `MODELHUB_API_KEY` | — (wajib untuk provider utama) | Jika diisi, aplikasi memakai ModelHub sebagai LLM utama |
| `MODELHUB_BASE_URL` | `https://api-modelhub.aiplayground.id/v1` | Endpoint OpenAI-compatible ModelHub |
| `MODELHUB_MODEL_NAME` | `gpt-4o-mini` | Nama model ModelHub |
| `AZURE_OPENAI_ENDPOINT` | — (fallback Azure) | Endpoint Azure OpenAI |
| `AZURE_OPENAI_API_KEY` | — (fallback Azure) | API Key Azure OpenAI |
| `AZURE_OPENAI_DEPLOYMENT_NAME` | `gpt-4o-mini` | Nama deployment model Azure |
| `AZURE_OPENAI_PREVIEW_API_VERSION` | — (fallback Azure) | Versi API preview |
| `LLM_TEMPERATURE` | `0.7` | Temperature LLM (inferensi) |
| `LLM_MAX_TOKENS` | `1500` | Maksimum token jawaban LLM |
| `LLM_TIMEOUT` | `60` | Timeout request LLM (detik) |
| `LLM_MAX_RETRIES` | `2` | Retry otomatis request LLM |
| `MLFLOW_TRACING_ENABLED` | `true` | Aktifkan MLflow GenAI tracing untuk LangChain |
| `MLFLOW_TRACKING_URI` | URL server MLflow internal (lihat `.env.example`) | URI server MLflow untuk tracing |
| `MLFLOW_EXPERIMENT_NAME` | `browsing-agent-dev` | Nama experiment MLflow |
| `MLFLOW_HTTP_TIMEOUT` | `5` | Timeout REST call MLflow (detik) |
| `MLFLOW_PREFLIGHT_TIMEOUT` | `2.0` | Timeout pre-flight TCP check MLflow saat startup (detik) |
| `SEARCH_PROVIDER` | `duckduckgo` | Provider pencarian: `duckduckgo` \| `searxng` |
| `SEARXNG_BASE_URL` | `http://searxng:8080` (di Compose) | Base URL SearXNG JSON API |
| `SEARCH_FALLBACK_ENABLED` | `true` | Fallback ke provider lain jika provider utama gagal |
| `MAX_TOOL_CALLS` | `5` | Batas pemanggilan tool per query |
| `MAX_URLS_PER_QUERY` | `3` | Batas URL unik yang dicoba di-fetch per query; gagal tetap dihitung, URL yang sama tidak menambah kuota |
| `MAX_SEARCH_RESULTS` | `5` | Maksimum hasil search yang ditampilkan |
| `REQUEST_TIMEOUT` | `30` | Timeout HTTP request (detik) |
| `BROWSER_FALLBACK_ENABLED` | `true` | Aktifkan Selenium fallback |
| `FETCH_MAX_RETRIES` | `3` | Retry fetch HTTP dengan exponential backoff |
| `BROWSER_WAIT_TIMEOUT` | `10` | Timeout explicit wait Selenium (detik) |
| `FETCH_MAX_CONTENT_CHARS` | `3000` | Maksimum karakter konten yang dikirim ke LLM per halaman |
| `USER_AGENT` | `BrowsingAgent/0.1` | User-Agent untuk pengambilan halaman web |
| `RATE_LIMIT_PER_DOMAIN_SECONDS` | `1.0` | Delay antar request ke domain sama (detik) |
| `ROBOTS_FAIL_OPEN` | `true` | `true`: izinkan jika robots.txt gagal di-fetch (non-404); `false`: tolak |
| `ROBOTS_CACHE_TTL_SECONDS` | `3600` | TTL cache robots.txt per domain (detik) |
| `CHUNK_SIZE` | `2000` | Ukuran chunk konten halaman |
| `RATE_LIMIT_REDIS_URL` | `redis://redis:6379/0` (di Compose) | URL Redis untuk rate limit per API key; kosong = nonaktif (dev/CLI); Redis down = 503 |
| `RATE_LIMIT_REQUESTS_PER_MINUTE` | `10` | Maksimum request per API key per menit |
| `RATE_LIMIT_REDIS_TIMEOUT` | `1.0` | Timeout socket Redis (detik) |
| `RATE_LIMIT_WINDOW_SECONDS` | `60` | Ukuran window fixed-window rate limit (detik) |
| `MAX_CONCURRENT_AGENT_RUNS` | `4` | Maksimum agent yang berjalan konkuren; sisanya ditolak 429 |
| `MAX_QUESTION_LENGTH` | `2000` | Panjang maksimum pertanyaan (karakter) |

Untuk menjalankan contoh penggunaan API ModelHub secara langsung:
```bash
uv run scripts/modelhub.py
```

## API melalui Docker Compose

API dijalankan hanya di jaringan internal Compose; Nginx menerbitkan UI dan API pada port `8080` host. Buat `.env` lokal dari `.env.example`, lalu ganti semua nilai placeholder dengan nilai acak/rahasia milik Anda. `API_ALLOWED_KEYS` menerima daftar key caller yang dipisahkan koma; masukkan `UI_API_KEY` dan `UI_TO_API_KEY` ke daftar tersebut (boleh sama nilainya). Simpan `.env` dengan izin akses terbatas dan jangan commit atau membagikan isinya.

```bash
cp .env.example .env
# Edit .env: set API_ALLOWED_KEYS, UI_API_KEY, UI_TO_API_KEY yang unik serta kredensial provider.
docker compose --profile prod up --build -d
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

Sukses menghasilkan JSON berisi `answer` dan `citations` (array citation dengan `id`, `url`, dan `snippet`). Key hilang/tidak sah menghasilkan HTTP `401`; pertanyaan kosong/terlalu panjang menghasilkan HTTP `422`; melewati rate limit HTTP `429` (`rate_limited` / `server_busy`); Redis tidak terjangkau HTTP `503` (`dependency_unavailable`, fail-closed — ADR-0006). Respons kegagalan agent menggunakan HTTP `500` dengan envelope `{"error":{"code":"internal_error","message":"Terjadi kesalahan internal."}}`. Endpoint health publik Nginx: `/healthz` (Nginx hidup) dan `/healthz/ready` (200 hanya jika API hidup). Metrik `/api/metrics` menyediakan `browsing_agent_requests_total{outcome}` dan ringkasan durasi (ADR-0010).

Jangan gunakan kredensial provider nyata dalam pengujian. Tes unit API memakai agent stub dan tidak menghubungi provider.

### Batasan keamanan

- Jaringan API tidak dipublikasikan langsung ke host; akses caller dilakukan lewat Nginx.
- `/api/` meneruskan header `Authorization` caller apa adanya, sedangkan `/ui-api/` menggunakan `UI_TO_API_KEY` dari environment Nginx (ADR-0009).
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
| Search | `ddgs` (DuckDuckGo) / SearXNG JSON |
| HTTP Fetch | `httpx` |
| Browser Fallback | `selenium` + `webdriver-manager` |
| Content Extraction | `trafilatura`, `beautifulsoup4`, `lxml` |
| Testing | `pytest` |
| Environment | `python-dotenv` |
