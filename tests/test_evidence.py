"""
Unit test untuk storage/evidence.py.
Verifikasi deduplikasi dan citations.
"""

from storage.evidence import EvidenceStore
from tools.extract import ExtractedPage


def make_extracted(url: str, text: str, title: str = None) -> ExtractedPage:
    """Helper untuk membuat ExtractedPage."""
    return ExtractedPage(
        url=url,
        title=title,
        main_text=text,
        canonical_url=url,
        headings=[],
        links=[],
        fetched_at="2024-01-01T00:00:00+00:00",
        status_code=200,
    )


def test_evidence_store_add_unique():
    """Menambahkan evidence unik berhasil."""
    store = EvidenceStore()
    extracted = make_extracted("https://example.com/a", "Konten unik A", "Judul A")

    item = store.add(extracted)

    assert item is not None
    assert item.title == "Judul A"
    assert len(store.items) == 1


def test_evidence_store_dedup_by_url():
    """Duplikat berdasarkan URL tidak ditambahkan."""
    store = EvidenceStore()

    extracted1 = make_extracted("https://example.com/a", "Konten A", "Judul A")
    store.add(extracted1)

    extracted2 = make_extracted("https://example.com/a", "Konten B", "Judul B")
    item2 = store.add(extracted2)

    assert item2 is None  # Duplikat — ditolak
    assert len(store.items) == 1


def test_evidence_store_dedup_by_similar_content():
    """Duplikat dengan konten serupa (hash sama) ditolak."""
    store = EvidenceStore()

    extracted1 = make_extracted("https://example.com/a", "Sama persis", "Judul A")
    store.add(extracted1)

    # URL berbeda, tapi canonical berbeda dan konten sama 500 karakter pertama
    extracted2 = make_extracted("https://other.com/b", "Sama persis", "Judul B")
    extracted2.canonical_url = "https://example.com/a"
    item2 = store.add(extracted2)

    assert item2 is None
    assert len(store.items) == 1


def test_evidence_citations_format():
    """Citations dalam format yang benar."""
    store = EvidenceStore()

    store.add(make_extracted("https://a.com", "Teks A", "Judul A"))
    store.add(make_extracted("https://b.com", "Teks B", "Judul B"))

    citations = store.get_citations()
    assert len(citations) == 2
    assert "[Judul A](https://a.com)" in citations[0]
    assert "[Judul B](https://b.com)" in citations[1]
