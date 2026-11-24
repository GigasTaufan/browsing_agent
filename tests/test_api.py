"""Contract tests for the authenticated API without LLM or network access."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from agent.planner import get_run_state
from api import create_app
from storage.evidence import EvidenceItem

API_KEY = "caller-test-key"


class StubAgent:
    def __init__(self):
        self.calls = []
        self.error = None

    def invoke(self, payload):
        self.calls.append(payload)
        if self.error is not None:
            raise self.error

        state = get_run_state()
        assert state is not None
        state.evidence_store.items.append(
            EvidenceItem(
                url="https://example.com/article",
                title="Example article",
                snippet="A short source excerpt.",
                canonical_url="https://example.com/article",
            )
        )
        return {"messages": [SimpleNamespace(type="ai", content="An answer.")]}


@pytest.fixture
def api_client(monkeypatch):
    monkeypatch.setenv("API_ALLOWED_KEYS", API_KEY)
    agent = StubAgent()
    factory_calls = []

    def agent_factory():
        factory_calls.append(True)
        return agent

    with TestClient(
        create_app(agent_factory=agent_factory), raise_server_exceptions=False
    ) as client:
        yield client, agent, factory_calls


def test_valid_question_returns_separate_answer_and_citations(api_client):
    client, agent, _ = api_client

    response = client.post(
        "/api/v1/ask",
        headers={"Authorization": f"Bearer {API_KEY}"},
        json={"question": "What is new?"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "answer": "An answer.",
        "citations": [
            {
                "id": 1,
                "title": "Example article",
                "url": "https://example.com/article",
                "snippet": "A short source excerpt.",
            }
        ],
    }
    assert len(agent.calls) == 1
    assert agent.calls[0]["messages"] == [{"role": "user", "content": "What is new?"}]


@pytest.mark.parametrize(
    "headers",
    [{}, {"Authorization": "Bearer wrong-key"}],
    ids=["missing-key", "invalid-key"],
)
def test_missing_or_invalid_key_rejects_without_running_agent(api_client, headers):
    client, agent, _ = api_client

    response = client.post("/api/v1/ask", headers=headers, json={"question": "Question"})

    assert response.status_code == 401
    assert response.json() == {"error": {"code": "unauthorized", "message": "API key tidak valid."}}
    assert agent.calls == []


@pytest.mark.parametrize("question", ["", " \t\n "])
def test_blank_question_is_422_and_does_not_run_agent(api_client, question):
    client, agent, _ = api_client

    response = client.post(
        "/api/v1/ask",
        headers={"Authorization": f"Bearer {API_KEY}"},
        json={"question": question},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_request"
    assert agent.calls == []


def test_agent_failure_returns_generic_500_envelope(api_client):
    client, agent, _ = api_client
    agent.error = RuntimeError("private backend detail")

    response = client.post(
        "/api/v1/ask",
        headers={"Authorization": f"Bearer {API_KEY}"},
        json={"question": "Question"},
    )

    assert response.status_code == 500
    assert response.json() == {
        "error": {"code": "internal_error", "message": "Terjadi kesalahan internal."}
    }
    assert "private backend detail" not in response.text
    assert len(agent.calls) == 1


def test_health_check_is_public_and_does_not_expose_configuration(api_client):
    client, _, _ = api_client

    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert API_KEY not in response.text


def test_agent_is_created_once_and_fetcher_is_cleaned_at_shutdown(monkeypatch):
    monkeypatch.setenv("API_ALLOWED_KEYS", API_KEY)
    factory = Mock(return_value=StubAgent())
    cleanup = Mock()
    monkeypatch.setattr("api.fetcher_cleanup", cleanup)

    with TestClient(create_app(agent_factory=factory)):
        assert factory.call_count == 1

    assert factory.call_count == 1
    cleanup.assert_called_once_with()
