"""
Guardrails keamanan: menolak query atau URL berbahaya.

Query: hanya upaya otomasi/login bypass, paywall bypass, dan personal data harvesting
yang diblokir (sesuai PRD) — kata tunggal seperti "password" pada pertanyaan sah lolos.
URL: domain per-label, path login, serta URL internal/privat (SSRF) ditolak.
"""

import ipaddress
import re
import socket
from urllib.parse import urlparse

# Pola upaya bypass / otomasi ilegal (word boundary, case-insensitive).
_BLOCKED_PATTERNS = re.compile(
    r"\b(?:"
    r"automate login|login automation|auto-?login"
    r"|bypass|paywall|credential stuffing|brute force|harvest|personal data|scrape private"
    r")\b",
    re.IGNORECASE,
)

# Domain sensitif: dicocokkan per label (domain persis atau subdomain-nya).
_BLOCKED_DOMAINS = (
    "bca.co.id",
    "bni.co.id",
    "mandiri.co.id",
    "bri.co.id",
)

_BLOCKED_PATH_SEGMENTS = ("login", "signin", "auth", "admin")


def is_query_blocked(query: str) -> tuple[bool, str]:
    """
    Cek apakah query pengguna mengandung upaya yang dilarang.

    Returns:
        (True, reason) jika query diblokir.
        (False, "") jika lolos.
    """
    match = _BLOCKED_PATTERNS.search(query)
    if match:
        return True, (
            f"[Guardrail]: Query mengandung kata kunci yang tidak diizinkan ('{match.group()}'). "
            "Agen ini tidak melakukan login automation, bypass, atau scraping data pribadi."
        )
    return False, ""


def is_url_blocked(url: str) -> tuple[bool, str]:
    """
    Cek apakah URL menuju domain sensitif atau alamat internal/privat.

    Returns:
        (True, reason) jika URL diblokir.
        (False, "") jika lolos.
    """
    parsed = urlparse(url)
    scheme = parsed.scheme.lower()
    if scheme not in ("http", "https"):
        return True, "[Guardrail]: Hanya URL http/https yang diizinkan."

    hostname = (parsed.hostname or "").lower()
    domain = parsed.netloc.lower()
    if not hostname:
        return True, "[Guardrail]: URL tidak memiliki hostname."

    for blocked in _BLOCKED_DOMAINS:
        if hostname == blocked or hostname.endswith("." + blocked):
            return True, (
                f"[Guardrail]: Domain '{domain}' termasuk dalam daftar yang tidak diizinkan."
            )

    # Tolak URL yang mengandung path login
    path_lower = parsed.path.lower()
    if any(f"/{kw}" in path_lower for kw in _BLOCKED_PATH_SEGMENTS):
        return True, "[Guardrail]: URL mengandung halaman login/autentikasi — tidak diizinkan."

    try:
        port = parsed.port or (443 if scheme == "https" else 80)
    except ValueError:
        return True, "[Guardrail]: Port pada URL tidak valid."

    # Hostname tanpa titik hanya dipakai service internal container (redis, api, searxng).
    if hostname == "localhost" or hostname.endswith(".localhost") or "." not in hostname:
        return True, "[Guardrail]: URL menuju host internal — tidak diizinkan."

    if _resolves_to_private(hostname, port):
        return True, "[Guardrail]: URL menuju alamat internal/privat — tidak diizinkan."

    return False, ""
