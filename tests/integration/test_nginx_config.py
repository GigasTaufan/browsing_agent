"""Smoke checks for the Nginx ingress contract without provider credentials."""

import json
import re
import shutil
import subprocess
import time
import uuid
from pathlib import Path

import pytest

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

    assert "proxy_pass $api_upstream;" in caller
    assert "proxy_set_header Authorization $http_authorization;" in caller


def test_ui_ingress_uses_server_key_and_never_serves_it_to_browser():
    config = NGINX_TEMPLATE.read_text(encoding="utf-8")
    ui = _location_block(config, "/ui-api/")

    assert "rewrite ^/ui-api/(.*)$ /api/$1 break;" in ui
    assert "proxy_pass $api_upstream;" in ui
    assert 'proxy_set_header Authorization "Bearer ${UI_API_KEY}";' in ui
    for asset in (FRONTEND / "index.html", FRONTEND / "app.js"):
        assert "UI_API_KEY" not in asset.read_text(encoding="utf-8")


def test_upstream_dns_is_reresolved_at_runtime():
    """Resolver + variable upstream agar rebuild api tidak menyebabkan 502 stale IP."""
    config = NGINX_TEMPLATE.read_text(encoding="utf-8")

    assert "resolver 127.0.0.11 valid=10s ipv6=off;" in config
    assert "set $api_upstream http://api:8000;" in config


def test_valid_caller_request_succeeds_through_nginx_with_stub_backend(tmp_path):
    if shutil.which("docker") is None:
        pytest.skip("Docker CLI is required for the Nginx integration smoke test")
    if subprocess.run(["docker", "info"], capture_output=True).returncode != 0:
        pytest.skip("Docker daemon is unavailable")

    suffix = uuid.uuid4().hex[:12]
    network = f"task5-{suffix}"
    stub_name = f"task5-api-{suffix}"
    nginx_name = f"task5-nginx-{suffix}"
    caller_key = "task5-caller-smoke-key"
    stub_script = tmp_path / "stub_api.py"
    stub_script.write_text(
        """from http.server import BaseHTTPRequestHandler, HTTPServer
import json

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path != "/healthz":
            self.send_error(404)
            return
        body = b"ok"
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        if self.path != "/api/v1/ask" or self.headers.get("Authorization") != "Bearer task5-caller-smoke-key":
            self.send_response(401)
            self.end_headers()
            return
        length = int(self.headers.get("Content-Length", "0"))
        request = json.loads(self.rfile.read(length))
        payload = {
            "answer": "Stub response through Nginx.",
            "citations": [{"id": 1, "url": "https://example.test/source", "snippet": request["question"]}],
        }
        body = json.dumps(payload).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass

HTTPServer(("0.0.0.0", 8000), Handler).serve_forever()
""",
        encoding="utf-8",
    )

    def docker(*args, check=True):
        return subprocess.run(["docker", *args], capture_output=True, text=True, check=check)

    try:
        docker("network", "create", network)
        docker(
            "run",
            "--detach",
            "--name",
            stub_name,
            "--network",
            network,
            "--network-alias",
            "api",
            "--volume",
            f"{stub_script}:/stub_api.py:ro,Z",
            "python:3.14-slim",
            "python",
            "/stub_api.py",
        )
        docker(
            "run",
            "--detach",
            "--name",
            nginx_name,
            "--network",
            network,
            "--env",
            f"UI_API_KEY={caller_key}",
            "--volume",
            f"{FRONTEND}:/usr/share/nginx/html:ro,Z",
            "--volume",
            f"{NGINX_TEMPLATE}:/etc/nginx/templates/default.conf.template:ro,Z",
            "nginx:alpine",
        )

        deadline = time.monotonic() + 15
        response = None
        while time.monotonic() < deadline:
            response = docker(
                "exec",
                nginx_name,
                "wget",
                "-qO-",
                "http://127.0.0.1/healthz",
                check=False,
            )
            if response.returncode == 0:
                break
            time.sleep(0.1)
        nginx_logs = docker("logs", nginx_name, check=False).stderr
        assert response is not None and response.returncode == 0, (
            f"Nginx did not become ready: {nginx_logs}"
        )

        deadline = time.monotonic() + 15
        response = None
        while time.monotonic() < deadline:
            response = docker(
                "exec",
                nginx_name,
                "wget",
                "-qO-",
                "http://api:8000/healthz",
                check=False,
            )
            if response.returncode == 0 and response.stdout == "ok":
                break
            time.sleep(0.1)
        assert response is not None and response.returncode == 0 and response.stdout == "ok", (
            "API stub did not become ready before the ingress request"
        )

        result = docker(
            "exec",
            nginx_name,
            "wget",
            "-qO-",
            '--post-data={"question":"Ingress smoke question"}',
            f"--header=Authorization: Bearer {caller_key}",
            "--header=Content-Type: application/json",
            "http://127.0.0.1/api/v1/ask",
        )
        assert json.loads(result.stdout) == {
            "answer": "Stub response through Nginx.",
            "citations": [
                {
                    "id": 1,
                    "url": "https://example.test/source",
                    "snippet": "Ingress smoke question",
                }
            ],
        }
    finally:
        docker("rm", "--force", nginx_name, check=False)
        docker("rm", "--force", stub_name, check=False)
        docker("network", "rm", network, check=False)
