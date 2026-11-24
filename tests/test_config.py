"""Unit test konfigurasi: default nilai operasional dan parsing yang fail-fast."""

import importlib

import pytest

import config

_OPERATIONAL_VARS = [
    "MAX_TOOL_CALLS",
    "MAX_URLS_PER_QUERY",
    "MAX_SEARCH_RESULTS",
    "REQUEST_TIMEOUT",
    "BROWSER_FALLBACK_ENABLED",
    "USER_AGENT",
    "RATE_LIMIT_PER_DOMAIN_SECONDS",
    "CHUNK_SIZE",
    "AZURE_OPENAI_DEPLOYMENT_NAME",
    "MODELHUB_BASE_URL",
    "MODELHUB_MODEL_NAME",
]


@pytest.fixture(autouse=True)
def _restore_config():
    """Pastikan modul config kembali membaca environment asli setelah tiap test."""
    yield
    importlib.reload(config)


def test_operational_defaults_when_env_missing(monkeypatch):
    # Isolasi dari file .env lokal agar hanya os.environ yang dibaca.
    monkeypatch.setattr("dotenv.load_dotenv", lambda *args, **kwargs: None)
    for name in _OPERATIONAL_VARS:
        monkeypatch.delenv(name, raising=False)

    reloaded = importlib.reload(config)

    assert reloaded.MAX_TOOL_CALLS == 5
    assert reloaded.MAX_URLS_PER_QUERY == 3
    assert reloaded.MAX_SEARCH_RESULTS == 5
    assert reloaded.REQUEST_TIMEOUT == 30
    assert reloaded.BROWSER_FALLBACK_ENABLED is True
    assert reloaded.USER_AGENT == "BrowsingAgent/0.1"
    assert reloaded.RATE_LIMIT_PER_DOMAIN_SECONDS == 1.0
    assert reloaded.CHUNK_SIZE == 2000
    assert reloaded.AZURE_OPENAI_DEPLOYMENT_NAME == "gpt-4o-mini"
    assert reloaded.MODELHUB_BASE_URL == "https://api-modelhub.aiplayground.id/v1"
    assert reloaded.MODELHUB_MODEL_NAME == "gpt-4o-mini"


def test_blank_operational_value_falls_back_to_default(monkeypatch):
    monkeypatch.setenv("MAX_TOOL_CALLS", "  ")
    monkeypatch.setenv("BROWSER_FALLBACK_ENABLED", "")

    reloaded = importlib.reload(config)

    assert reloaded.MAX_TOOL_CALLS == 5
    assert reloaded.BROWSER_FALLBACK_ENABLED is True


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
