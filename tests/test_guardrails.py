"""Unit test guardrails: scope PRD (automation), domain per-label, dan blokir SSRF."""

import socket

import pytest

from policy.guardrails import is_query_blocked, is_url_blocked


def test_automation_keyword_blocks():
    blocked, reason = is_query_blocked("cara automate login instagram")

    assert blocked is True
    assert "Guardrail" in reason


@pytest.mark.parametrize(
    "query",
    [
        "cara ganti password akun email saya",
        "cara reset password saya",
        "tren passwordless authentication terbaru",
        "penjelasan login SSO perusahaan",
    ],
    ids=["ganti-password", "reset-password", "passwordless", "login-sso"],
)
def test_general_questions_about_login_are_allowed(query):
    """Sesuai PRD: yang dilarang adalah otomasi login, bukan pertanyaan sah."""
    blocked, _ = is_query_blocked(query)

    assert blocked is False


@pytest.mark.parametrize(
    "query",
    ["cara bypass paywall koran", "daftar credential stuffing", "cara scrape private data"],
)
def test_bypass_keywords_still_block(query):
    blocked, _ = is_query_blocked(query)

    assert blocked is True


def test_normal_query_allowed():
    blocked, _ = is_query_blocked("berapa kurs dolar hari ini")

    assert blocked is False


def test_blocked_domain_matches_subdomain_only():
    blocked, reason = is_url_blocked("https://ibank.bca.co.id/kurs")

    assert blocked is True
    assert "Guardrail" in reason


def test_domain_lookalike_is_not_blocked(monkeypatch):
    """Pencocokan per label: 'notbca.co.id' bukan subdomain bca.co.id."""
    monkeypatch.setattr("policy.guardrails._resolves_to_private", lambda host, port: False)

    blocked, _ = is_url_blocked("https://notbca.co.id/artikel")

    assert blocked is False


def test_login_path_blocked():
    blocked, _ = is_url_blocked("https://example.com/user/login")

    assert blocked is True


def test_blocked_domains_come_from_config(monkeypatch):
    monkeypatch.setattr("policy.guardrails.config.GUARDRAIL_BLOCKED_DOMAINS", ("blocked.example",))
    monkeypatch.setattr("policy.guardrails._resolves_to_private", lambda host, port: False)

    blocked, _ = is_url_blocked("https://sub.blocked.example/x")

    assert blocked is True


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/admin-health",
        "http://10.0.0.1/",
        "http://192.168.1.10/",
        "http://169.254.169.254/latest/meta-data/",
        "http://redis:6379/",
        "http://api:8000/healthz",
        "http://searxng:8080/search?format=json",
        "http://localhost:8000/",
        "http://2130706433/",
        "http://0x7f000001/",
        "http://[::ffff:127.0.0.1]/",
        "file:///etc/passwd",
    ],
    ids=[
        "loopback",
        "private-10",
        "private-192",
        "cloud-metadata",
        "compose-redis",
        "compose-api",
        "compose-searxng",
        "localhost",
        "decimal-ip",
        "hex-ip",
        "ipv4-mapped-ipv6",
        "file-scheme",
    ],
)
def test_internal_and_private_urls_blocked(url):
    blocked, _ = is_url_blocked(url)

    assert blocked is True


def test_unresolvable_hostname_blocked(monkeypatch):
    def _raise(host, port, *args, **kwargs):
        raise OSError("Name or service not known")

    monkeypatch.setattr("policy.guardrails.socket.getaddrinfo", _raise)

    blocked, _ = is_url_blocked("https://tidak-ada.example.invalid/")

    assert blocked is True


def test_ipv6_lookup_failure_does_not_block_public_ipv4(monkeypatch):
    """Host A-only (tanpa AAAA) tetap boleh; kegagalan satu family bukan alasan blokir."""

    def getaddrinfo(host, port, family, *args, **kwargs):
        if family == socket.AF_INET:
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", port))]
        raise OSError("no ipv6 record")

    monkeypatch.setattr("policy.guardrails.socket.getaddrinfo", getaddrinfo)

    blocked, _ = is_url_blocked("https://example.com/article")

    assert blocked is False


def test_private_ipv6_still_blocks_with_public_ipv4(monkeypatch):
    def getaddrinfo(host, port, family, *args, **kwargs):
        if family == socket.AF_INET:
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", port))]
        return [(socket.AF_INET6, socket.SOCK_STREAM, 6, "", ("fd00::1", port, 0, 0))]

    monkeypatch.setattr("policy.guardrails.socket.getaddrinfo", getaddrinfo)

    blocked, _ = is_url_blocked("https://example.com/article")

    assert blocked is True


def test_public_url_allowed(monkeypatch):
    monkeypatch.setattr(
        "policy.guardrails.socket.getaddrinfo",
        lambda host, port, *args, **kwargs: [(2, 1, 6, "", ("93.184.216.34", port))],
    )

    blocked, _ = is_url_blocked("https://example.com/article")

    assert blocked is False
