"""
Unit test untuk policy/rate_limit.py.
Mock waktu untuk verifikasi delay.
"""

import threading
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from policy.rate_limit import DomainRateLimiter


def test_rate_limit_no_wait_first_request():
    """Request pertama ke domain tidak perlu menunggu."""
    limiter = DomainRateLimiter(delay_seconds=2.0)

    with patch("time.sleep") as mock_sleep:
        with patch("time.monotonic", return_value=1000.0):
            wait = limiter.wait_if_needed("https://example.com/page")

    mock_sleep.assert_not_called()
    assert wait == 0.0


def test_rate_limit_waits_when_needed():
    """Request kedua ke domain yang sama dalam delay period harus menunggu."""
    limiter = DomainRateLimiter(delay_seconds=2.0)

    # Request pertama pada t=1000
    with patch("time.monotonic", return_value=1000.0):
        limiter.wait_if_needed("https://example.com/page1")

    # Request kedua pada t=1001 (hanya 1 detik berlalu, delay=2)
    with patch("time.sleep") as mock_sleep:
        with patch("time.monotonic", return_value=1001.0):
            wait = limiter.wait_if_needed("https://example.com/page2")

    mock_sleep.assert_called_once()
    assert wait == 1.0  # 2 - 1 = 1 detik tersisa


def test_rate_limit_different_domains():
    """Request ke domain berbeda tidak perlu menunggu."""
    limiter = DomainRateLimiter(delay_seconds=2.0)

    with patch("time.monotonic", return_value=1000.0):
        limiter.wait_if_needed("https://example.com/page")

    with patch("time.sleep") as mock_sleep:
        with patch("time.monotonic", return_value=1000.5):
            wait = limiter.wait_if_needed("https://another.com/page")

    mock_sleep.assert_not_called()
    assert wait == 0.0


def test_concurrent_requests_reserve_distinct_slots_before_sleep():
    """Concurrent calls reserve separate slots before either sleeps."""
    limiter = DomainRateLimiter(delay_seconds=2.0)
    sleep_count = 0
    sleep_count_lock = threading.Lock()
    both_sleeping = threading.Event()

    def synchronized_sleep(_seconds):
        nonlocal sleep_count
        with sleep_count_lock:
            sleep_count += 1
            if sleep_count == 2:
                both_sleeping.set()
        if not both_sleeping.wait(timeout=2):
            raise AssertionError("Concurrent requests did not overlap while sleeping.")

    with patch("time.monotonic", return_value=1000.0) as mock_monotonic:
        limiter.wait_if_needed("https://example.com/first")
        mock_monotonic.return_value = 1001.0

        with patch("time.sleep", side_effect=synchronized_sleep):
            with ThreadPoolExecutor(max_workers=2) as executor:
                waits = list(
                    executor.map(
                        limiter.wait_if_needed,
                        ["https://example.com/second", "https://example.com/third"],
                    )
                )

    assert sorted(waits) == [1.0, 3.0]
