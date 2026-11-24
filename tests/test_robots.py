"""
Unit test untuk policy/robots.py.
Mock urllib.request untuk menghindari request HTTP nyata.
"""

import urllib.error
from unittest.mock import MagicMock, patch

import pytest

from policy.robots import clear_robots_cache, is_url_allowed


@pytest.fixture(autouse=True)
def clear_cache():
    """Bersihkan cache robots.txt sebelum setiap test."""
    clear_robots_cache()


def test_robots_allow(mock_urlopen):
    """URL yang diizinkan harus return True."""
    robots_content = "User-agent: *\nAllow: /\nDisallow: /admin"
    mock_urlopen(robots_content)

    allowed = is_url_allowed("https://example.com/page")
    assert allowed is True


def test_robots_disallow(mock_urlopen):
    """URL yang tidak diizinkan harus return False."""
    robots_content = "User-agent: *\nDisallow: /admin/\nAllow: /"
    mock_urlopen(robots_content)

    blocked = is_url_allowed("https://example.com/admin/secrets")
    assert blocked is False


def test_robots_allow_specific_path(mock_urlopen):
    """Path yang tidak ada di Disallow harus diizinkan."""
    robots_content = "User-agent: *\nDisallow: /admin\nAllow: /public"
    mock_urlopen(robots_content)

    allowed = is_url_allowed("https://example.com/public/data")
    assert allowed is True


def test_robots_fetch_error(capsys):
    """Jika gagal fetch robots.txt, anggap diizinkan (fail-open default)."""
    with patch("urllib.request.urlopen", side_effect=Exception("timeout")):
        allowed = is_url_allowed("https://example.com/page")
    assert allowed is True
    captured = capsys.readouterr()
    assert "Gagal mengambil" in captured.out


def test_robots_fetch_error_fail_closed(monkeypatch):
    """ROBOTS_FAIL_OPEN=false: error fetch (non-404) menolak URL."""
    monkeypatch.setattr("policy.robots.config.ROBOTS_FAIL_OPEN", False)

    with patch("urllib.request.urlopen", side_effect=Exception("timeout")):
        allowed = is_url_allowed("https://example.com/page")

    assert allowed is False


def test_robots_404_allows_even_when_fail_closed(monkeypatch):
    """404 = robots.txt tidak ada; RFC 9309: semua diizinkan meski fail-closed."""
    monkeypatch.setattr("policy.robots.config.ROBOTS_FAIL_OPEN", False)
    error = urllib.error.HTTPError("https://example.com/robots.txt", 404, "Not Found", None, None)

    with patch("urllib.request.urlopen", side_effect=error):
        allowed = is_url_allowed("https://example.com/page")

    assert allowed is True


@pytest.mark.parametrize("fail_open, expected", [(True, True), (False, False)])
def test_robots_parse_error_follows_policy(monkeypatch, fail_open, expected):
    """Error parsing can_fetch mengikuti ROBOTS_FAIL_OPEN."""
    monkeypatch.setattr("policy.robots.config.ROBOTS_FAIL_OPEN", fail_open)

    broken_parser = MagicMock()
    broken_parser.allow_all = False
    broken_parser.can_fetch.side_effect = Exception("parse error")

    with patch("policy.robots.get_robots_parser", return_value=broken_parser):
        allowed = is_url_allowed("https://example.com/page")

    assert allowed is expected


# --- Helper fixture ---
@pytest.fixture
def mock_urlopen():
    """Fixture untuk mock urllib.request.urlopen dengan robots.txt content."""

    def _mock(content: str):
        def side_effect(req, **kwargs):
            # Return a mock response with a read() method
            mock_resp = MagicMock()
            mock_resp.read.return_value = content.encode("utf-8")
            mock_resp.__enter__ = lambda s: s
            mock_resp.__exit__ = lambda s, *a: False
            return mock_resp

        patcher = patch("urllib.request.urlopen", side_effect=side_effect)
        patcher.start()
        return patcher

    return _mock
