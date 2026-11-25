"""Unit test konfigurasi: pembacaan .env strict tanpa default hardcoded (fail-fast)."""

import importlib

import pytest

import config

_REQUIRED_VARS = [
    "LLM_TEMPERATURE",
    "LLM_MAX_TOKENS",
    "LLM_TIMEOUT",
    "LLM_MAX_RETRIES",
    "MAX_TOOL_CALLS",
    "MAX_URLS_PER_QUERY",
    "MAX_SEARCH_RESULTS",
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
]

_MLFLOW_VARS = [
    "MLFLOW_TRACKING_URI",
    "MLFLOW_EXPERIMENT_NAME",
    "MLFLOW_HTTP_TIMEOUT",
    "MLFLOW_PREFLIGHT_TIMEOUT",
]


@pytest.fixture(autouse=True)
def _restore_config():
    """Pastikan modul config kembali membaca environment asli setelah tiap test."""
    yield
    importlib.reload(config)


def test_missing_required_vars_fail_fast(monkeypatch):
    # Isolasi dari file .env lokal agar hanya os.environ yang dibaca.
    monkeypatch.setattr("dotenv.load_dotenv", lambda *args, **kwargs: None)
    for name in _REQUIRED_VARS + _MLFLOW_VARS:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("MLFLOW_TRACING_ENABLED", "true")

    with pytest.raises(ValueError, match="LLM_TEMPERATURE"):
        importlib.reload(config)


def test_blank_required_value_treated_as_missing(monkeypatch):
    monkeypatch.setenv("MAX_TOOL_CALLS", "  ")

    with pytest.raises(ValueError, match="MAX_TOOL_CALLS"):
        importlib.reload(config)


def test_mlflow_group_optional_when_tracing_disabled(monkeypatch):
    monkeypatch.setattr("dotenv.load_dotenv", lambda *args, **kwargs: None)
    for name in _MLFLOW_VARS:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("MLFLOW_TRACING_ENABLED", "false")

    reloaded = importlib.reload(config)

    assert reloaded.MLFLOW_TRACING_ENABLED is False
    assert reloaded.MLFLOW_HTTP_TIMEOUT is None
    assert reloaded.MLFLOW_PREFLIGHT_TIMEOUT is None


def test_mlflow_group_required_when_tracing_enabled(monkeypatch):
    monkeypatch.setattr("dotenv.load_dotenv", lambda *args, **kwargs: None)
    for name in _MLFLOW_VARS:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("MLFLOW_TRACING_ENABLED", "true")

    with pytest.raises(ValueError, match="MLFLOW_TRACKING_URI"):
        importlib.reload(config)


def test_values_come_from_env_not_code(monkeypatch):
    monkeypatch.setenv("MAX_TOOL_CALLS", "7")
    monkeypatch.setenv("LLM_TEMPERATURE", "0.123")

    reloaded = importlib.reload(config)

    assert reloaded.MAX_TOOL_CALLS == 7
    assert reloaded.LLM_TEMPERATURE == 0.123


def test_invalid_integer_raises_clear_error(monkeypatch):
    monkeypatch.setenv("MAX_TOOL_CALLS", "abc")

    with pytest.raises(ValueError, match="MAX_TOOL_CALLS"):
        importlib.reload(config)


def test_invalid_float_raises_clear_error(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_PER_DOMAIN_SECONDS", "cepat")

    with pytest.raises(ValueError, match="RATE_LIMIT_PER_DOMAIN_SECONDS"):
        importlib.reload(config)


def test_invalid_bool_raises_clear_error(monkeypatch):
    monkeypatch.setenv("BROWSER_FALLBACK_ENABLED", "mungkin")

    with pytest.raises(ValueError, match="BROWSER_FALLBACK_ENABLED"):
        importlib.reload(config)


def test_bool_accepts_common_truthy_values(monkeypatch):
    monkeypatch.setenv("BROWSER_FALLBACK_ENABLED", "FALSE")

    reloaded = importlib.reload(config)

    assert reloaded.BROWSER_FALLBACK_ENABLED is False
