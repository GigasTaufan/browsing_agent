"""Unit test provider pencarian: seleksi, mapping SearXNG, dan fallback."""

from unittest.mock import Mock, patch

import pytest

import config
from tools import search as search_module


def _set_config(monkeypatch, **kwargs):
    for name, value in kwargs.items():
        monkeypatch.setattr(search_module.config, name, value)


def test_searxng_provider_maps_json_results(monkeypatch):
    _set_config(
        monkeypatch,
        SEARCH_PROVIDER="searxng",
        SEARXNG_BASE_URL="http://searxng:8080/",
        SEARCH_FALLBACK_ENABLED=False,
        MAX_SEARCH_RESULTS=5,
    )
    payload = {
        "results": [
            {
                "title": "Kurs BI",
                "url": "https://www.bi.go.id/kurs",
                "content": "1 USD = 15.800 IDR",
            },
            {"title": "General", "url": "https://example.com/kurs", "content": "snippet umum"},
        ]
    }
    fake_response = Mock()
    fake_response.raise_for_status = Mock()
    fake_response.json = Mock(return_value=payload)
    fake_client = Mock()
    fake_client.get = Mock(return_value=fake_response)
    fake_client.__enter__ = Mock(return_value=fake_client)
    fake_client.__exit__ = Mock(return_value=False)

    with patch.object(search_module.httpx, "Client", return_value=fake_client):
        results = search_module.search_web("kurs dollar")

    fake_client.get.assert_called_once()
    assert fake_client.get.call_args.kwargs["params"]["safesearch"] == config.SEARXNG_SAFESEARCH
    assert [result.url for result in results] == [
        "https://www.bi.go.id/kurs",
        "https://example.com/kurs",
    ]
    assert [result.title for result in results] == ["Kurs BI", "General"]


def test_fallback_to_searxng_when_ddgs_fails(monkeypatch):
    _set_config(
        monkeypatch,
        SEARCH_PROVIDER="duckduckgo",
        SEARXNG_BASE_URL="http://searxng:8080",
        SEARCH_FALLBACK_ENABLED=True,
        MAX_SEARCH_RESULTS=5,
    )

    class FailingDDGS:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            return False

        def text(self, query, **kwargs):
            raise RuntimeError("blocked")

    monkeypatch.setattr(search_module, "DDGS", FailingDDGS)

    payload = {"results": [{"title": "Hasil", "url": "https://example.com/x", "content": "isi"}]}
    fake_response = Mock()
    fake_response.raise_for_status = Mock()
    fake_response.json = Mock(return_value=payload)
    fake_client = Mock()
    fake_client.get = Mock(return_value=fake_response)
    fake_client.__enter__ = Mock(return_value=fake_client)
    fake_client.__exit__ = Mock(return_value=False)

    with (
        patch.object(search_module.httpx, "Client", return_value=fake_client),
        patch.object(search_module.time, "sleep"),
    ):
        results = search_module.search_web("test")

    assert any(result.url == "https://example.com/x" for result in results)


def test_searxng_skipped_as_fallback_when_not_configured(monkeypatch):
    _set_config(
        monkeypatch,
        SEARCH_PROVIDER="duckduckgo",
        SEARXNG_BASE_URL=None,
        SEARCH_FALLBACK_ENABLED=True,
    )

    class FailingDDGS:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            return False

        def text(self, query, **kwargs):
            raise RuntimeError("blocked")

    monkeypatch.setattr(search_module, "DDGS", FailingDDGS)

    with patch.object(search_module.time, "sleep"):
        with pytest.raises(RuntimeError, match="Tidak dapat melakukan pencarian"):
            search_module.search_web("test")


def test_unknown_provider_returns_clear_error(monkeypatch):
    """config.py menolak SEARCH_PROVIDER asing saat startup; guard run-time tetap ada."""
    _set_config(monkeypatch, SEARCH_PROVIDER="google")

    with pytest.raises(RuntimeError, match="SEARCH_PROVIDER tidak dikenal"):
        search_module.search_web("test")


def test_searxng_without_base_url_raises(monkeypatch):
    _set_config(monkeypatch, SEARXNG_BASE_URL=None)

    with pytest.raises(RuntimeError, match="SEARXNG_BASE_URL"):
        search_module._search_searxng("test")


def test_provider_recorded_on_mlflow_span(monkeypatch):
    """Provider yang benar-benar dipakai tercatat sebagai atribut span MLflow aktif."""
    import mlflow

    captured = {}

    class FakeSpan:
        def set_attributes(self, attrs):
            captured.update(attrs)

    monkeypatch.setattr(mlflow, "get_current_active_span", lambda: FakeSpan())

    _set_config(
        monkeypatch,
        SEARCH_PROVIDER="duckduckgo",
        SEARXNG_BASE_URL="http://searxng:8080",
        SEARCH_FALLBACK_ENABLED=True,
        MAX_SEARCH_RESULTS=5,
    )

    class FailingDDGS:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            return False

        def text(self, query, **kwargs):
            raise RuntimeError("blocked")

    monkeypatch.setattr(search_module, "DDGS", FailingDDGS)

    payload = {"results": [{"title": "Hasil", "url": "https://example.com/x", "content": "isi"}]}
    fake_response = Mock()
    fake_response.raise_for_status = Mock()
    fake_response.json = Mock(return_value=payload)
    fake_client = Mock()
    fake_client.get = Mock(return_value=fake_response)
    fake_client.__enter__ = Mock(return_value=fake_client)
    fake_client.__exit__ = Mock(return_value=False)

    with (
        patch.object(search_module.httpx, "Client", return_value=fake_client),
        patch.object(search_module.time, "sleep"),
    ):
        results = search_module.search_web("test")

    assert any(result.url == "https://example.com/x" for result in results)
    assert captured == {"search.provider": "searxng", "search.fallback_used": True}


def test_ranking_dedups_by_url_and_never_rewrites_commas(monkeypatch):
    """URL berisi koma/titik-koma tidak boleh terpotong oleh parsing regex lama."""
    _set_config(monkeypatch, MAX_SEARCH_RESULTS=5)
    results = [
        search_module.SearchResult(title="Koma", url="https://example.com/a,b;c", snippet="satu"),
        search_module.SearchResult(title="Gov", url="https://example.gov/a,b;c", snippet="dua"),
        search_module.SearchResult(
            title="Duplikat", url="https://EXAMPLE.com/a,b;c/", snippet="tiga"
        ),
    ]

    ranked = search_module._rank_and_dedup(results, 5)

    assert [result.url for result in ranked] == [
        "https://example.gov/a,b;c",
        "https://example.com/a,b;c",
    ]
