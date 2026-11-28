"""
Unit test untuk storage/evidence.py.
Verifikasi deduplikasi dan urutan item evidence.
"""

import pytest

import config
from storage.evidence import EvidenceStore
from tools.extract import ExtractedPage


def make_extracted(url: str, text: str, title: str | None = None) -> ExtractedPage:
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


def test_evidence_keeps_unique_items_in_fetch_order():
    """Jawaban & citations memakai `items` apa adanya: urutan fetch, tanpa duplikat."""
    store = EvidenceStore()

    store.add(make_extracted("https://a.com", "Teks A", "Judul A"))
    store.add(make_extracted("https://b.com", "Teks B", "Judul B"))
    store.add(make_extracted("https://a.com", "Teks A", "Judul A"))

    assert [item.url for item in store.items] == ["https://a.com", "https://b.com"]
    assert store.items[0].canonical_url == "https://a.com"
    assert store.items[1].title == "Judul B"


@pytest.mark.parametrize("status,text", [(404, "Error page"), (200, "  "), (500, "Server error")])
def test_failed_and_empty_pages_are_not_citations(status, text):
    page = make_extracted("https://example.com/a", text)
    page.status_code = status
    store = EvidenceStore()
    assert store.add(page) is None
    assert store.items == []


def test_snippet_length_comes_from_config(monkeypatch):
    monkeypatch.setattr(config, "EVIDENCE_SNIPPET_CHARS", 5)
    store = EvidenceStore()

    item = store.add(make_extracted("https://example.com/a", "abcdefghij"))

    assert item is not None
    assert item.snippet == "abcde"


def test_hash_window_comes_from_config(monkeypatch):
    monkeypatch.setattr(config, "EVIDENCE_HASH_CHARS", 4)
    first = make_extracted("https://a.example/x", "abcd1111")
    second = make_extracted("https://b.example/y", "abcd2222")
    first.canonical_url = second.canonical_url = "https://canonical.example/page"

    assert EvidenceStore._compute_hash(first) == EvidenceStore._compute_hash(second)

    monkeypatch.setattr(config, "EVIDENCE_HASH_CHARS", 6)

    assert EvidenceStore._compute_hash(first) != EvidenceStore._compute_hash(second)
