"""
Unit test untuk policy/rate_limit.py.
Mock waktu untuk verifikasi delay.
"""

import time
from unittest.mock import patch
from policy.rate_limit import DomainRateLimiter


def test_rate_limit_no_wait_first_request():
    """Request pertama ke domain tidak perlu menunggu."""
    limiter = DomainRateLimiter(delay_seconds=2.0)

    with patch("time.sleep") as mock_sleep:
        with patch("time.time", return_value=1000.0):
            wait = limiter.wait_if_needed("https://example.com/page")

    mock_sleep.assert_not_called()
    assert wait == 0.0


def test_rate_limit_waits_when_needed():
    """Request kedua ke domain yang sama dalam delay period harus menunggu."""
    limiter = DomainRateLimiter(delay_seconds=2.0)

    # Request pertama pada t=1000
    with patch("time.time", return_value=1000.0):
        limiter.wait_if_needed("https://example.com/page1")

    # Request kedua pada t=1001 (hanya 1 detik berlalu, delay=2)
    with patch("time.sleep") as mock_sleep:
        with patch("time.time", return_value=1001.0):
            wait = limiter.wait_if_needed("https://example.com/page2")

    mock_sleep.assert_called_once()
    assert wait == 1.0  # 2 - 1 = 1 detik tersisa


def test_rate_limit_different_domains():
    """Request ke domain berbeda tidak perlu menunggu."""
    limiter = DomainRateLimiter(delay_seconds=2.0)

    with patch("time.time", return_value=1000.0):
        limiter.wait_if_needed("https://example.com/page")

    with patch("time.sleep") as mock_sleep:
        with patch("time.time", return_value=1000.5):
            wait = limiter.wait_if_needed("https://another.com/page")

    mock_sleep.assert_not_called()
    assert wait == 0.0
