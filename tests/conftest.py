"""Konfigurasi pytest untuk seluruh suite."""

import os

from dotenv import load_dotenv

# Nonaktifkan async trace logging MLflow di lingkungan test agar tidak ada
# background queue yang mem-flush ke tracking server saat proses exit.
os.environ.setdefault("MLFLOW_ENABLE_ASYNC_TRACE_LOGGING", "false")

# Nilai test untuk variabel operasional wajib (config.py tidak menyimpan default).
# .env lokal (bila ada) menang; nilai di bawah hanya mengisi yang kosong,
# sehingga suite tetap hermetic di CI tanpa file .env.
TEST_ENV_DEFAULTS = {
    "LLM_TEMPERATURE": "0.7",
    "LLM_MAX_TOKENS": "1500",
    "LLM_TIMEOUT": "60",
    "LLM_MAX_RETRIES": "2",
    "MAX_TOOL_CALLS": "5",
    "MAX_URLS_PER_QUERY": "3",
    "MAX_SEARCH_RESULTS": "5",
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
    "MLFLOW_TRACKING_URI": "http://127.0.0.1:5000",
    "MLFLOW_EXPERIMENT_NAME": "browsing-agent-dev",
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
    """Isi variabel wajib yang belum ada di environment (tanpa menimpa yang sudah ada)."""
    load_dotenv()
    for name, value in TEST_ENV_DEFAULTS.items():
        os.environ.setdefault(name, value)


apply_test_env_defaults()
