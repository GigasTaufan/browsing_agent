"""
Guardrails keamanan: menolak query atau URL berbahaya.
"""

import re
from urllib.parse import urlparse


# Keyword yang mengindikasikan upaya bypass / scraping ilegal
_BLOCKED_KEYWORDS = [
    "bypass", "login", "password", "credential", "paywall",
    "personal data", "harvest", "scrape private", "automate login",
    "credential stuffing", "brute force",
]

# Domain / pattern yang sensitif — tidak perlu di-fetch
_BLOCKED_DOMAINS = [
    "bca.co.id", "bni.co.id", "mandiri.co.id", "bri.co.id",
    "bca.co.id", "login.", "signin.", "auth.", "bank",
]


def is_query_blocked(query: str) -> tuple[bool, str]:
    """
    Cek apakah query pengguna mengandung upaya yang dilarang.

    Returns:
        (True, reason) jika query diblokir.
        (False, "") jika lolos.
    """
    lowered = query.lower()
    for keyword in _BLOCKED_KEYWORDS:
        if keyword in lowered:
            return True, (
                f"[Guardrail]: Query mengandung kata kunci yang tidak diizinkan ('{keyword}'). "
                "Agen ini tidak melakukan login automation, bypass, atau scraping data pribadi."
            )
    return False, ""


def is_url_blocked(url: str) -> tuple[bool, str]:
    """
    Cek apakah URL termasuk domain yang sensitif / berbahaya.

    Returns:
        (True, reason) jika URL diblokir.
        (False, "") jika lolos.
    """
    parsed = urlparse(url)
    domain = parsed.netloc.lower()

    for blocked in _BLOCKED_DOMAINS:
        if blocked in domain:
            return True, (
                f"[Guardrail]: Domain '{domain}' termasuk dalam daftar yang tidak diizinkan."
            )

    # Tolak URL yang mengandung path login
    path_lower = parsed.path.lower()
    if any(kw in path_lower for kw in ["/login", "/signin", "/auth", "/admin"]):
        return True, "[Guardrail]: URL mengandung halaman login/autentikasi — tidak diizinkan."

    return False, ""
