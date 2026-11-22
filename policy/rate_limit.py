"""
Rate limiter per domain untuk mencegah request terlalu cepat.
Menggunakan delay sederhana antar request ke domain yang sama.
"""

import threading
import time
from urllib.parse import urlparse
from typing import Dict

import config


class DomainRateLimiter:
    """
    Rate limiter yang melacak slot berikutnya untuk tiap domain.
    Jika slot berikutnya belum tiba, menunggu (sleep) di luar lock.
    """

    def __init__(self, delay_seconds: float = None):
        """
        Args:
            delay_seconds: Delay antar request ke domain yang sama.
                           Default dari config.RATE_LIMIT_PER_DOMAIN_SECONDS.
        """
        self.delay_seconds = delay_seconds or config.RATE_LIMIT_PER_DOMAIN_SECONDS
        # domain -> timestamp slot berikutnya
        self._next_allowed: Dict[str, float] = {}
        self._lock = threading.Lock()

    def wait_if_needed(self, url: str) -> float:
        """
        Cek apakah perlu menunggu sebelum request ke URL ini.
        Jika ya, sleep sesuai selisih waktu yang tersisa.

        Returns:
            Detik yang di-sleep (0 jika tidak perlu menunggu).
        """
        parsed = urlparse(url)
        domain = parsed.netloc.lower()

        with self._lock:
            now = time.monotonic()
            next_allowed = self._next_allowed.get(domain, now)
            wait_time = max(0.0, next_allowed - now)
            self._next_allowed[domain] = max(now, next_allowed) + self.delay_seconds

        if wait_time > 0:
            print(f"[Rate Limit]: Menunggu {wait_time:.2f}s sebelum request ke {domain}...")
            time.sleep(wait_time)
        return wait_time

    def reset(self) -> None:
        """Reset semua tracking (berguna untuk testing)."""
        with self._lock:
            self._next_allowed.clear()
