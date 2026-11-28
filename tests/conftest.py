"""Konfigurasi pytest untuk seluruh suite."""

import os

from dotenv import load_dotenv

# Nonaktifkan async trace logging MLflow di lingkungan test agar tidak ada
# background queue yang mem-flush ke tracking server saat proses exit.
os.environ.setdefault("MLFLOW_ENABLE_ASYNC_TRACE_LOGGING", "false")

# Nilai test untuk variabel operasional wajib (config.py tidak menyimpan default).
# Nilai di bawah SELALU dipakai untuk test (menimpa .env lokal) agar hasil suite tidak
# bergantung isi .env developer; hanya variabel yang tidak terdaftar di sini (opsional)
# yang tetap dibaca dari .env.
TEST_ENV_DEFAULTS = {
    "API_ALLOWED_KEYS": "test-caller-key,test-ui-key,test-ui-to-api-key",
    "UI_API_KEY": "test-ui-key",
    "UI_TO_API_KEY": "test-ui-to-api-key",
    "SEARXNG_SECRET": "test-searxng-secret",
    "SEARXNG_CONTACT_URL": "mailto:admin@example.com",
    "MODELHUB_API_KEY": "test-modelhub-key",
    "MODELHUB_BASE_URL": "https://modelhub.test/v1",
    "MODELHUB_MODEL_NAME": "test-model",
    "LLM_TEMPERATURE": "0.7",
    "LLM_MAX_TOKENS": "1500",
    "LLM_TIMEOUT": "60",
    "LLM_MAX_RETRIES": "2",
    "MAX_TOOL_CALLS": "5",
    "MAX_URLS_PER_QUERY": "3",
    "MAX_SEARCH_RESULTS": "5",
    "SEARCH_CANDIDATE_LIMIT": "20",
    "REQUEST_TIMEOUT": "30",
    "BROWSER_FALLBACK_ENABLED": "true",
    "FETCH_MAX_RETRIES": "3",
    "BROWSER_WAIT_TIMEOUT": "10",
    "FETCH_MAX_CONTENT_CHARS": "3000",
    "USER_AGENT": "BrowsingAgent/0.1",
    "RATE_LIMIT_PER_DOMAIN_SECONDS": "1.0",
    "ROBOTS_FAIL_OPEN": "true",
    "ROBOTS_CACHE_TTL_SECONDS": "3600",
    "SEARCH_PROVIDER": "duckduckgo",
    "SEARCH_FALLBACK_ENABLED": "true",
    "MLFLOW_TRACING_ENABLED": "true",
    "MLFLOW_TRACKING_URI": "http://localhost:5000",
    "MLFLOW_EXPERIMENT_ID": "1",
    "MLFLOW_HTTP_TIMEOUT": "5",
    "MLFLOW_PREFLIGHT_TIMEOUT": "2.0",
    "CHUNK_SIZE": "2000",
    "RATE_LIMIT_REQUESTS_PER_MINUTE": "10",
    "RATE_LIMIT_REDIS_TIMEOUT": "1.0",
    "RATE_LIMIT_WINDOW_SECONDS": "60",
    "MAX_CONCURRENT_AGENT_RUNS": "4",
    "MAX_QUESTION_LENGTH": "2000",
}


def apply_test_env_defaults() -> None:
    """Paksa nilai test untuk variabel wajib agar suite hermetic."""
    load_dotenv()
    os.environ.update(TEST_ENV_DEFAULTS)


apply_test_env_defaults()
