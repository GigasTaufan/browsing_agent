# Runbook Operasional — browsing_agent

Panduan deploy dan pemulihan untuk operator. Bahasa: Indonesia.

## 1. Topologi Deploy

```
docker compose up -d --build
```

Semua service aktif pada `docker compose up`; tidak perlu mengaktifkan profile.
Untuk staging sebagai stack terpisah di host yang sama, gunakan project name dan port berbeda:
`COMPOSE_PROJECT_NAME=browsing-agent-staging NGINX_PORT=8081 docker compose up -d --build`.
Hentikan staging dengan `COMPOSE_PROJECT_NAME=browsing-agent-staging docker compose down`.

| Service | Image | Jaringan | Fungsi |
|---------|-------|----------|--------|
| `api` | build lokal (Dockerfile) | backend, egress | FastAPI agent (port 8000, internal) |
| `nginx` | nginx:alpine + template | backend, egress | Ingress :8080 — UI statis, `/api/`, `/ui-api/` |
| `searxng` | searxng/searxng | egress | Search engine JSON API (metasearch Google/Bing/dll) |
| `redis` | redis:7-alpine | backend | Rate limit per API key (fail-closed) |

- Port host mengikuti `NGINX_PORT` (template 8080; staging 8081). Port 8000 tidak dipublish (by design).
- `egress` = jaringan dengan akses internet; `backend` = internal-only.
- Nginx menyuntik `UI_TO_API_KEY` ke header `/ui-api/*` (ADR-0003, ADR-0009) — key tidak pernah ke browser.

## 2. Prosedur Deploy / Upgrade

1. `git pull` di mesin deploy.
2. `docker compose up -d --build` (api di-rebuild; nginx re-resolve otomatis ≤10s).
3. Verifikasi: `curl http://localhost:8080/healthz/ready` → `ok` (proxy ke API); `curl http://localhost:8080/healthz`
   hanya menandakan Nginx hidup; `docker compose ps` semua Up.
4. Smoke: POST satu pertanyaan via `/ui-api/v1/ask` → jawaban + citations.

Rollback: `git checkout <tag sebelumnya>` lalu ulang langkah 2.

Staging terpisah di host yang sama menggunakan perintah di atas; smoke ke `http://localhost:8081/`.
Project name berbeda memberi container/network terpisah. `.env` shared; gunakan key staging berbeda bila
perlu isolasi akses lebih ketat.

Mount aset memakai SELinux shared `:z`. Tes Nginx hanya me-mount salinan sementara;
menjalankan pytest tidak mengganti label frontend/config stack lokal yang sedang berjalan.

## 3. Kredensial & Environment

Wajib di `.env` (gitignored): `MODELHUB_API_KEY` (atau kredensial Azure), `API_ALLOWED_KEYS`,
`UI_API_KEY`, `UI_TO_API_KEY`. `config.py` memvalidasi semuanya saat startup (fail-fast);
kedua key UI harus tercantum di `API_ALLOWED_KEYS`. Variabel operasional lain juga wajib — lihat `.env.example`.

Rotasi `UI_API_KEY` (browser) dan/atau `UI_TO_API_KEY` (service Nginx→API): ganti nilai di `.env`
→ `docker compose up -d --force-recreate nginx api`.
Tidak perlu redeploy frontend (key tidak pernah ada di aset statis).

## 4. Observability

- **Health**: `GET /healthz` (Nginx hidup) dan `GET /healthz/ready` (200 hanya jika API hidup — dipakai healthcheck container); `docker compose ps`.
- **Tracing**: experiment MLflow yang sudah ada dipilih lewat `MLFLOW_EXPERIMENT_ID` (default template `1`); aplikasi tidak membuat experiment.
  Proses host memakai `MLFLOW_TRACKING_URI=http://localhost:5000`. `MLFLOW_CONTAINER_TRACKING_URI` harus alamat yang dapat dijangkau container: `host.docker.internal:5000` atau IP/hostname server MLflow. API Compose memakai `MLFLOW_CONTAINER_TRACKING_URI=http://host.docker.internal:5000`; alias `host.docker.internal:host-gateway` disetel Compose, dan server MLflow harus mengizinkan `host.docker.internal:5000` di `MLFLOW_SERVER_ALLOWED_HOSTS`.
  Setiap request agent menghasilkan satu root span `browsing_agent.request` dengan child spans LangGraph/model dan `browse_tool`. Atribut `search.provider`/`search.fallback_used` ditempel pada trace aktif; search bukan span tersendiri.
  Inputs/outputs root berisi teks pertanyaan dan jawaban akhir mentah (selain jumlah karakter dan metadata citation). Batasi akses dan retensi trace karena dapat memuat data pengguna.
- **Log operasional**: stderr container api berisi JSON lines dari `oplog`
  (`api.request` per request: `outcome`, `status`, `duration_ms`; `rate_limit.redis_error`):
  `docker compose logs api | grep '"event"'`.
- **Metrik**: `curl http://localhost:8080/api/metrics` (route khusus di Nginx, bukan prefix `/api/`)
  → counter `browsing_agent_requests_total{outcome}` + ringkasan durasi (ADR-0010).
- **Log aplikasi**: `docker compose logs api` (UX print + uvicorn access log).

## 5. Kegagalan Umum & Pemulihan

### DuckDuckGo diblokir DNS (filter "Trust Positive")
Gejala: search gagal dengan TLS/hostname error; log `[Search Tool]` error.
Aksi: set `SEARCH_PROVIDER=searxng` di `.env` (atau biarkan fallback aktif —
`SEARCH_FALLBACK_ENABLED` di `.env`, template true). Verifikasi SearXNG:
`docker compose exec -T api python -c "import urllib.request; print(urllib.request.urlopen('http://searxng:8080/search?q=test&format=json', timeout=5).read(200).decode())"`.

### Redis down
Gejala: `rate_limit.redis_error` di log; `POST /api/v1/ask` membalas **503**
`dependency_unavailable` (fail-closed, ADR-0006). `/healthz` tetap 200.
Aksi: `docker compose restart redis`.

### Metrik menunjukkan 503 dependency_unavailable
Gejala: Redis tidak terjangkau; API fail-closed. Aksi: `docker compose restart redis`
(lihat bagian Redis down).

### Nginx 502 setelah rebuild api
Gejala: 502 beberapa detik setelah `docker compose up -d --build api`.
Normal: resolver Docker DNS re-resolve ≤10s (valid=10s) — tunggu saja.
Jika 502 persisten: `docker compose restart nginx`, cek `docker compose logs nginx`.

### MLflow unreachable
Gejala: log `[Tracing]` error saat startup; traces tidak muncul.
Aksi: tracing bersifat non-fatal — agent tetap jalan. Cek konektivitas
`MLFLOW_TRACKING_URI`; atau set `MLFLOW_TRACING_ENABLED=false` untuk mematikan.

### 429 dari API
- `rate_limited`: key tersebut mencapai `RATE_LIMIT_REQUESTS_PER_MINUTE` (default 10/menit) — naikkan limit di `.env` jika perlu.
- `server_busy`: konkurensi penuh (`MAX_CONCURRENT_AGENT_RUNS`, default 4) — naikkan hanya jika resource memadai (setiap run memakai Chrome/LLM call).

### Selenium/Chrome di container
Gejala: fallback browser gagal; `[Browser Fetcher]` error.
Aksi: pastikan image api di-build dari Dockerfile terbaru (chromium + chromedriver
pre-installed). Fallback browser hanya untuk halaman JS-heavy — mayoritas fetch via HTTP.

### robots.txt error
Dikendalikan `ROBOTS_FAIL_OPEN` (ADR-0004): `true` (default) = izinkan saat robots.txt
gagal di-fetch (non-404); `false` = tolak. 404 selalu diizinkan (RFC 9309).

## 6. Laporan Kualitas

Quality gate wajib hijau sebelum deploy:
```
uv run --no-sync ruff check . && uv run --no-sync ruff format --check . \
  && uv run --no-sync mypy . \
  && uv run --no-sync python -m pytest tests/ -q --cov --cov-fail-under=83
```
CI (GitHub Actions / GitLab CI) menjalankan hal yang sama pada setiap push.
