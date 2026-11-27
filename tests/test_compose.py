"""Kontrak compose.yaml: profil, key wajib, dan staging tanpa bentrok port."""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
REQUIRED_ENV = {
    "UI_API_KEY": "caller-key",
    "UI_TO_API_KEY": "caller-key",
    "SEARXNG_SECRET": "searxng-secret",
}


def _compose_config(*args: str, extra_env: dict[str, str] | None = None) -> str:
    if shutil.which("docker") is None:
        pytest.skip("Docker CLI is required to render compose.yaml")
    env = {**os.environ, **REQUIRED_ENV, **(extra_env or {})}
    result = subprocess.run(
        ["docker", "compose", "--profile", *args, "config"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        env=env,
    )
    assert result.returncode == 0, result.stderr
    return result.stdout


def test_staging_can_run_alongside_prod_on_host():
    """Staging di host yang sama: port publish Nginx dikendalikan NGINX_PORT."""
    rendered = _compose_config("staging", extra_env={"NGINX_PORT": "8081"})

    assert 'published: "8081"' in rendered


def test_staging_renders_both_nginx_keys():
    """Nginx menerima key browser dan key service terpisah (ADR-0009)."""
    rendered = _compose_config("staging")

    assert "UI_TO_API_KEY" in rendered
    assert "UI_API_KEY" in rendered
