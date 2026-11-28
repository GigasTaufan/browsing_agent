"""
Ekstraksi konten terstruktur dari halaman web.
Menggunakan trafilatura untuk main text dan BeautifulSoup untuk metadata.
"""

from datetime import UTC, datetime
from urllib.parse import urljoin

try:
    import trafilatura

    TRAFILATURA_AVAILABLE = True
except ImportError:
    TRAFILATURA_AVAILABLE = False

from bs4 import BeautifulSoup, Tag
from pydantic import BaseModel


class ExtractedPage(BaseModel):
    """
    Struktur data hasil ekstraksi konten dari halaman web.
    """

    url: str
    title: str | None = None
    canonical_url: str | None = None
    main_text: str = ""
    headings: list[str] = []
    fetched_at: str = ""
    status_code: int = 200


def _get_str_attr(tag: Tag, name: str) -> str | None:
    """Ambil atribut tag sebagai string (abaikan nilai berupa list)."""
    value = tag.get(name)
    if isinstance(value, str):
        return value
    return None


def _extract_with_bs4(soup: BeautifulSoup, url: str) -> tuple[str, str | None, list[str]]:
    """
    Ekstraksi fallback menggunakan BeautifulSoup.
    Returns: (main_text, title, headings_list)
    """
    # Title
    title = None
    title_tag = soup.find("title")
    if title_tag:
        title = title_tag.get_text(strip=True)

    # Headings
    headings = []
    for level in range(1, 7):
        for h in soup.find_all(f"h{level}"):
            text = h.get_text(strip=True)
            if text:
                headings.append(text)

    # Main text: prefer <main> atau <article>, fallback <body>
    main_tag = soup.find("main") or soup.find("article") or soup.find("body")
    if main_tag:
        main_text = " ".join(main_tag.get_text(separator=" ", strip=True).split())
    else:
        main_text = " ".join(soup.get_text(separator=" ", strip=True).split())

    return main_text, title, headings


def _extract_with_trafilatura(html: str, url: str) -> str | None:
    """
    Ekstraksi main text menggunakan trafilatura.
    Returns main text atau None jika gagal / tidak tersedia.
    """
    if not TRAFILATURA_AVAILABLE:
        return None

    try:
        text = trafilatura.extract(
            html,
            url=url,
            include_comments=False,
            include_tables=False,
            deduplicate=True,
        )
        return text.strip() if text else None
    except Exception:
        return None


def extract_page(html: str, url: str, status_code: int = 200) -> ExtractedPage:
    """
    Mengekstrak konten terstruktur dari HTML halaman web.

    Alur:
        1. Parse dengan BeautifulSoup untuk metadata (title, canonical, headings).
        2. Gunakan trafilatura untuk main text (lebih bersih).
        3. Fallback ke BeautifulSoup body text jika trafilatura gagal.
    """
    soup = BeautifulSoup(html, "lxml")

    # Metadata dari BS4
    main_text_bs, title, headings = _extract_with_bs4(soup, url)

    # Main text dari trafilatura (lebih bersih)
    main_text = _extract_with_trafilatura(html, url)

    # Fallback ke BS4 jika trafilatura kosong
    if not main_text:
        main_text = main_text_bs

    # Canonical URL juga dari BS4
    canonical_url = None
    canonical_tag = soup.find("link", rel="canonical")
    if canonical_tag:
        canonical_url = _get_str_attr(canonical_tag, "href")
        if canonical_url and canonical_url.startswith("/"):
            canonical_url = urljoin(url, canonical_url)

    return ExtractedPage(
        url=url,
        title=title,
        canonical_url=canonical_url or url,
        main_text=main_text,
        headings=headings,
        fetched_at=datetime.now(UTC).isoformat(),
        status_code=status_code,
    )
