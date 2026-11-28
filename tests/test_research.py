"""Riset adaptif dengan LLM scripted dan batas jaringan di-stub."""

import json
from unittest.mock import Mock

import pytest
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage

import config
from main import build_system_prompt, define_agent, run_agent
from tools import fetch as fetch_module
from tools import search as search_module


def decision(value: dict) -> AIMessage:
    return AIMessage(content=json.dumps(value))


def agent_with(*responses):
    return define_agent(
        model=FakeMessagesListChatModel(responses=list(responses)),
        system_prompt=build_system_prompt(),
    )


@pytest.fixture
def web(monkeypatch):
    monkeypatch.setattr(config, "SEARCH_PROVIDER", "duckduckgo")
    monkeypatch.setattr(config, "SEARCH_FALLBACK_ENABLED", False)
    monkeypatch.setattr(config, "BROWSER_FALLBACK_ENABLED", False)
    monkeypatch.setattr(config, "MAX_URLS_PER_QUERY", 3)
    monkeypatch.setattr(config, "MAX_TOOL_CALLS", 5)
    monkeypatch.setattr(fetch_module, "is_url_blocked", lambda url: (False, ""))
    monkeypatch.setattr(fetch_module, "is_url_allowed", lambda url: True)
    monkeypatch.setattr(fetch_module, "_rate_limiter", Mock())
    fetcher = Mock(max_retries=1)
    fetcher.fetch.side_effect = lambda url: (
        200,
        "text/html",
        f"<title>{url}</title><body>SIP Trunk tersedia di Indonesia. Sumber: {url}.</body>",
    )
    monkeypatch.setattr(fetch_module, "_get_http_fetcher", lambda: fetcher)
    return fetcher


def test_reformulates_and_follows_up_until_competitor_evidence(web, monkeypatch):
    queries = []

    def search(query):
        queries.append(query)
        if query == "SIP trunk Telkom":
            return [
                search_module.SearchResult(
                    title="Produk Telkom", url="https://telkom.example/product", snippet="SIP trunk"
                )
            ]
        return [
            search_module.SearchResult(
                title="Tidak relevan", url=f"https://irrelevant{i}.gov/", snippet="Laporan tahunan"
            )
            for i in range(6)
        ] + [
            search_module.SearchResult(
                title="Penyedia alternatif",
                url="https://vendor.example/sip",
                snippet="SIP trunk Indonesia",
            )
        ]

    monkeypatch.setattr(search_module, "_search_ddgs", search)
    agent = agent_with(
        decision(
            {
                "goal": "Alternatif SIP Trunk",
                "constraints": "Indonesia",
                "queries": ["SIP trunk Telkom"],
            }
        ),
        decision({"candidate_ids": [1]}),
        decision(
            {
                "relevant_ids": [],
                "sufficient": False,
                "missing_information": "Belum ada alternatif",
                "next_queries": ["penyedia SIP trunk Indonesia"],
            }
        ),
        decision({"candidate_ids": [7]}),
        decision(
            {"relevant_ids": [1], "sufficient": True, "missing_information": "", "next_queries": []}
        ),
        AIMessage(content="Penyedia alternatif menawarkan SIP Trunk di Indonesia. [1]"),
    )
    result = run_agent(agent, "Kompetitor product yang mirip SIP Trunk Telkom siapa saja?")
    assert queries == ["SIP trunk Telkom", "penyedia SIP trunk Indonesia"]
    assert [item.url for item in result.citations] == ["https://vendor.example/sip"]
    assert "[1]" in result.answer
    assert web.fetch.call_count == 2


def test_irrelevant_candidates_do_not_consume_fetch_quota(web, monkeypatch):
    search = Mock(
        return_value=[
            search_module.SearchResult(
                title="FAQ IP", url="https://unrelated.example/faq", snippet="Alamat IP"
            )
        ]
    )
    monkeypatch.setattr(search_module, "_search_ddgs", search)
    agent = agent_with(
        decision({"goal": "SIP trunk", "constraints": "Indonesia", "queries": ["SIP trunk"]}),
        decision({"candidate_ids": []}),
        decision(
            {
                "relevant_ids": [],
                "sufficient": False,
                "missing_information": "Tidak relevan",
                "next_queries": ["SIP trunk", " SIP TRUNK "],
            }
        ),
    )
    result = run_agent(agent, "SIP trunk Indonesia?")
    assert result.citations == []
    assert "tanpa bukti" in result.answer
    web.fetch.assert_not_called()
    search.assert_called_once()


def test_invalid_decision_ids_cannot_invent_sources(web, monkeypatch):
    monkeypatch.setattr(
        search_module,
        "_search_ddgs",
        lambda query: [
            search_module.SearchResult(title="Produk", url="https://vendor.example/", snippet="SIP")
        ],
    )
    agent = agent_with(
        decision({"goal": "SIP", "constraints": "", "queries": ["SIP trunk"]}),
        decision({"candidate_ids": [99]}),
    )
    result = run_agent(agent, "SIP trunk?")
    assert result.citations == []
    assert "keputusan yang valid" in result.answer
    web.fetch.assert_not_called()


def test_follow_up_search_stops_at_existing_budget(web, monkeypatch):
    monkeypatch.setattr(config, "MAX_TOOL_CALLS", 1)
    search = Mock(return_value=[])
    monkeypatch.setattr(search_module, "_search_ddgs", search)
    agent = agent_with(
        decision({"goal": "SIP", "constraints": "", "queries": ["SIP trunk"]}),
        decision(
            {
                "relevant_ids": [],
                "sufficient": False,
                "missing_information": "Kosong",
                "next_queries": ["provider SIP alternatif"],
            }
        ),
    )
    result = run_agent(agent, "SIP trunk?")
    assert result.citations == []
    search.assert_called_once()
    web.fetch.assert_not_called()
