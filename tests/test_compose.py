"""Kontrak Compose diuji dengan file environment sementara yang tidak berisi secrets nyata."""

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SAFE_ENV = {
    "API_ALLOWED_KEYS": "test-caller-key,test-ui-key",
    "UI_API_KEY": "test-ui-key",
    "UI_TO_API_KEY": "test-ui-key",
    "MODELHUB_API_KEY": "test-modelhub-key",
    "MODELHUB_BASE_URL": "https://modelhub.invalid/v1",
    "MODELHUB_MODEL_NAME": "test-model",
    "MLFLOW_TRACING_ENABLED": "false",
    "SEARXNG_SECRET": "test-searxng-secret",
    "SEARXNG_CONTACT_URL": "mailto:admin@example.invalid",
}


def compose_config(*args: str, extra_env: dict[str, str] | None = None) -> dict:
    """Render salinan Compose memakai env-file sementara; tidak membaca `.env` root."""
    if shutil.which("docker") is None:
        pytest.skip("Docker CLI is required to render compose.yaml")

    safe_env = {**SAFE_ENV, **(extra_env or {})}
    with tempfile.TemporaryDirectory(prefix="browsing-agent-compose-") as temp_dir:
        project_dir = Path(temp_dir)
        shutil.copy2(ROOT / "compose.yaml", project_dir / "compose.yaml")
        (project_dir / ".env").write_text(
            "".join(f"{name}={value}\n" for name, value in safe_env.items()),
            encoding="utf-8",
        )
        environment = {
            key: os.environ[key]
            for key in ("PATH", "HOME", "DOCKER_CONFIG", "XDG_RUNTIME_DIR")
            if key in os.environ
        }
        result = subprocess.run(
            [
                "docker",
                "compose",
                "--project-directory",
                str(project_dir),
                "--env-file",
                str(project_dir / ".env"),
                *args,
            ],
            cwd=project_dir,
            capture_output=True,
            text=True,
            env=environment,
        )
        if result.returncode != 0:
            # Jangan masukkan stderr/stdout Compose ke assertion: output dapat memuat env.
            pytest.fail("docker compose config failed with sanitized test environment")
        return json.loads(result.stdout)


def test_plain_compose_starts_core_stack_without_profile():
    """`docker compose up -d` tanpa profil mencakup service inti."""
    rendered = compose_config("config", "--format", "json")

    assert sorted(rendered["services"]) == ["api", "nginx", "redis", "searxng"]


def test_api_defaults_to_searxng_provider():
    """Compose menggunakan SearXNG sebagai provider saat tidak di-override."""
    rendered = compose_config("config", "--format", "json", extra_env={"SEARCH_PROVIDER": ""})

    assert rendered["services"]["api"]["environment"]["SEARCH_PROVIDER"] == "searxng"


def test_staging_can_use_separate_host_port():
    """Port staging dikendalikan oleh `NGINX_PORT`."""
    rendered = compose_config(
        "--profile", "staging", "config", "--format", "json", extra_env={"NGINX_PORT": "8081"}
    )

    assert rendered["services"]["nginx"]["ports"][0]["published"] == "8081"


def test_nginx_keys_come_only_from_sanitized_env_file():
    """Compose env_file terisolasi: output config berisi sentinel test, bukan `.env` root."""
    rendered = compose_config("config", "--format", "json")
    environment = rendered["services"]["nginx"]["environment"]

    assert environment["UI_API_KEY"] == "test-ui-key"
    assert environment["UI_TO_API_KEY"] == "test-ui-key"
    assert rendered["services"]["api"]["environment"]["API_ALLOWED_KEYS"] == (
        "test-caller-key,test-ui-key"
    )


def test_api_routes_mlflow_to_host_gateway_with_existing_experiment():
    rendered = compose_config("config", "--format", "json")
    api = rendered["services"]["api"]
    assert api["extra_hosts"] == ["host.docker.internal=host-gateway"]
    assert api["environment"]["MLFLOW_TRACKING_URI"] == "http://host.docker.internal:5000"
    assert api["environment"]["MLFLOW_EXPERIMENT_ID"] == "1"
