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
    "MODELHUB_USER_AGENT": "curl/8.0",
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
    "FETCH_BACKOFF_BASE_SECONDS": "2.0",
    "BROWSER_JS_HEAVY_MIN_CHARS": "500",
    "FETCH_MAX_HEADINGS": "5",
    "EVIDENCE_HASH_CHARS": "500",
    "EVIDENCE_SNIPPET_CHARS": "300",
    "USER_AGENT": "BrowsingAgent/0.1",
    "RATE_LIMIT_PER_DOMAIN_SECONDS": "1.0",
    "ROBOTS_FAIL_OPEN": "true",
    "ROBOTS_CACHE_TTL_SECONDS": "3600",
    "SEARCH_PROVIDER": "duckduckgo",
    "SEARCH_FALLBACK_ENABLED": "true",
    "SEARCH_TRUSTED_DOMAINS": (
        ".edu,.gov,.ac.id,.go.id,.or.id,.wikipedia.org,.britannica.com,.stackoverflow.com"
    ),
    "SEARCH_TRUSTED_SCORE": "10",
    "SEARCH_DEFAULT_SCORE": "1",
    "SEARCH_LOG_TOP_RESULTS": "3",
    "DDG_RETRY_BACKENDS": "lite,lite,auto",
    "DDG_RETRY_DELAY_SECONDS": "1.0",
    "SEARXNG_SAFESEARCH": "1",
    "MLFLOW_TRACING_ENABLED": "true",
    "MLFLOW_TRACKING_URI": "http://localhost:5000",
    "MLFLOW_EXPERIMENT_ID": "1",
    "MLFLOW_HTTP_TIMEOUT": "5",
    "MLFLOW_PREFLIGHT_TIMEOUT": "2.0",
    "CHUNK_SIZE": "2000",
    "RATE_LIMIT_REQUESTS_PER_MINUTE": "10",
    "RATE_LIMIT_REDIS_TIMEOUT": "1.0",
    "RATE_LIMIT_WINDOW_SECONDS": "60",
    "RATE_LIMIT_KEY_HASH_CHARS": "16",
    "RATE_LIMIT_BUCKET_PREFIX": "ratelimit",
    "RATE_LIMIT_BUCKET_TTL_FACTOR": "2",
    "GUARDRAIL_BLOCKED_DOMAINS": "bca.co.id,bni.co.id,mandiri.co.id,bri.co.id",
    "GUARDRAIL_BLOCKED_PATH_SEGMENTS": "login,signin,auth,admin",
    "MAX_CONCURRENT_AGENT_RUNS": "4",
    "MAX_QUESTION_LENGTH": "2000",
}


def apply_test_env_defaults() -> None:
    """Paksa nilai test untuk variabel wajib agar suite hermetic."""
    load_dotenv()
    os.environ.update(TEST_ENV_DEFAULTS)


apply_test_env_defaults()
