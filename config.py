"""
Konfigurasi utama aplikasi Browsing Agent.
Membaca dan memvalidasi variabel lingkungan dari .env secara fail-fast.
Tidak ada nilai default hardcoded: semua parameter operasional wajib di .env
(salin dari .env.example). Variabel opsional (kredensial/feature toggle)
dibaca apa adanya dan divalidasi saat dipakai.
"""

import os

from dotenv import load_dotenv

# Muat variabel dari .env saat modul di-import
load_dotenv()


def _env_int(name: str) -> int:
    """Baca variabel lingkungan integer yang wajib terisi."""
    raw = os.getenv(name, "").strip()
    if not raw:
        raise ValueError(f"Variabel lingkungan {name} wajib diisi di .env.")
    try:
        return int(raw)
    except ValueError:
        raise ValueError(
            f"Variabel lingkungan {name} harus berupa integer, ditemukan: {raw!r}."
        ) from None


def _env_float(name: str) -> float:
    """Baca variabel lingkungan float yang wajib terisi."""
    raw = os.getenv(name, "").strip()
    if not raw:
        raise ValueError(f"Variabel lingkungan {name} wajib diisi di .env.")
    try:
        return float(raw)
    except ValueError:
        raise ValueError(
            f"Variabel lingkungan {name} harus berupa angka, ditemukan: {raw!r}."
        ) from None


def _env_bool(name: str) -> bool:
    """Baca variabel lingkungan boolean ('true'/'false', case-insensitive) yang wajib terisi."""
    raw = os.getenv(name, "").strip().lower()
    if raw in ("true", "1", "yes"):
        return True
    if raw in ("false", "0", "no"):
        return False
    raise ValueError(f"Variabel lingkungan {name} harus 'true' atau 'false', ditemukan: {raw!r}.")


def _env_csv(name: str) -> tuple[str, ...]:
    """Baca variabel lingkungan daftar dipisah koma yang wajib terisi."""
    raw = os.getenv(name, "").strip()
    if not raw:
        raise ValueError(f"Variabel lingkungan {name} wajib diisi di .env.")
    values = tuple(value.strip() for value in raw.split(",") if value.strip())
    if not values:
        raise ValueError(f"Variabel lingkungan {name} wajib berisi minimal satu nilai.")
    return values


def _require(names: list[str]) -> None:
    """Pastikan semua variabel wajib terisi; kumpulkan yang hilang dalam satu pesan."""
    missing = [name for name in names if not os.getenv(name, "").strip()]
    if missing:
        raise ValueError(
            "Variabel lingkungan wajib belum diisi di .env: "
            f"{', '.join(missing)}. Salin dari .env.example lalu sesuaikan nilainya."
        )


# --- Azure OpenAI (fallback, opsional; divalidasi saat dipakai) ---
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_DEPLOYMENT_NAME = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")
AZURE_OPENAI_PREVIEW_API_VERSION = os.getenv("AZURE_OPENAI_PREVIEW_API_VERSION")

# --- ModelHub (provider utama; divalidasi saat dipakai) ---
MODELHUB_API_KEY = os.getenv("MODELHUB_API_KEY")
MODELHUB_BASE_URL = os.getenv("MODELHUB_BASE_URL")
MODELHUB_MODEL_NAME = os.getenv("MODELHUB_MODEL_NAME")

# --- Search Provider ---
# SEARXNG_BASE_URL opsional; wajib jika SEARCH_PROVIDER=searxng (divalidasi saat dipakai).
SEARXNG_BASE_URL = os.getenv("SEARXNG_BASE_URL")

# --- MLflow GenAI Tracing ---
# MLFLOW_TRACKING_URI dan kawan-kawannya hanya wajib jika tracing aktif.
MLFLOW_TRACKING_URI = os.getenv("MLFLOW_TRACKING_URI")
MLFLOW_EXPERIMENT_ID = os.getenv("MLFLOW_EXPERIMENT_ID")

# --- API Inbound Limits ---
# Rate limit per API key via Redis; kosong = dinonaktifkan (dev/CLI). Redis down = 503 (ADR-0006).
RATE_LIMIT_REDIS_URL = os.getenv("RATE_LIMIT_REDIS_URL")

# Validasi keberadaan semua variabel operasional wajib (fail-fast, satu pesan untuk semua).
_require(
    [
        "LLM_TEMPERATURE",
        "LLM_MAX_TOKENS",
        "LLM_TIMEOUT",
        "LLM_MAX_RETRIES",
        "MAX_TOOL_CALLS",
        "MAX_URLS_PER_QUERY",
        "MAX_SEARCH_RESULTS",
        "SEARCH_CANDIDATE_LIMIT",
        "REQUEST_TIMEOUT",
        "BROWSER_FALLBACK_ENABLED",
        "FETCH_MAX_RETRIES",
        "BROWSER_WAIT_TIMEOUT",
        "FETCH_MAX_CONTENT_CHARS",
        "USER_AGENT",
        "RATE_LIMIT_PER_DOMAIN_SECONDS",
        "ROBOTS_FAIL_OPEN",
        "ROBOTS_CACHE_TTL_SECONDS",
        "SEARCH_PROVIDER",
        "SEARCH_FALLBACK_ENABLED",
        "MLFLOW_TRACING_ENABLED",
        "CHUNK_SIZE",
        "RATE_LIMIT_REQUESTS_PER_MINUTE",
        "RATE_LIMIT_REDIS_TIMEOUT",
        "RATE_LIMIT_WINDOW_SECONDS",
        "MAX_CONCURRENT_AGENT_RUNS",
        "MAX_QUESTION_LENGTH",
        "MODELHUB_USER_AGENT",
        "SEARCH_TRUSTED_DOMAINS",
        "SEARCH_TRUSTED_SCORE",
        "SEARCH_DEFAULT_SCORE",
        "SEARCH_LOG_TOP_RESULTS",
        "DDG_RETRY_BACKENDS",
        "DDG_RETRY_DELAY_SECONDS",
        "SEARXNG_SAFESEARCH",
        "FETCH_BACKOFF_BASE_SECONDS",
        "BROWSER_JS_HEAVY_MIN_CHARS",
        "FETCH_MAX_HEADINGS",
        "EVIDENCE_HASH_CHARS",
        "EVIDENCE_SNIPPET_CHARS",
        "RATE_LIMIT_KEY_HASH_CHARS",
        "RATE_LIMIT_BUCKET_PREFIX",
        "RATE_LIMIT_BUCKET_TTL_FACTOR",
        "GUARDRAIL_BLOCKED_DOMAINS",
        "GUARDRAIL_BLOCKED_PATH_SEGMENTS",
    ]
)

# --- API access (auth caller + Nginx UI) ---
# UI_API_KEY wajib ikut di API_ALLOWED_KEYS agar hanya caller terdaftar yang lolos auth.
API_ALLOWED_KEYS = tuple(
    key.strip() for key in os.getenv("API_ALLOWED_KEYS", "").split(",") if key.strip()
)
UI_API_KEY = os.getenv("UI_API_KEY", "").strip()
UI_TO_API_KEY = os.getenv("UI_TO_API_KEY", "").strip()
if not API_ALLOWED_KEYS:
    raise ValueError(
        "Variabel lingkungan wajib belum diisi di .env: API_ALLOWED_KEYS. "
        "Salin dari .env.example lalu sesuaikan nilainya."
    )
if not UI_API_KEY:
    raise ValueError(
        "Variabel lingkungan wajib belum diisi di .env: UI_API_KEY. "
        "Salin dari .env.example lalu sesuaikan nilainya."
    )
# Key service Nginx -> API (ADR-0009); boleh sama dengan UI_API_KEY untuk deployment kecil.
UI_TO_API_KEY = UI_TO_API_KEY or UI_API_KEY
if UI_API_KEY not in API_ALLOWED_KEYS or UI_TO_API_KEY not in API_ALLOWED_KEYS:
    raise ValueError(
        "UI_API_KEY dan UI_TO_API_KEY harus tercantum di API_ALLOWED_KEYS agar Nginx "
        "dapat memanggil API."
    )

# --- LLM (provider utama ModelHub; Azure hanya fallback) ---
# Keduanya opsional satu per satu, tetapi minimal satu provider harus lengkap.
if MODELHUB_API_KEY:
    if not MODELHUB_BASE_URL or not MODELHUB_MODEL_NAME:
        raise ValueError(
            "MODELHUB_BASE_URL dan MODELHUB_MODEL_NAME wajib diisi jika MODELHUB_API_KEY digunakan."
        )
elif not (AZURE_OPENAI_API_KEY and AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_PREVIEW_API_VERSION):
    raise ValueError(
        "Tidak ada provider LLM terkonfigurasi. Isi MODELHUB_API_KEY (beserta "
        "MODELHUB_BASE_URL & MODELHUB_MODEL_NAME) atau kredensial Azure OpenAI "
        "(AZURE_OPENAI_API_KEY, AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_PREVIEW_API_VERSION)."
    )

# --- Search Provider ---
# Nilai valid divalidasi saat startup (SEARXNG_BASE_URL opsional, divalidasi saat dipakai).
_SEARCH_PROVIDERS = ("duckduckgo", "searxng")
SEARCH_PROVIDER = os.getenv("SEARCH_PROVIDER", "").strip().lower()
if SEARCH_PROVIDER not in _SEARCH_PROVIDERS:
    raise ValueError(
        f"SEARCH_PROVIDER harus salah satu dari {', '.join(_SEARCH_PROVIDERS)}, "
        f"ditemukan: {SEARCH_PROVIDER!r}."
    )

# --- LLM (parameter inferensi) ---
LLM_TEMPERATURE = _env_float("LLM_TEMPERATURE")
LLM_MAX_TOKENS = _env_int("LLM_MAX_TOKENS")
LLM_TIMEOUT = _env_int("LLM_TIMEOUT")
LLM_MAX_RETRIES = _env_int("LLM_MAX_RETRIES")
# Header HTTP untuk koneksi ke ModelHub (bukan USER_AGENT crawler).
MODELHUB_USER_AGENT = os.getenv("MODELHUB_USER_AGENT", "").strip()

# --- Tool Limits ---
MAX_TOOL_CALLS = _env_int("MAX_TOOL_CALLS")
MAX_URLS_PER_QUERY = _env_int("MAX_URLS_PER_QUERY")
MAX_SEARCH_RESULTS = _env_int("MAX_SEARCH_RESULTS")
# Pool kandidat dievaluasi sebelum dipotong menjadi MAX_SEARCH_RESULTS.
SEARCH_CANDIDATE_LIMIT = _env_int("SEARCH_CANDIDATE_LIMIT")
if SEARCH_CANDIDATE_LIMIT < MAX_SEARCH_RESULTS:
    raise ValueError("SEARCH_CANDIDATE_LIMIT harus >= MAX_SEARCH_RESULTS.")

# --- Fetching ---
REQUEST_TIMEOUT = _env_int("REQUEST_TIMEOUT")
BROWSER_FALLBACK_ENABLED = _env_bool("BROWSER_FALLBACK_ENABLED")
FETCH_MAX_RETRIES = _env_int("FETCH_MAX_RETRIES")
BROWSER_WAIT_TIMEOUT = _env_int("BROWSER_WAIT_TIMEOUT")
FETCH_MAX_CONTENT_CHARS = _env_int("FETCH_MAX_CONTENT_CHARS")
# Backoff eksponensial: base ** attempt (detik).
FETCH_BACKOFF_BASE_SECONDS = _env_float("FETCH_BACKOFF_BASE_SECONDS")
# Halaman HTML dengan teks lebih pendek dari ini dianggap JS-heavy.
BROWSER_JS_HEAVY_MIN_CHARS = _env_int("BROWSER_JS_HEAVY_MIN_CHARS")
# Jumlah heading yang disertakan dalam konteks LLM.
FETCH_MAX_HEADINGS = _env_int("FETCH_MAX_HEADINGS")
# Path browser di image/container; kosong = unduh lewat webdriver-manager.
CHROME_BIN = os.getenv("CHROME_BIN") or None
CHROMEDRIVER_PATH = os.getenv("CHROMEDRIVER_PATH") or None

# --- Safe Crawling ---
USER_AGENT = os.getenv("USER_AGENT", "").strip()
RATE_LIMIT_PER_DOMAIN_SECONDS = _env_float("RATE_LIMIT_PER_DOMAIN_SECONDS")
# True: robots.txt gagal di-fetch (non-404) => izinkan. False: tolak (fail-closed).
ROBOTS_FAIL_OPEN = _env_bool("ROBOTS_FAIL_OPEN")
ROBOTS_CACHE_TTL_SECONDS = _env_int("ROBOTS_CACHE_TTL_SECONDS")

# --- Guardrails ---
# Domain sensitif dicocokkan per label; path login/auth ditolak.
GUARDRAIL_BLOCKED_DOMAINS = _env_csv("GUARDRAIL_BLOCKED_DOMAINS")
GUARDRAIL_BLOCKED_PATH_SEGMENTS = _env_csv("GUARDRAIL_BLOCKED_PATH_SEGMENTS")

SEARCH_FALLBACK_ENABLED = _env_bool("SEARCH_FALLBACK_ENABLED")

# --- Search Tuning ---
# Domain yang dianggap kredibel (cocokkan substring) dan skor ranking-nya.
SEARCH_TRUSTED_DOMAINS = _env_csv("SEARCH_TRUSTED_DOMAINS")
SEARCH_TRUSTED_SCORE = _env_int("SEARCH_TRUSTED_SCORE")
SEARCH_DEFAULT_SCORE = _env_int("SEARCH_DEFAULT_SCORE")
# Jumlah link teratas yang dicetak ke log pencarian.
SEARCH_LOG_TOP_RESULTS = _env_int("SEARCH_LOG_TOP_RESULTS")
# Urutan backend DuckDuckGo: "lite" dipetakan ke backend ddgs "duckduckgo".
DDG_RETRY_BACKENDS = _env_csv("DDG_RETRY_BACKENDS")
DDG_RETRY_DELAY_SECONDS = _env_float("DDG_RETRY_DELAY_SECONDS")
# Filter konten SearXNG: 0=off, 1=moderate, 2=strict.
SEARXNG_SAFESEARCH = _env_int("SEARXNG_SAFESEARCH")
if SEARXNG_SAFESEARCH not in (0, 1, 2):
    raise ValueError("SEARXNG_SAFESEARCH harus 0, 1, atau 2.")

# --- MLflow GenAI Tracing ---
MLFLOW_TRACING_ENABLED = _env_bool("MLFLOW_TRACING_ENABLED")
MLFLOW_HTTP_TIMEOUT: int | None = None
MLFLOW_PREFLIGHT_TIMEOUT: float | None = None
if MLFLOW_TRACING_ENABLED:
    _require(
        [
            "MLFLOW_TRACKING_URI",
            "MLFLOW_EXPERIMENT_ID",
            "MLFLOW_HTTP_TIMEOUT",
            "MLFLOW_PREFLIGHT_TIMEOUT",
        ]
    )
    MLFLOW_HTTP_TIMEOUT = _env_int("MLFLOW_HTTP_TIMEOUT")
    MLFLOW_PREFLIGHT_TIMEOUT = _env_float("MLFLOW_PREFLIGHT_TIMEOUT")

# --- Content Extraction ---
CHUNK_SIZE = _env_int("CHUNK_SIZE")
# Jumlah karakter main_text untuk hash dedup dan snippet citation.
EVIDENCE_HASH_CHARS = _env_int("EVIDENCE_HASH_CHARS")
EVIDENCE_SNIPPET_CHARS = _env_int("EVIDENCE_SNIPPET_CHARS")

# --- API Inbound Limits ---
RATE_LIMIT_REQUESTS_PER_MINUTE = _env_int("RATE_LIMIT_REQUESTS_PER_MINUTE")
RATE_LIMIT_REDIS_TIMEOUT = _env_float("RATE_LIMIT_REDIS_TIMEOUT")
RATE_LIMIT_WINDOW_SECONDS = _env_int("RATE_LIMIT_WINDOW_SECONDS")
# Prefix bucket Redis, panjang hash identitas key, dan kelipatan TTL window.
RATE_LIMIT_BUCKET_PREFIX = os.getenv("RATE_LIMIT_BUCKET_PREFIX", "").strip()
RATE_LIMIT_KEY_HASH_CHARS = _env_int("RATE_LIMIT_KEY_HASH_CHARS")
RATE_LIMIT_BUCKET_TTL_FACTOR = _env_int("RATE_LIMIT_BUCKET_TTL_FACTOR")
if not 1 <= RATE_LIMIT_KEY_HASH_CHARS <= 64:
    raise ValueError("RATE_LIMIT_KEY_HASH_CHARS harus antara 1 dan 64.")
if RATE_LIMIT_BUCKET_TTL_FACTOR < 1:
    raise ValueError("RATE_LIMIT_BUCKET_TTL_FACTOR harus >= 1.")
MAX_CONCURRENT_AGENT_RUNS = _env_int("MAX_CONCURRENT_AGENT_RUNS")
MAX_QUESTION_LENGTH = _env_int("MAX_QUESTION_LENGTH")
