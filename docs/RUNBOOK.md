# Runbook Operasional — browsing_agent

Panduan deploy dan pemulihan untuk operator. Bahasa: Indonesia.

## 1. Topologi Deploy

```
docker compose --profile prod up -d --build
```

Tanpa `--profile prod`, service `api` dan `nginx` tidak dijalankan (redis/searxng tetap).

| Service | Image | Jaringan | Fungsi |
|---------|-------|----------|--------|
| `api` | build lokal (Dockerfile) | backend, egress | FastAPI agent (port 8000, internal) |
| `nginx` | nginx:alpine + template | backend, egress | Ingress :8080 — UI statis, `/api/`, `/ui-api/` |
| `searxng` | searxng/searxng | egress | Search engine JSON API (metasearch Google/Bing/dll) |
| `redis` | redis:7-alpine | backend | Rate limit per API key (fail-closed) |

- Port publik hanya **:8080 (nginx)**. Port 8000 tidak dipublish (by design).
- `egress` = jaringan dengan akses internet; `backend` = internal-only.
- Nginx menyuntik `UI_TO_API_KEY` ke header `/ui-api/*` (ADR-0003, ADR-0009) — key tidak pernah ke browser.

## 2. Prosedur Deploy / Upgrade

1. `git pull` di mesin deploy.
2. `docker compose --profile prod up -d --build` (api di-rebuild; nginx re-resolve otomatis ≤10s).
3. Verifikasi: `curl http://localhost:8080/healthz/ready` → `ok` (proxy ke API); `curl http://localhost:8080/healthz`
   hanya menandakan Nginx hidup; `docker compose ps` semua Up.
4. Smoke: POST satu pertanyaan via `/ui-api/v1/ask` → jawaban + citations.

Rollback: `git checkout <tag sebelumnya>` lalu ulang langkah 2.

Staging di host yang sama: `NGINX_PORT=8081 docker compose --profile staging up -d --build`
lalu smoke ke `http://localhost:8081/` (`.env` sama; jangan jalankan bersamaan dengan prod —
port 8080 bentrok). Service tanpa profil (redis, searxng) tetap jalan.

## 3. Kredensial & Environment

Wajib di `.env` (gitignored): `MODELHUB_API_KEY` (atau kredensial Azure), `API_ALLOWED_KEYS`,
`UI_API_KEY`, `UI_TO_API_KEY`. `config.py` memvalidasi semuanya saat startup (fail-fast);
kedua key UI harus tercantum di `API_ALLOWED_KEYS`. Variabel operasional lain juga wajib — lihat `.env.example`.

Rotasi `UI_API_KEY` (browser) dan/atau `UI_TO_API_KEY` (service Nginx→API): ganti nilai di `.env`
→ `docker compose --profile prod up -d --force-recreate nginx api`.
Tidak perlu redeploy frontend (key tidak pernah ada di aset statis).

## 4. Observability

- **Health**: `GET /healthz` (Nginx hidup) dan `GET /healthz/ready` (200 hanya jika API hidup — dipakai healthcheck container); `docker compose ps`.
- **Tracing**: MLflow di `MLFLOW_TRACKING_URI` (nilai intranet ada di `.env`),
  experiment `browsing-agent-dev`. Setiap run agent menghasilkan trace; span `search_tool`
  memiliki atribut `search.provider` dan `search.fallback_used`.
- **Log operasional**: stderr container api berisi JSON lines dari `oplog`
  (`api.request` per request: `outcome`, `status`, `duration_ms`; `rate_limit.redis_error`):
  `docker compose logs api | grep '"event"'`.
- **Metrik**: `curl http://localhost:8080/api/metrics` (atau langsung `api:8000/metrics`)
  → counter `browsing_agent_requests_total{outcome}` + ringkasan durasi (ADR-0010).
- **Log aplikasi**: `docker compose logs api` (UX print + uvicorn access log).

## 5. Kegagalan Umum & Pemulihan

### DuckDuckGo diblokir DNS (filter "Trust Positive")
Gejala: search gagal dengan TLS/hostname error; log `[Search Tool]` error.
Aksi: set `SEARCH_PROVIDER=searxng` di `.env` (atau biarkan fallback aktif —
`SEARCH_FALLBACK_ENABLED=true` default). Verifikasi SearXNG:
`docker compose exec api curl -s "http://searxng:8080/search?q=test&format=json" | head -c 200`.

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
