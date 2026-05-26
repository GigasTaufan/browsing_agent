"""
Rate limiter per domain untuk mencegah request terlalu cepat.
Menggunakan delay sederhana antar request ke domain yang sama.
"""

import time
from urllib.parse import urlparse
from typing import Dict

import config


class DomainRateLimiter:
    """
    Rate limiter yang melacak request terakhir per domain.
    Jika terlalu cepat, menunggu (sleep) sebelum melanjutkan.
    """

    def __init__(self, delay_seconds: float = None):
        """
        Args:
            delay_seconds: Delay antar request ke domain yang sama.
                           Default dari config.RATE_LIMIT_PER_DOMAIN_SECONDS.
        """
        self.delay_seconds = delay_seconds or config.RATE_LIMIT_PER_DOMAIN_SECONDS
        # domain -> timestamp request terakhir
        self._last_request: Dict[str, float] = {}

    def wait_if_needed(self, url: str) -> float:
        """
        Cek apakah perlu menunggu sebelum request ke URL ini.
        Jika ya, sleep sesuai selisih waktu yang tersisa.

        Returns:
            Detik yang di-sleep (0 jika tidak perlu menunggu).
        """
        parsed = urlparse(url)
        domain = parsed.netloc.lower()

        now = time.time()
        last = self._last_request.get(domain, 0)
        elapsed = now - last

        if elapsed < self.delay_seconds:
            wait_time = self.delay_seconds - elapsed
            print(f"[Rate Limit]: Menunggu {wait_time:.2f}s sebelum request ke {domain}...")
            time.sleep(wait_time)
            self._last_request[domain] = time.time()
            return wait_time

        self._last_request[domain] = now
        return 0.0

    def reset(self) -> None:
        """Reset semua tracking (berguna untuk testing)."""
        self._last_request.clear()
