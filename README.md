# Agen Browsing Web dengan LangChain

Agen browsing web yang aman, modular, dan legal-compliant untuk menjawab pertanyaan pengguna dengan informasi terkini dari web — lengkap dengan sumber (citations).

## Fitur Utama

- **LLM dengan ModelHub (utama) / Azure OpenAI (fallback)** — `ChatOpenAI` OpenAI-compatible untuk ModelHub; `AzureChatOpenAI` hanya jika kredensial Azure diisi.
- **Pencarian Adaptif** — LLM memahami intent/wilayah, merumuskan query singkat, memilih kandidat relevan, dan menyusun pencarian lanjutan berdasarkan kekurangan bukti. Provider tetap SearXNG/DuckDuckGo.
- **HTTP-First Fetching** — `httpx` sebagai default; browser Selenium hanya jadi fallback untuk halaman JS-heavy.
- **Extract Konten Terstruktur** — Menggunakan `trafilatura` / `BeautifulSoup` untuk ekstrak judul, headings, dan teks utama.
- **Evidence & Citations Wajib** — Aplikasi mencari dan mengambil sumber sebelum LLM dipanggil. Jawaban harus mengutip bukti dengan `[1]`, `[2]`, dst.; array `citations` hanya berisi halaman yang berhasil diambil dan dikutip. Tanpa bukti atau referensi valid, aplikasi menolak menjawab, bukan mengarang sumber.
- **Safe Crawling** — Cek `robots.txt`, User-Agent transparan, rate limit per domain, dan stop pada 403/429.
- **Tool Execution Limits** — Counter tool calls reset per query, dengan batas maksimum tool calls & URLs per query.
- **CLI Interaktif + Mode Argumen** — Jalankan sekali dengan argumen atau pakai mode interaktif.

## Arsitektur

```
browsing_agent/
├── main.py              # Entry point CLI
├── api.py               # FastAPI app factory + endpoint
├── oplog.py             # Structured operational log
├── config.py            # Environment & settings (fail-fast)
├── agent/
│   ├── planner.py       # Per-run state: tool limits, evidence store
│   ├── research.py      # Riset iteratif: plan, select, review
│   └── synthesis.py     # Sintesis jawaban + validasi citations
├── tools/
│   ├── search.py        # Pluggable search (DDG/SearXNG) dengan retry & ranking
│   ├── fetch.py         # HTTP-first fetcher + Selenium fallback
│   └── extract.py       # Content extraction (trafilatura / BS4)
├── policy/
│   ├── guardrails.py    # Keyword & domain blocking
│   ├── robots.py        # robots.txt checker dengan cache
│   └── rate_limit.py    # Per-domain rate limiter
├── storage/
│   └── evidence.py      # Structured evidence store + dedup
├── evals/               # Evaluasi offline (schema, scoring, GEPA)
├── scripts/             # Utility manual
├── frontend/            # UI statis
├── nginx/               # Template ingress
└── tests/               # Unit tests (pytest)
```

## Cara Kerja

1. Pengguna memberikan pertanyaan via CLI (argumen atau interaktif).
2. LLM menyusun goal, constraints, dan beberapa reformulasi query.
3. Aplikasi mengambil pool kandidat (`SEARCH_CANDIDATE_LIMIT`, referensi 20). LLM mengevaluasi judul/URL/snippet sebelum seleksi (`MAX_SEARCH_RESULTS`); URL duplikat tidak di-fetch ulang dan domain beragam diprioritaskan.
4. Fetch tetap dibatasi kuota → guardrails → `robots.txt` → rate limit. Isi halaman dievaluasi: bukti melenceng dibuang, kekurangan bukti memicu query lanjutan sampai cukup atau kuota habis. Tidak ada bypass maupun daftar produk yang di-hardcode.
5. Fetcher menggunakan HTTP dulu; jika halaman JS-heavy, fallback ke Selenium.
6. Konten diekstrak secara terstruktur (judul, headings, teks) dan disimpan sebagai evidence.
7. LLM menyintesis hanya dari bukti yang terkumpul, tanpa bergantung pada tool-calling model. Nomor sumber diverifikasi dan disamakan dengan id pada array `citations`. Jika sumber tidak tersedia, hanya pesan ketidakcukupan bukti yang ditampilkan.

Tradeoff: riset menambah panggilan LLM untuk plan/seleksi/evaluasi. Pencarian tetap maksimum `MAX_TOOL_CALLS` per run, fetch maksimum `MAX_URLS_PER_QUERY`; bila bukti hanya parsial, jawaban harus menyatakan batasnya. Tidak menjamin hasil identik dengan Google.

### Flow Aplikasi

```mermaid
flowchart TD
    A["Pertanyaan CLI/API"] --> B{"Lolos guardrails?"}
    B -->|Tidak| R["Penolakan, tanpa klaim faktual"]
    B -->|Ya| P["Plan: intent, constraints, query"]
    P --> S["Search: pool kandidat dan seleksi relevansi"]
    S --> F["Fetch URL: kuota, guardrails, robots, rate limit"]
    F --> E["Ekstraksi dan evaluasi isi halaman"]
    E --> V{"Bukti relevan cukup?"}
    V -->|Belum, kuota tersedia| P
    V -->|Tidak ada bukti, kuota habis| R
    V -->|Parsial, kuota habis| L
    V -->|Ya| L["LLM menyintesis dari bukti yang diberikan"]
    L --> C{"Referensi inline valid?"}
    C -->|Tidak| R
    C -->|Ya| O["Jawaban dan citations dari halaman yang dikutip"]
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
| `API_ALLOWED_KEYS` | `replace-with-caller-key,replace-with-ui-key,replace-with-ui-to-api-key` | Caller key yang diterima; `UI_API_KEY` dan `UI_TO_API_KEY` wajib termasuk |
| `UI_API_KEY` | `replace-with-ui-key` | Key browser → Nginx; disuntik Nginx, bukan disimpan frontend |
| `UI_TO_API_KEY` | `replace-with-ui-to-api-key` | Key service Nginx → API |
| `MODELHUB_API_KEY` | — (wajib untuk provider utama) | Jika diisi, aplikasi memakai ModelHub sebagai LLM utama |
| `MODELHUB_BASE_URL` | `https://modelhub.example/v1` | Endpoint OpenAI-compatible ModelHub (dummy di template) |
| `MODELHUB_MODEL_NAME` | `your-model-name` | Nama model ModelHub (dummy di template) |
| `MODELHUB_USER_AGENT` | `curl/8.0` | Header User-Agent untuk koneksi LLM, terpisah dari crawler |
| `AZURE_OPENAI_ENDPOINT` | — (fallback Azure) | Endpoint Azure OpenAI |
| `AZURE_OPENAI_API_KEY` | — (fallback Azure) | API Key Azure OpenAI |
| `AZURE_OPENAI_DEPLOYMENT_NAME` | `your-azure-deployment` | Nama deployment model Azure (opsional) |
| `AZURE_OPENAI_PREVIEW_API_VERSION` | — (fallback Azure) | Versi API preview |
| `LLM_TEMPERATURE` | `0.7` | Temperature LLM (inferensi) |
| `LLM_MAX_TOKENS` | `1500` | Maksimum token jawaban LLM |
| `LLM_TIMEOUT` | `60` | Timeout request LLM (detik) |
| `LLM_MAX_RETRIES` | `2` | Retry otomatis request LLM |
| `MLFLOW_TRACING_ENABLED` | `true` | Aktifkan tracing LangChain dan span root request |
| `MLFLOW_TRACKING_URI` | `http://localhost:5000` | URI MLflow untuk proses di host, lihat `.env.example` |
| `MLFLOW_EXPERIMENT_ID` | `1` | ID experiment yang sudah ada; aplikasi tidak membuat experiment baru |
| `MLFLOW_CONTAINER_TRACKING_URI` | `http://host.docker.internal:5000` | API container menuju host via host-gateway (wajib di `.env` untuk Compose); allowlist server harus mengizinkan `host.docker.internal:5000` |
| `MLFLOW_HTTP_TIMEOUT` | `5` | Timeout REST call MLflow (detik) |
| `MLFLOW_PREFLIGHT_TIMEOUT` | `2.0` | Timeout pre-flight TCP check MLflow saat startup (detik) |
| `SEARCH_PROVIDER` | `searxng` | Provider pencarian: `duckduckgo` \| `searxng` |
| `SEARXNG_BASE_URL` | `http://searxng:8080` | Base URL SearXNG JSON API (wajib di `.env`) |
| `SEARCH_FALLBACK_ENABLED` | `true` | Fallback ke provider lain jika provider utama gagal |
| `SEARXNG_SECRET` | `replace-with-random-searxng-secret` | Secret session SearXNG (Compose) |
| `SEARXNG_CONTACT_URL` | `mailto:admin@example.com` | Kontak admin SearXNG (Compose) |
| `SEARXNG_SAFESEARCH` | `1` | Filter konten SearXNG: `0` off, `1` moderate, `2` strict |
| `SEARCH_TRUSTED_DOMAINS` | `.edu,.gov,...` | Domain kredibel untuk skor ranking (dicocokkan sebagai substring) |
| `SEARCH_TRUSTED_SCORE` / `SEARCH_DEFAULT_SCORE` | `10` / `1` | Skor ranking untuk domain kredibel dan domain biasa |
| `DDG_RETRY_BACKENDS` | `lite,lite,auto` | Urutan backend DuckDuckGo; `lite` dipetakan ke `duckduckgo` |
| `DDG_RETRY_DELAY_SECONDS` | `1.0` | Jeda dasar retry DDG; attempt ke-N menunggu `N * nilai` |
| `MAX_TOOL_CALLS` | `5` | Batas pemanggilan tool per query |
| `MAX_URLS_PER_QUERY` | `3` | Batas URL unik yang dicoba di-fetch per query; gagal tetap dihitung, URL yang sama tidak menambah kuota |
| `MAX_SEARCH_RESULTS` | `5` | Maksimum hasil search yang ditampilkan |
| `SEARCH_CANDIDATE_LIMIT` | `20` | Pool kandidat sebelum seleksi relevansi |
| `REQUEST_TIMEOUT` | `30` | Timeout HTTP request (detik) |
| `BROWSER_FALLBACK_ENABLED` | `true` | Aktifkan Selenium fallback |
| `FETCH_MAX_RETRIES` | `3` | Retry fetch HTTP dengan exponential backoff |
| `BROWSER_WAIT_TIMEOUT` | `10` | Timeout explicit wait Selenium (detik) |
| `FETCH_MAX_CONTENT_CHARS` | `3000` | Maksimum karakter konten yang dikirim ke LLM per halaman |
| `FETCH_BACKOFF_BASE_SECONDS` | `2.0` | Basis backoff eksponensial retry HTTP (`base ** attempt`) |
| `BROWSER_JS_HEAVY_MIN_CHARS` | `500` | Ambang teks HTML untuk memicu fallback Selenium |
| `FETCH_MAX_HEADINGS` | `5` | Jumlah heading yang disertakan dalam konteks LLM |
| `CHROME_BIN` / `CHROMEDRIVER_PATH` | — (opsional) | Path browser/driver di container; kosong = unduh via webdriver-manager |
| `USER_AGENT` | `BrowsingAgent/0.1` | User-Agent untuk pengambilan halaman web |
| `RATE_LIMIT_PER_DOMAIN_SECONDS` | `1.0` | Delay antar request ke domain sama (detik) |
| `ROBOTS_FAIL_OPEN` | `true` | `true`: izinkan jika robots.txt gagal di-fetch (non-404); `false`: tolak |
| `ROBOTS_CACHE_TTL_SECONDS` | `3600` | TTL cache robots.txt per domain (detik) |
| `GUARDRAIL_BLOCKED_DOMAINS` | `bca.co.id,...` | Domain sensitif yang ditolak (per label/subdomain) |
| `GUARDRAIL_BLOCKED_PATH_SEGMENTS` | `login,signin,auth,admin` | Segmen path yang ditolak |
| `EVIDENCE_HASH_CHARS` | `500` | Jumlah karakter main_text untuk hash dedup evidence |
| `EVIDENCE_SNIPPET_CHARS` | `300` | Panjang snippet pada citation/evidence |
| `RATE_LIMIT_REDIS_URL` | `redis://redis:6379/0` | URL Redis untuk rate limit per API key (wajib di `.env` untuk Compose); kosong = nonaktif khusus dev/CLI; Redis down = 503 |
| `RATE_LIMIT_REQUESTS_PER_MINUTE` | `10` | Maksimum request per API key per menit |
| `RATE_LIMIT_REDIS_TIMEOUT` | `1.0` | Timeout socket Redis (detik) |
| `RATE_LIMIT_WINDOW_SECONDS` | `60` | Ukuran window fixed-window rate limit (detik) |
| `RATE_LIMIT_BUCKET_PREFIX` | `ratelimit` | Prefix key bucket Redis |
| `RATE_LIMIT_KEY_HASH_CHARS` | `16` | Panjang hash identitas API key di Redis |
| `RATE_LIMIT_BUCKET_TTL_FACTOR` | `2` | TTL bucket = `window * faktor` |
| `MAX_CONCURRENT_AGENT_RUNS` | `4` | Maksimum agent yang berjalan konkuren; sisanya ditolak 429 |
| `MAX_QUESTION_LENGTH` | `2000` | Panjang maksimum pertanyaan (karakter) |
| `NGINX_PORT` | `8080` | Port host untuk Nginx (Compose); wajib di `.env` |
| `EVAL_TEMPERATURE` | `0` | Temperature evaluasi offline |
| `EVAL_LLM_MAX_RETRIES` | `0` | Retry LLM evaluasi (harus 0) |
| `EVAL_MAX_LM_CALLS` | `160` | Budget inference evaluasi |
| `EVAL_GEPA_METRIC_CALLS` | `24` | Budget metrik GEPA |
| `EVAL_SEED` | `17` | Seed evaluasi |

Untuk menjalankan contoh penggunaan API ModelHub secara langsung:
```bash
uv run scripts/modelhub.py
```

## API melalui Docker Compose

API dijalankan hanya di jaringan internal Compose; Nginx menerbitkan UI dan API pada port `8080` host. Buat `.env` lokal dari `.env.example`, lalu ganti semua nilai placeholder dengan nilai acak/rahasia milik Anda. `API_ALLOWED_KEYS` menerima daftar key caller yang dipisahkan koma; masukkan `UI_API_KEY` dan `UI_TO_API_KEY` ke daftar tersebut (boleh sama nilainya). Simpan `.env` dengan izin akses terbatas dan jangan commit atau membagikan isinya.

```bash
cp .env.example .env
# Edit .env: set API_ALLOWED_KEYS, UI_API_KEY, UI_TO_API_KEY yang unik serta kredensial provider.
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

Sukses menghasilkan JSON berisi `answer` dan `citations` (array citation dengan `id`, `url`, dan `snippet`). Key hilang/tidak sah menghasilkan HTTP `401`; pertanyaan kosong/terlalu panjang menghasilkan HTTP `422`; melewati rate limit HTTP `429` (`rate_limited` / `server_busy`); Redis tidak terjangkau HTTP `503` (`dependency_unavailable`, fail-closed — ADR-0006). Respons kegagalan agent menggunakan HTTP `500` dengan envelope `{"error":{"code":"internal_error","message":"Terjadi kesalahan internal."}}`. Endpoint health publik Nginx: `/healthz` (Nginx hidup) dan `/healthz/ready` (200 hanya jika API hidup). Metrik `/api/metrics` menyediakan `browsing_agent_requests_total{outcome}` dan ringkasan durasi (ADR-0010).

Jangan gunakan kredensial provider nyata dalam pengujian. Tes unit API memakai agent stub dan tidak menghubungi provider.

### Batasan keamanan

- Jaringan API tidak dipublikasikan langsung ke host; akses caller dilakukan lewat Nginx.
- `/api/` meneruskan header `Authorization` caller apa adanya, sedangkan `/ui-api/` menggunakan `UI_TO_API_KEY` dari environment Nginx (ADR-0009).
- Halaman UI merupakan halaman uji, bukan autentikasi pengguna. Semua pengakses dapat memakai akses API yang diberikan key UI.
- Jangan mengekspos port HTTP `8080` ke jaringan yang tidak tepercaya. HTTPS intranet wajib disediakan oleh reverse proxy atau terminasi TLS di depan Nginx.
- Trace MLflow `browsing_agent.request` menyimpan pertanyaan pengguna dan jawaban akhir mentah, serta metadata citation. Batasi akses dan retensi experiment sesuai kebijakan privasi data.

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
