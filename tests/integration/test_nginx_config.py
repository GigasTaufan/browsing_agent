"""Smoke checks for the Nginx ingress contract without provider credentials."""

from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[2]
NGINX_TEMPLATE = ROOT / "nginx" / "default.conf.template"
FRONTEND = ROOT / "frontend"


def _location_block(config: str, path: str) -> str:
    match = re.search(
        rf"location\s+{re.escape(path)}\s*\{{(?P<body>.*?)\n\s*\}}",
        config,
        re.DOTALL,
    )
    assert match is not None, f"location {path} must be configured"
    return match.group("body")


def test_caller_ingress_forwards_auth_header_to_api():
    config = NGINX_TEMPLATE.read_text(encoding="utf-8")
    caller = _location_block(config, "/api/")

    assert "proxy_pass http://api:8000;" in caller
    assert "proxy_set_header Authorization $http_authorization;" in caller


def test_ui_ingress_uses_server_key_and_never_serves_it_to_browser():
    config = NGINX_TEMPLATE.read_text(encoding="utf-8")
    ui = _location_block(config, "/ui-api/")

    assert "proxy_pass http://api:8000/api/;" in ui
    assert 'proxy_set_header Authorization "Bearer ${UI_API_KEY}";' in ui
    for asset in (FRONTEND / "index.html", FRONTEND / "app.js"):
        assert "UI_API_KEY" not in asset.read_text(encoding="utf-8")
