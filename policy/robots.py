"""
Pengecekan kebijakan robots.txt menggunakan urllib.robotparser.
Meng-cache robots.txt per domain untuk mencegah fetch ulang.
"""

import time
import urllib.error
import urllib.request
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import config

# Cache robots.txt parser per domain: {domain: RobotFileParser}
_robots_cache: dict[str, RobotFileParser] = {}
_cache_timestamp: dict[str, float] = {}
_CACHE_TTL_SECONDS = config.ROBOTS_CACHE_TTL_SECONDS


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
        # 404 = robots.txt tidak ada -> RFC 9309: semua diizinkan.
        # Error lain (timeout, 5xx, DNS): ikut kebijakan ROBOTS_FAIL_OPEN.
        is_404 = isinstance(e, urllib.error.HTTPError) and e.code == 404
        allow = is_404 or config.ROBOTS_FAIL_OPEN
        verdict = "Diizinkan" if allow else "Ditolak"
        print(f"[Robots Policy]: Gagal mengambil {robots_url} ({e}). {verdict}.")
        if allow:
            rp.allow_all = True  # type: ignore[attr-defined]  # atribut runtime stdlib
        else:
            rp.disallow_all = True  # type: ignore[attr-defined]  # atribut runtime stdlib

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
    if domain not in _robots_cache or (now - _cache_timestamp.get(domain, 0)) > _CACHE_TTL_SECONDS:
        robots_url = _get_robots_url(target_url)
        _robots_cache[domain] = _fetch_robots_txt(robots_url)
        _cache_timestamp[domain] = now

    return _robots_cache[domain]


def is_url_allowed(target_url: str, user_agent: str | None = None) -> bool:
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
        return config.ROBOTS_FAIL_OPEN  # Fail-open default: izinkan jika parser error
