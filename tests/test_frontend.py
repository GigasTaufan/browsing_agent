"""
Contract test frontend statis: struktur, endpoint, dan bebas kredensial.
Dijalankan di CI (tanpa browser) sebagai smoke test UI (T-13).
"""

import re
from pathlib import Path

FRONTEND = Path(__file__).resolve().parents[1] / "frontend"
ASSETS = ["index.html", "app.js", "style.css"]


def _read(name: str) -> str:
    path = FRONTEND / name
    assert path.exists(), f"{name} wajib ada di frontend/"
    return path.read_text(encoding="utf-8")


def test_all_assets_exist():
    for name in ASSETS:
        _read(name)


def test_index_declares_form_and_mounts_app():
    html = _read("index.html")

    assert 'id="question-form"' in html
    assert 'id="question"' in html
    assert 'src="/app.js"' in html
    assert 'href="/style.css"' in html
    assert 'lang="id"' in html


def test_app_js_calls_ui_api_endpoint_only():
    """Frontend hanya boleh memanggil /ui-api/ (key disuntik Nginx, ADR-0003)."""
    js = _read("app.js")

    assert "/ui-api/v1/ask" in js
    # Tidak boleh ada pemanggilan langsung ke /api/ (butuh key di browser).
    assert not re.search(r"fetch\(\s*[\"']/api/", js)


def test_no_credentials_or_secrets_in_assets():
    """Tidak ada API key/token/pattern kredensial di aset statis."""
    secret_patterns = [
        "UI_API_KEY",
        "API_ALLOWED_KEYS",
        "MODELHUB_API_KEY",
        "AZURE_OPENAI_API_KEY",
        "Bearer ",
        "sk-",
    ]
    for name in ASSETS:
        content = _read(name)
        for pattern in secret_patterns:
            assert pattern not in content, f"{pattern} ditemukan di {name}"
