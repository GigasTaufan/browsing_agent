"""Unit test guardrails: keyword word-boundary dan domain filter."""

from policy.guardrails import is_query_blocked, is_url_blocked


def test_blocked_keyword_as_standalone_word():
    blocked, reason = is_query_blocked("cara reset password saya")

    assert blocked is True
    assert "Guardrail" in reason


def test_keyword_inside_larger_word_is_allowed():
    """Presisi: 'passwordless' tidak tertangkap keyword 'password'."""
    blocked, _ = is_query_blocked("tren passwordless authentication terbaru")

    assert blocked is False


def test_multi_word_keyword_blocks():
    blocked, _ = is_query_blocked("cara scrape private data instagram")

    assert blocked is True


def test_normal_query_allowed():
    blocked, _ = is_query_blocked("berapa kurs dolar hari ini")

    assert blocked is False


def test_blocked_domain():
    blocked, reason = is_url_blocked("https://bca.co.id/kurs")

    assert blocked is True
    assert "Guardrail" in reason


def test_login_path_blocked():
    blocked, _ = is_url_blocked("https://example.com/user/login")

    assert blocked is True


def test_normal_url_allowed():
    blocked, _ = is_url_blocked("https://example.com/article")

    assert blocked is False
