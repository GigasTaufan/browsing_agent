"""
Konfigurasi utama aplikasi Browsing Agent.
Mengambil variabel lingkungan dari .env dan mendefinisikan konstanta.
Variabel operasional memiliki nilai default; hanya kredensial provider yang wajib diisi.
"""

import os

from dotenv import load_dotenv

# Muat variabel dari .env saat modul di-import
load_dotenv()


def _env_int(name: str, default: int) -> int:
    """Baca variabel lingkungan integer dengan pesan error yang jelas."""
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        raise ValueError(
            f"Variabel lingkungan {name} harus berupa integer, ditemukan: {raw!r}."
        ) from None


def _env_float(name: str, default: float) -> float:
    """Baca variabel lingkungan float dengan pesan error yang jelas."""
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        raise ValueError(
            f"Variabel lingkungan {name} harus berupa angka, ditemukan: {raw!r}."
        ) from None


def _env_bool(name: str, default: bool) -> bool:
    """Baca variabel lingkungan boolean ('true'/'false', case-insensitive)."""
    raw = os.getenv(name, "").strip().lower()
    if not raw:
        return default
    if raw in ("true", "1", "yes"):
        return True
    if raw in ("false", "0", "no"):
        return False
    raise ValueError(f"Variabel lingkungan {name} harus 'true' atau 'false', ditemukan: {raw!r}.")


# --- Azure OpenAI ---
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_DEPLOYMENT_NAME = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4o-mini")
AZURE_OPENAI_PREVIEW_API_VERSION = os.getenv("AZURE_OPENAI_PREVIEW_API_VERSION")

# --- ModelHub ---
MODELHUB_API_KEY = os.getenv("MODELHUB_API_KEY")
MODELHUB_BASE_URL = os.getenv("MODELHUB_BASE_URL", "https://api-modelhub.aiplayground.id/v1")
MODELHUB_MODEL_NAME = os.getenv("MODELHUB_MODEL_NAME", "gpt-4o-mini")

# --- Tool Limits ---
MAX_TOOL_CALLS = _env_int("MAX_TOOL_CALLS", 5)
MAX_URLS_PER_QUERY = _env_int("MAX_URLS_PER_QUERY", 3)
MAX_SEARCH_RESULTS = _env_int("MAX_SEARCH_RESULTS", 5)


# --- Fetching ---
REQUEST_TIMEOUT = _env_int("REQUEST_TIMEOUT", 30)
BROWSER_FALLBACK_ENABLED = _env_bool("BROWSER_FALLBACK_ENABLED", True)


# --- Safe Crawling ---
USER_AGENT = os.getenv("USER_AGENT", "BrowsingAgent/0.1")
RATE_LIMIT_PER_DOMAIN_SECONDS = _env_float("RATE_LIMIT_PER_DOMAIN_SECONDS", 1.0)
# True: robots.txt gagal di-fetch (non-404) => izinkan. False: tolak (fail-closed).
ROBOTS_FAIL_OPEN = _env_bool("ROBOTS_FAIL_OPEN", True)

# --- MLflow GenAI Tracing ---
MLFLOW_TRACING_ENABLED = _env_bool("MLFLOW_TRACING_ENABLED", True)
MLFLOW_TRACKING_URI = os.getenv("MLFLOW_TRACKING_URI", "http://10.60.144.48:5000")
MLFLOW_EXPERIMENT_NAME = os.getenv("MLFLOW_EXPERIMENT_NAME", "browsing-agent-dev")

# --- Search Provider ---
SEARCH_PROVIDER = os.getenv("SEARCH_PROVIDER", "duckduckgo").strip().lower()
SEARXNG_BASE_URL = os.getenv("SEARXNG_BASE_URL")
SEARCH_FALLBACK_ENABLED = _env_bool("SEARCH_FALLBACK_ENABLED", True)

# --- Content Extraction ---
CHUNK_SIZE = _env_int("CHUNK_SIZE", 2000)
# --- API Inbound Limits ---
# Rate limit per API key via Redis; kosong = dinonaktifkan (fail-open saat Redis down).
RATE_LIMIT_REDIS_URL = os.getenv("RATE_LIMIT_REDIS_URL")
RATE_LIMIT_REQUESTS_PER_MINUTE = _env_int("RATE_LIMIT_REQUESTS_PER_MINUTE", 10)
MAX_CONCURRENT_AGENT_RUNS = _env_int("MAX_CONCURRENT_AGENT_RUNS", 4)
MAX_QUESTION_LENGTH = _env_int("MAX_QUESTION_LENGTH", 2000)
