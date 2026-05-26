"""
Ekstraksi konten terstruktur dari halaman web.
Menggunakan trafilatura untuk main text dan BeautifulSoup untuk metadata.
"""

from datetime import datetime, timezone
from typing import List, Optional
from urllib.parse import urljoin

try:
    import trafilatura
    TRAFILATURA_AVAILABLE = True
except ImportError:
    TRAFILATURA_AVAILABLE = False

from bs4 import BeautifulSoup
from pydantic import BaseModel

import config


class ExtractedPage(BaseModel):
    """
    Struktur data hasil ekstraksi konten dari halaman web.
    """
    url: str
    title: Optional[str] = None
    canonical_url: Optional[str] = None
    main_text: str = ""
    headings: List[str] = []
    links: List[str] = []
    text_chunks: List[str] = []
    fetched_at: str = ""
    status_code: int = 200


def _extract_with_bs4(soup: BeautifulSoup, url: str) -> tuple[str, str, List[str], List[str]]:
    """
    Ekstraksi fallback menggunakan BeautifulSoup.
    Returns: (main_text, title, headings_list, links_list)
    """
    # Title
    title = None
    title_tag = soup.find("title")
    if title_tag:
        title = title_tag.get_text(strip=True)

    # Canonical URL
    canonical = None
    canonical_tag = soup.find("link", rel="canonical")
    if canonical_tag:
        canonical = canonical_tag.get("href")
        if canonical and canonical.startswith("/"):
            canonical = urljoin(url, canonical)

    # Headings
    headings = []
    for level in range(1, 7):
        for h in soup.find_all(f"h{level}"):
            text = h.get_text(strip=True)
            if text:
                headings.append(text)

    # Links
    links = []
    for a in soup.find_all("a", href=True):
        href = a.get("href")
        if href:
            links.append(urljoin(url, href))

    # Main text: prefer <main> atau <article>, fallback <body>
    main_tag = soup.find("main") or soup.find("article") or soup.find("body")
    if main_tag:
        main_text = " ".join(main_tag.get_text(separator=" ", strip=True).split())
    else:
        main_text = " ".join(soup.get_text(separator=" ", strip=True).split())

    return main_text, title, headings, list(set(links))  # dedup links


def _extract_with_trafilatura(html: str, url: str) -> Optional[str]:
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


def _chunk_text(text: str, chunk_size: int = None) -> List[str]:
    """
    Memotong teks panjang menjadi chunk berukuran chunk_size (default dari config).
    Split pada spasi terdekat untuk tidak memotong kata.
    """
    chunk_size = chunk_size or config.CHUNK_SIZE
    if len(text) <= chunk_size:
        return [text]

    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        if end < len(text):
            # Cari spasi terdekat ke belakang untuk split keren
            space_pos = text.rfind(" ", start, end + 1)
            if space_pos > start:
                end = space_pos
        chunks.append(text[start:end].strip())
        start = end

    return chunks


def extract_page(html: str, url: str, status_code: int = 200) -> ExtractedPage:
    """
    Mengekstrak konten terstruktur dari HTML halaman web.

    Alur:
        1. Parse dengan BeautifulSoup untuk metadata (title, canonical, headings, links).
        2. Gunakan trafilatura untuk main text (lebih bersih).
        3. Fallback ke BeautifulSoup body text jika trafilatura gagal.
        4. Chunking jika main_text terlalu panjang.
    """
    soup = BeautifulSoup(html, "lxml")

    # Metadata dari BS4
    main_text_bs, title, headings, links = _extract_with_bs4(soup, url)

    # Main text dari trafilatura (lebih bersih)
    main_text = _extract_with_trafilatura(html, url)

    # Fallback ke BS4 jika trafilatura kosong
    if not main_text:
        main_text = main_text_bs

    # Canonical URL juga dari BS4
    canonical_url = None
    canonical_tag = soup.find("link", rel="canonical")
    if canonical_tag:
        canonical_url = canonical_tag.get("href")
        if canonical_url and canonical_url.startswith("/"):
            canonical_url = urljoin(url, canonical_url)

    # Chunking
    text_chunks = _chunk_text(main_text)

    return ExtractedPage(
        url=url,
        title=title,
        canonical_url=canonical_url or url,
        main_text=main_text,
        headings=headings,
        links=list(dict.fromkeys(links)),  # Deduplicate preserve order
        text_chunks=text_chunks,
        fetched_at=datetime.now(timezone.utc).isoformat(),
        status_code=status_code,
    )
