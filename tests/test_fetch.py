"""Regresi batas URL dan pemilihan fallback browser tanpa akses jaringan."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import config
from agent.planner import AgentRunState
from tools import fetch


@pytest.fixture
def fetcher(monkeypatch):
    with AgentRunState():
        monkeypatch.setattr(config, "MAX_TOOL_CALLS", 20)
        monkeypatch.setattr(config, "MAX_URLS_PER_QUERY", 1)
        monkeypatch.setattr(config, "BROWSER_FALLBACK_ENABLED", False)
        monkeypatch.setattr(fetch, "is_url_allowed", Mock(return_value=True))
        monkeypatch.setattr(fetch._rate_limiter, "wait_if_needed", Mock())
        client = Mock(max_retries=3)
        client.fetch.return_value = (200, "text/html", "<html><body>Artikel uji</body></html>")
        monkeypatch.setattr(fetch, "_get_http_fetcher", lambda: client)
        yield client


def test_url_limit_blocks_network_and_resets(fetcher):
    fetch.browse_tool.invoke({"url": "https://example.com/a"})
    fetch.is_url_allowed.reset_mock()
    result = fetch.browse_tool.invoke({"url": "https://example.com/b"})
    assert "[URL Limit]" in result
    fetch.is_url_allowed.assert_not_called()
    fetcher.fetch.assert_called_once_with("https://example.com/a")

    with AgentRunState():
        result = fetch.browse_tool.invoke({"url": "https://example.com/b"})
        assert "Artikel uji" in result
        fetcher.fetch.assert_called_with("https://example.com/b")


def test_failed_fetch_counts_but_same_url_can_retry(fetcher):
    fetcher.fetch.return_value = (0, "", "")
    url = "https://example.com/a"
    assert "Gagal fetch" in fetch.browse_tool.invoke({"url": url})
    assert "Gagal fetch" in fetch.browse_tool.invoke({"url": url})
    assert "[URL Limit]" in fetch.browse_tool.invoke({"url": "https://example.com/b"})
    assert fetcher.fetch.call_count == 2


def test_zero_limit_prevents_network(fetcher, monkeypatch):
    monkeypatch.setattr(config, "MAX_URLS_PER_QUERY", 0)
    assert "[URL Limit]" in fetch.browse_tool.invoke({"url": "https://example.com/a"})
    fetch.is_url_allowed.assert_not_called()
    fetcher.fetch.assert_not_called()


@pytest.mark.parametrize("length, expected", [(499, True), (500, False)])
def test_js_detection_boundary(length, expected):
    assert fetch._is_js_heavy("text/html", f"<body>{'a' * length}</body>") is expected


def test_non_html_does_not_need_browser():
    assert not fetch._is_js_heavy("application/json", "{}")


def test_short_html_uses_browser_fallback(fetcher, monkeypatch):
    monkeypatch.setattr(config, "BROWSER_FALLBACK_ENABLED", True)
    driver = Mock()
    driver.find_element.return_value = SimpleNamespace(text="Artikel dari browser")
    monkeypatch.setattr(fetch, "_get_browser", lambda: driver)
    monkeypatch.setattr(fetch.time, "sleep", lambda _: None)
    result = fetch.browse_tool.invoke({"url": "https://example.com/a"})
    assert "Artikel dari browser" in result
    driver.get.assert_called_once_with("https://example.com/a")


def test_long_html_skips_browser(fetcher, monkeypatch):
    monkeypatch.setattr(config, "BROWSER_FALLBACK_ENABLED", True)
    fetcher.fetch.return_value = (200, "text/html", f"<body>{'artikel ' * 100}</body>")
    browser = Mock()
    monkeypatch.setattr(fetch, "_get_browser", browser)
    assert "artikel" in fetch.browse_tool.invoke({"url": "https://example.com/a"})
    browser.assert_not_called()
