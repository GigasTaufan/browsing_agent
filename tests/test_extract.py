"""
Unit test untuk tools/extract.py.
Menggunakan HTML fixture langsung di kode (tanpa request eksternal).
"""

from tools.extract import extract_page, _chunk_text


SIMPLE_HTML = """<!DOCTYPE html>
<html>
<head><title>Halaman Contoh</title>
<link rel="canonical" href="https://example.com/canonical-page" />
</head>
<body>
<h1>Judul Utama</h1>
<p>Ini adalah paragraf pertama dari konten halaman.</p>
<h2>Sub Judul</h2>
<p>Paragraf kedua dengan lebih banyak teks untuk testing.</p>
<a href="/relative-link">Link Relatif</a>
<a href="https://other.com/absolute-link">Link Absolut</a>
</body>
</html>"""


def test_extract_basic_structure():
    """Ekstraksi menghasilkan semua field yang diharapkan."""
    result = extract_page(SIMPLE_HTML, "https://example.com/page")

    assert result.url == "https://example.com/page"
    assert result.title == "Halaman Contoh"
    assert result.canonical_url == "https://example.com/canonical-page"
    assert "Judul Utama" in result.headings
    assert "Sub Judul" in result.headings
    assert len(result.links) >= 2
    assert result.status_code == 200
    assert result.fetched_at  # tidak kosong


def test_extract_main_text_not_empty():
    """Main text harus berisi konten halaman."""
    result = extract_page(SIMPLE_HTML, "https://example.com/page")

    assert len(result.main_text) > 50
    assert "paragraf pertama" in result.main_text


def test_chunking_short_text():
    """Teks pendek tidak di-chunk."""
    chunks = _chunk_text("Ini teks pendek.", chunk_size=100)
    assert len(chunks) == 1
    assert chunks[0] == "Ini teks pendek."


def test_chunking_long_text():
    """Teks panjang di-chunk menjadi beberapa bagian."""
    long_text = "kata " * 1000  # Lebih dari default chunk_size 2000
    chunks = _chunk_text(long_text, chunk_size=100)
    assert len(chunks) > 1
