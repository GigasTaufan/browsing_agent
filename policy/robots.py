"""
Pengecekan kebijakan robots.txt menggunakan urllib.robotparser.
Meng-cache robots.txt per domain untuk mencegah fetch ulang.
"""

import time
from urllib.parse import urlparse, urljoin
from urllib.robotparser import RobotFileParser
import urllib.request

import config


# Cache robots.txt parser per domain: {domain: RobotFileParser}
_robots_cache: dict[str, RobotFileParser] = {}
_cache_timestamp: dict[str, float] = {}
_CACHE_TTL_SECONDS = 3600  # Cache robots.txt selama 1 jam


def _get_robots_url(target_url: str) -> str:
    """Bangun URL robots.txt dari URL target."""
    parsed = urlparse(target_url)
    base = f"{parsed.scheme}://{parsed.netloc}"
    return urljoin(base, "/robots.txt")


def _fetch_robots_txt(robots_url: str) -> RobotFileParser:
    """
    Ambil dan parse robots.txt dari URL.
    Gunakan timeout dan user-agent yang transparan.
    """
    rp = RobotFileParser()
    rp.set_url(robots_url)

    try:
        req = urllib.request.Request(
            robots_url,
            headers={"User-Agent": config.USER_AGENT},
            method="GET",
        )
        with urllib.request.urlopen(req, timeout=config.REQUEST_TIMEOUT) as response:
            # Parse langsung dari bytes response
            rp.parse(response.read().decode("utf-8", errors="replace").splitlines())
    except Exception as e:
        # Jika gagal ambil robots.txt (404, timeout, dll), anggap semua boleh
        print(f"[Robots Policy]: Gagal mengambil {robots_url} ({e}). Asumsikan diizinkan.")
        # Allow all fallback
        rp.allow_all = True

    return rp


def get_robots_parser(target_url: str) -> RobotFileParser:
    """
    Mengembalikan RobotFileParser untuk domain dari URL target.
    Menggunakan cache dengan TTL 1 jam.
    """
    parsed = urlparse(target_url)
    domain = parsed.netloc.lower()

    now = time.time()

    # Cache miss atau cache expired
    if (
        domain not in _robots_cache
        or (now - _cache_timestamp.get(domain, 0)) > _CACHE_TTL_SECONDS
    ):
        robots_url = _get_robots_url(target_url)
        _robots_cache[domain] = _fetch_robots_txt(robots_url)
        _cache_timestamp[domain] = now

    return _robots_cache[domain]


def is_url_allowed(target_url: str, user_agent: str = None) -> bool:
    """
    Cek apakah URL diizinkan oleh robots.txt domain-nya.
    Meng-handle edge case: jika robots.txt tidak bisa di-fetch, asumsikan diizinkan.
    """
    if not target_url.startswith(("http://", "https://")):
        return False  # URL tidak valid — tolak

    ua = user_agent or config.USER_AGENT
    rp = get_robots_parser(target_url)

    # Jika cache menggunakan fallback allow_all, langsung return True
    if getattr(rp, "allow_all", False):
        return True

    try:
        return rp.can_fetch(ua, target_url)
    except Exception as e:
        print(f"[Robots Policy]: Error parsing robots.txt untuk {target_url}: {e}")
        return True  # Fail-open: izinkan jika parser error


def clear_robots_cache() -> None:
    """Bersihkan cache robots.txt (berguna untuk testing)."""
    _robots_cache.clear()
    _cache_timestamp.clear()
