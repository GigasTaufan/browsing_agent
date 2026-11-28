"""
Unit test untuk tools/extract.py.
Menggunakan HTML fixture langsung di kode (tanpa request eksternal).
"""

from tools.extract import extract_page

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
    assert result.status_code == 200
    assert result.fetched_at  # tidak kosong


def test_extract_main_text_not_empty():
    """Main text harus berisi konten halaman."""
    result = extract_page(SIMPLE_HTML, "https://example.com/page")

    assert len(result.main_text) > 50
    assert "paragraf pertama" in result.main_text
