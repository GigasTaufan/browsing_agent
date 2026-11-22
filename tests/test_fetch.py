"""Regresi batas URL dan pemilihan fallback browser tanpa akses jaringan."""

from concurrent.futures import ThreadPoolExecutor
import threading
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


def test_browser_access_and_cleanup_are_serialized(fetcher, monkeypatch):
    monkeypatch.setattr(config, "BROWSER_FALLBACK_ENABLED", True)
    fetcher.fetch.return_value = (200, "text/html", "<body>short</body>")
    monkeypatch.setattr(fetch.time, "sleep", lambda _: None)

    active = 0
    maximum_active = 0
    active_lock = threading.Lock()
    first_get_started = threading.Event()
    release_first_get = threading.Event()
    first_body_started = threading.Event()
    release_first_body = threading.Event()
    second_get_started = threading.Event()
    cleanup_started = threading.Event()

    def enter_browser():
        nonlocal active, maximum_active
        with active_lock:
            active += 1
            maximum_active = max(maximum_active, active)

    def leave_browser():
        nonlocal active
        with active_lock:
            active -= 1

    def get(url):
        enter_browser()
        try:
            if url.endswith("/first"):
                first_get_started.set()
                release_first_get.wait(timeout=2)
            else:
                second_get_started.set()
        finally:
            leave_browser()

    def read_body(_by, _name):
        enter_browser()
        try:
            if not first_body_started.is_set():
                first_body_started.set()
                release_first_body.wait(timeout=2)
            return SimpleNamespace(text="Browser article")
        finally:
            leave_browser()
    def quit_browser():
        cleanup_started.set()
        enter_browser()
        leave_browser()

    driver = Mock()
    driver.get.side_effect = get
    driver.find_element.side_effect = read_body
    driver.quit.side_effect = quit_browser
    fetch._browser_instance = driver
    monkeypatch.setattr(fetch, "_get_browser", lambda: driver)

    def browse(url):
        with AgentRunState():
            return fetch.browse_tool.invoke({"url": url})

    try:
        with ThreadPoolExecutor(max_workers=3) as executor:
            first = executor.submit(browse, "https://example.com/first")
            assert first_get_started.wait(timeout=1)
            cleanup = executor.submit(fetch.close_browser)
            release_first_get.set()
            assert first_body_started.wait(timeout=1)
            second = executor.submit(browse, "https://example.com/second")
            threading.Event().wait(0.05)
            assert not second_get_started.is_set()
            assert not cleanup_started.is_set()
            release_first_body.set()
            assert "Browser article" in first.result(timeout=2)
            assert "Browser article" in second.result(timeout=2)
            cleanup.result(timeout=2)

        assert maximum_active == 1
        driver.quit.assert_called_once_with()
    finally:
        release_first_body.set()
        release_first_get.set()
        fetch._browser_instance = None

def test_browser_uses_preinstalled_chromedriver_without_download(monkeypatch):
    monkeypatch.setenv("CHROMEDRIVER_PATH", "/usr/bin/chromedriver")
    monkeypatch.setenv("CHROME_BIN", "/usr/bin/chromium")
    monkeypatch.setattr(fetch, "_browser_instance", None)
    driver = Mock()
    service = Mock()
    service_factory = Mock(return_value=service)
    chrome_factory = Mock(return_value=driver)
    driver_manager = Mock()
    driver_manager.return_value.install.return_value = "/downloaded/chromedriver"
    monkeypatch.setattr(fetch, "Service", service_factory)
    monkeypatch.setattr(fetch.webdriver, "Chrome", chrome_factory)
    monkeypatch.setattr(fetch, "ChromeDriverManager", driver_manager)

    assert fetch._get_browser() is driver

    service_factory.assert_called_once_with("/usr/bin/chromedriver")
    assert chrome_factory.call_args.kwargs["service"] is service
    assert chrome_factory.call_args.kwargs["options"].binary_location == "/usr/bin/chromium"
    driver_manager.assert_not_called()
