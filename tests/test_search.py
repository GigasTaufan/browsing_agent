from unittest.mock import patch

import pytest

from tools import search as search_module


def test_search_retries_ddg_then_auto_and_preserves_result_format(monkeypatch):
    calls = []
    results = [
        {"title": "General", "href": "https://example.com/page", "body": "general snippet"},
        {"title": "Official", "href": "https://example.gov/page", "body": "official snippet"},
    ]

    class FakeDDGS:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            return False

        def text(self, query, **kwargs):
            calls.append((query, kwargs))
            if len(calls) < 3:
                raise RuntimeError("backend unavailable")
            return results

    monkeypatch.setattr(search_module, "DDGS", FakeDDGS)

    with patch.object(search_module.time, "sleep") as sleep:
        answer = search_module.search_tool.invoke({"query": "test query"})

    assert [call[1]["backend"] for call in calls] == ["duckduckgo", "duckduckgo", "auto"]
    assert all(call[0] == "test query" for call in calls)
    assert [call.args[0] for call in sleep.call_args_list] == [1, 2]
    assert answer == (
        "snippet: official snippet, title: Official, link: https://example.gov/page, "
        "snippet: general snippet, title: General, link: https://example.com/page"
    )


def test_search_retries_after_empty_results(monkeypatch):
    calls = []
    results = [{"title": "Result", "href": "https://example.com/page", "body": "snippet"}]

    class FakeDDGS:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            return False

        def text(self, query, **kwargs):
            calls.append(kwargs["backend"])
            return [] if len(calls) == 1 else results

    monkeypatch.setattr(search_module, "DDGS", FakeDDGS)

    with patch.object(search_module.time, "sleep") as sleep:
        answer = search_module.search_tool.invoke({"query": "empty then results"})

    assert calls == ["duckduckgo", "duckduckgo"]
    sleep.assert_not_called()
    assert answer == "snippet: snippet, title: Result, link: https://example.com/page"


def test_retry_ladder_and_delay_come_from_config(monkeypatch):
    backends = []

    class FailingDDGS:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            return False

        def text(self, query, **kwargs):
            backends.append(kwargs["backend"])
            raise RuntimeError("blocked")

    monkeypatch.setattr(search_module, "DDGS", FailingDDGS)
    monkeypatch.setattr(search_module.config, "SEARCH_PROVIDER", "duckduckgo")
    monkeypatch.setattr(search_module.config, "SEARCH_FALLBACK_ENABLED", False)
    monkeypatch.setattr(search_module.config, "DDG_RETRY_BACKENDS", ("lite", "auto"))
    monkeypatch.setattr(search_module.config, "DDG_RETRY_DELAY_SECONDS", 0.5)

    with patch.object(search_module.time, "sleep") as sleep:
        with pytest.raises(RuntimeError, match="setelah 2 attempts"):
            search_module.search_web("test")

    assert backends == ["duckduckgo", "auto"]
    assert [call.args[0] for call in sleep.call_args_list] == [0.5]
