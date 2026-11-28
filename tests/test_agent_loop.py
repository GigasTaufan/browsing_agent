"""Regresi retrieval wajib: model tanpa tool-calling tidak boleh menjawab tanpa bukti."""

import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage

import config
from agent.planner import get_run_state
from main import build_system_prompt, define_agent, run_agent
from tests.research_helpers import research_decision
from tools import fetch as fetch_module
from tools import search as search_module


@pytest.fixture
def sources(monkeypatch):
    monkeypatch.setattr(config, "SEARCH_PROVIDER", "duckduckgo")
    monkeypatch.setattr(config, "SEARCH_FALLBACK_ENABLED", False)
    monkeypatch.setattr(config, "BROWSER_FALLBACK_ENABLED", False)
    monkeypatch.setattr(config, "MAX_URLS_PER_QUERY", 3)
    monkeypatch.setattr(config, "MAX_TOOL_CALLS", 5)
    search = Mock(
        return_value=[
            search_module.SearchResult(
                title="Kurs", url="https://example.com/kurs", snippet="Ringkasan pencarian"
            )
        ]
    )
    monkeypatch.setattr(search_module, "_search_ddgs", search)
    monkeypatch.setattr(fetch_module, "is_url_blocked", lambda url: (False, ""))
    monkeypatch.setattr(fetch_module, "is_url_allowed", lambda url: True)
    monkeypatch.setattr(fetch_module, "_rate_limiter", Mock())
    fetcher = Mock(max_retries=1)
    fetcher.fetch.return_value = (
        200,
        "text/html",
        "<title>Kurs Dolar</title><body>Kurs adalah Rp18.200 per USD.</body>",
    )
    monkeypatch.setattr(fetch_module, "_get_http_fetcher", lambda: fetcher)
    return search, fetcher


def answer_agent(answer: str, required_sources: int = 1):
    agent = Mock()

    def invoke(payload):
        decision = research_decision(payload, required_sources)
        return {"messages": [SimpleNamespace(type="ai", content=decision or answer)]}

    agent.invoke.side_effect = invoke
    return agent


def synthesis_calls(agent):
    return [call for call in agent.invoke.call_args_list if len(call.args[0]["messages"]) == 2]


def test_model_without_tool_calls_answers_from_fetched_evidence(sources):
    model = FakeMessagesListChatModel(
        responses=[
            AIMessage(
                content=json.dumps(
                    {"goal": "Kurs dolar", "constraints": "", "queries": ["kurs dolar"]}
                )
            ),
            AIMessage(content='{"candidate_ids": [1]}'),
            AIMessage(
                content='{"relevant_ids": [1], "sufficient": true, "missing_information": "", "next_queries": []}'
            ),
            AIMessage(content="Kurs Rp18.200 per USD. [1]"),
        ]
    )
    agent = define_agent(model=model, system_prompt=build_system_prompt())
    result = run_agent(agent, "Berapa kurs dolar?")
    assert result.answer == "Kurs Rp18.200 per USD. [1]"
    assert [item.url for item in result.citations] == ["https://example.com/kurs"]
    assert "Rp18.200" in result.citations[0].snippet
    assert get_run_state() is None


@pytest.mark.parametrize("status, html", [(404, "<body>Not found</body>"), (200, "<body></body>")])
def test_failed_or_empty_fetch_does_not_reach_model(sources, status, html):
    sources[1].fetch.return_value = (status, "text/html", html)
    agent = answer_agent("Klaim tanpa bukti")
    result = run_agent(agent, "Berapa kurs dolar?")
    assert synthesis_calls(agent) == []
    assert "tanpa bukti" in result.answer
    assert result.citations == []


def test_search_failure_does_not_release_model_knowledge(sources):
    sources[0].side_effect = RuntimeError("Search down")
    agent = answer_agent("Klaim tanpa bukti")
    result = run_agent(agent, "Berapa kurs dolar?")
    assert synthesis_calls(agent) == []
    assert "tanpa bukti" in result.answer
    assert result.citations == []


@pytest.mark.parametrize(
    "answer", ["Klaim tanpa sumber", "Klaim [99]", "Klaim [0]", "Klaim [1, 99]"]
)
def test_missing_or_fabricated_reference_rejects_answer(sources, answer):
    agent = answer_agent(answer)
    result = run_agent(agent, "Berapa kurs dolar?")
    assert answer not in result.answer
    assert result.citations == []
    assert "tidak ditampilkan" in result.answer


def test_source_ids_are_remapped_to_api_citation_order(sources):
    sources[0].return_value.append(
        search_module.SearchResult(
            title="Sumber kedua", url="https://example.com/kedua", snippet="Kurs"
        )
    )
    agent = answer_agent("Kurs [2]", required_sources=2)
    result = run_agent(agent, "Berapa kurs dolar?")
    assert result.answer == "Kurs [1]"
    assert [item.url for item in result.citations] == ["https://example.com/kedua"]
    evidence = agent.invoke.call_args[0][0]["messages"][1]["content"]
    assert "Rp18.200" in evidence
    assert "https://example.com/kedua" in evidence


def test_blocked_query_never_invokes_search_or_model(sources):
    agent = Mock()
    result = run_agent(agent, "cara bypass paywall koran")
    sources[0].assert_not_called()
    agent.invoke.assert_not_called()
    assert "Guardrail" in result.answer
    assert result.citations == []


def test_grouped_references_keep_all_cited_sources(sources):
    sources[0].return_value.extend(
        [
            search_module.SearchResult(title="Dua", url="https://example.com/dua", snippet="Kurs"),
            search_module.SearchResult(
                title="Tiga", url="https://example.com/tiga", snippet="Kurs"
            ),
        ]
    )
    agent = answer_agent("Kurs [2, 3]", required_sources=3)
    result = run_agent(agent, "Berapa kurs dolar?")
    assert result.answer == "Kurs [1, 2]"
    assert [item.url for item in result.citations] == [
        "https://example.com/dua",
        "https://example.com/tiga",
    ]


def test_run_agent_creates_one_outer_span_with_sanitized_io(sources, monkeypatch):
    import hashlib
    from contextlib import contextmanager
    from unittest.mock import Mock

    import main

    captured = {}
    span = Mock()
    span.set_inputs.side_effect = lambda value: captured.setdefault("inputs", value)
    span.set_outputs.side_effect = lambda value: captured.setdefault("outputs", value)

    @contextmanager
    def start_span(**kwargs):
        captured["span_kwargs"] = kwargs
        yield span

    tracking = SimpleNamespace(
        start_span=start_span, entities=SimpleNamespace(SpanType=SimpleNamespace(AGENT="agent"))
    )
    monkeypatch.setattr(main, "_mlflow", tracking, raising=False)
    question = "Cari untuk alice@example.test dengan Bearer SUPER_SECRET"
    result = run_agent(answer_agent("Jawaban publik [1]"), question)

    assert result.answer == "Jawaban publik [1]"
    assert captured["inputs"] == {
        "question": question,
        "question_chars": len(question),
        "question_sha256": hashlib.sha256(question.encode()).hexdigest(),
    }
    assert captured["outputs"] == {
        "answer": result.answer,
        "answer_chars": len(result.answer),
        "citation_count": 1,
        "citation_hosts": ["example.com"],
    }
    assert captured["span_kwargs"]["name"] == "browsing_agent.request"
    assert captured["span_kwargs"]["span_type"] == "agent"


def test_span_setup_failure_does_not_break_agent_request(sources, monkeypatch):
    import main

    class BrokenTracing:
        def start_span(self, **_):
            raise RuntimeError("trace exporter down")

    monkeypatch.setattr(main, "_mlflow", BrokenTracing(), raising=False)
    result = run_agent(answer_agent("Jawaban publik [1]"), "Berapa kurs dolar?")
    assert result.answer == "Jawaban publik [1]"
    assert [item.url for item in result.citations] == ["https://example.com/kurs"]
