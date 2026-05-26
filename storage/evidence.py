"""
Penyimpanan evidence dan citations.
Menyimpan hasil ekstraksi dari setiap URL yang di-fetch.
Mendukung deduplikasi berdasarkan content hash dan canonical URL.
"""

import hashlib
from typing import List

from pydantic import BaseModel

from tools.extract import ExtractedPage


class EvidenceItem(BaseModel):
    """
    Satu item evidence yang merepresentasikan satu halaman yang berhasil di-fetch.
    """
    url: str
    title: str | None = None
    snippet: str = ""
    canonical_url: str = ""
    fetched_at: str = ""
    content_hash: str = ""


class EvidenceStore:
    """
    Menyimpan evidence dari hasil fetch dan menyediakan deduplikasi.
    """

    def __init__(self):
        # List evidence yang sudah tersimpan (unik)
        self.items: List[EvidenceItem] = []
        # Set untuk deteksi duplikat
        self._hashes: set[str] = set()
        self._canonical_urls: set[str] = set()

    @staticmethod
    def _compute_hash(extracted: ExtractedPage) -> str:
        """
        Menghitung content hash dari canonical_url + snippet main_text (500 karakter pertama).
        """
        canonical = extracted.canonical_url or extracted.url
        snippet = extracted.main_text[:500] if extracted.main_text else ""
        raw = f"{canonical}||{snippet}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def dedup_by_hash(self, extracted: ExtractedPage) -> bool:
        """
        Cek apakah konten ini sudah pernah disimpan (duplikat).

        Returns:
            True jika DUPLIKAT (sudah ada), False jika unik (belum ada).
        """
        content_hash = self._compute_hash(extracted)
        canonical = extracted.canonical_url or extracted.url

        if content_hash in self._hashes or canonical in self._canonical_urls:
            return True
        return False

    def add(self, extracted: ExtractedPage) -> EvidenceItem | None:
        """
        Tambahkan hasil ekstraksi ke store.
        Jika duplikat, return None.

        Returns:
            EvidenceItem yang baru ditambahkan, atau None jika duplikat.
        """
        if self.dedup_by_hash(extracted):
            return None

        content_hash = self._compute_hash(extracted)
        canonical = extracted.canonical_url or extracted.url

        item = EvidenceItem(
            url=extracted.url,
            title=extracted.title,
            snippet=extracted.main_text[:300] if extracted.main_text else "",
            canonical_url=canonical,
            fetched_at=extracted.fetched_at,
            content_hash=content_hash,
        )

        self.items.append(item)
        self._hashes.add(content_hash)
        self._canonical_urls.add(canonical)
        return item

    def get_citations(self) -> List[str]:
        """
        Kembalikan daftar string citation dalam format:
        [index]. [Judul](URL)
        """
        lines = []
        for i, item in enumerate(self.items, start=1):
            title = item.title or item.canonical_url
            lines.append(f"{i}. [{title}]({item.canonical_url})")
        return lines

    def get_citations_text(self) -> str:
        """Kembalikan citations sebagai satu string yang sudah diformat."""
        if not self.items:
            return ""
        header = "\n---\nSumber:\n"
        return header + "\n".join(self.get_citations())
