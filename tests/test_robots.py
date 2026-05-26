"""
Unit test untuk policy/robots.py.
Mock urllib.request untuk menghindari request HTTP nyata.
"""

import pytest
from unittest.mock import patch, MagicMock
from io import BytesIO

from policy.robots import is_url_allowed, clear_robots_cache


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
    """Jika gagal fetch robots.txt, anggap diizinkan (fail-open)."""
    with patch("urllib.request.urlopen", side_effect=Exception("timeout")):
        allowed = is_url_allowed("https://example.com/page")
    assert allowed is True
    captured = capsys.readouterr()
    assert "Gagal mengambil" in captured.out


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
