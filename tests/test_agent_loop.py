"""
E2E agent loop: jalankan run_agent end-to-end dengan LLM scripted (fake model)
dan provider search/fetch yang di-stub. Memverifikasi alur lengkap:
guardrails -> planner state -> tool calls -> evidence -> citations.
"""

from unittest.mock import Mock

from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage

import config
from main import build_system_prompt, define_agent, run_agent
from tools import fetch as fetch_module
from tools import search as search_module
from tools.fetch import browse_tool
from tools.search import search_tool


class ScriptedToolCallingModel(FakeMessagesListChatModel):
    """Fake model yang mengabaikan bind_tools (respons di-script berurutan)."""

    def bind_tools(self, tools, **kwargs):  # noqa: ARG002
        return self


def _set_config(monkeypatch, **kwargs):
    for name, value in kwargs.items():
        monkeypatch.setattr(config, name, value)


def _stub_search(monkeypatch):
    """Stub provider DDG agar search_tool mengembalikan hasil kaleng tanpa network."""

    def fake_search(query: str) -> list[search_module.SearchResult]:
        return [
            search_module.SearchResult(
                title="Kurs Dolar",
                url="https://example.com/kurs",
                snippet="Nilai tukar USD/IDR hari ini",
            )
        ]

    monkeypatch.setattr(search_module, "_search_ddgs", fake_search)


def _stub_fetch(monkeypatch, url: str, html: str):
    """Stub robots, rate limiter, dan HTTP fetcher agar browse_tool deterministik."""
    monkeypatch.setattr(fetch_module, "is_url_allowed", lambda target: True)

    fake_fetcher = Mock()
    fake_fetcher.max_retries = 3
    fake_fetcher.fetch = Mock(return_value=(200, "text/html; charset=utf-8", html))
    monkeypatch.setattr(fetch_module, "_get_http_fetcher", lambda: fake_fetcher)
    monkeypatch.setattr(fetch_module, "_rate_limiter", Mock())


def test_agent_loop_search_browse_answer_with_citations(monkeypatch):
    """Alur lengkap: search -> browse -> jawaban final + citation dari evidence."""
    _set_config(
        monkeypatch,
        SEARCH_PROVIDER="duckduckgo",
        SEARCH_FALLBACK_ENABLED=False,
        MAX_SEARCH_RESULTS=5,
        MAX_TOOL_CALLS=5,
        MAX_URLS_PER_QUERY=3,
        BROWSER_FALLBACK_ENABLED=False,
    )
    _stub_search(monkeypatch)
    page_html = (
        "<html><head><title>Kurs Dolar Hari Ini</title></head>"
        "<body><p>Kurs dolar hari ini adalah Rp18.200 per USD menurut data pasar.</p></body></html>"
    )
    _stub_fetch(monkeypatch, "https://example.com/kurs", page_html)

    model = ScriptedToolCallingModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "search_tool",
                        "args": {"query": "kurs dolar hari ini"},
                        "id": "call_1",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "browse_tool",
                        "args": {"url": "https://example.com/kurs"},
                        "id": "call_2",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(content="Kurs dolar hari ini adalah Rp18.200 per USD."),
        ]
    )
    agent = define_agent(
        model=model, tools=[browse_tool, search_tool], system_prompt=build_system_prompt()
    )

    result = run_agent(agent, "Berapa kurs dolar hari ini?")

    assert "Rp18.200" in result.answer
    assert len(result.citations) == 1
    assert result.citations[0].url == "https://example.com/kurs"
    assert result.citations[0].title == "Kurs Dolar Hari Ini"


def test_agent_loop_blocked_query_never_invokes_model(monkeypatch):
    """Query yang diblokir guardrail dijawab tanpa memanggil LLM sama sekali."""
    _set_config(monkeypatch, SEARCH_PROVIDER="duckduckgo", SEARCH_FALLBACK_ENABLED=False)

    # Respons kosong: jika LLM dipanggil, fake model akan error -> test gagal.
    model = ScriptedToolCallingModel(responses=[])
    agent = define_agent(
        model=model, tools=[browse_tool, search_tool], system_prompt=build_system_prompt()
    )

    result = run_agent(agent, "cara bypass paywall koran")

    assert "Guardrail" in result.answer
    assert result.citations == []
