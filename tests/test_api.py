"""Contract tests for the authenticated API without LLM or network access."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

import config
from agent.planner import get_run_state
from api import create_app
from policy.inbound_rate_limit import RateLimitDecision
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


class StubLimiter:
    """Rate limiter stub: mencatat key dan mengembalikan keputusan tetap."""

    def __init__(self, decision: RateLimitDecision):
        self.decision = decision
        self.keys: list[str] = []

    async def check(self, api_key: str) -> RateLimitDecision:
        self.keys.append(api_key)
        return self.decision


@pytest.fixture
def api_client(monkeypatch):
    monkeypatch.setattr(config, "API_ALLOWED_KEYS", (API_KEY,))
    # Hermetic: jangan bangun Redis limiter dari .env lokal di unit test.
    monkeypatch.setattr(config, "RATE_LIMIT_REDIS_URL", None)
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
    assert 'browsing_agent_requests_total{outcome="error"} 1' in client.get("/metrics").text


def test_health_check_is_public_and_does_not_expose_configuration(api_client):
    client, _, _ = api_client

    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert API_KEY not in response.text


def test_agent_is_created_once_and_fetcher_is_cleaned_at_shutdown(monkeypatch):
    # Satu-satunya test yang tidak patch validator startup: lifespan (dan AGENTS.md
    # quality gate) boleh jalan dengan kredensial nyata .env/CI.
    monkeypatch.setattr(config, "RATE_LIMIT_REDIS_URL", None)
    factory = Mock(return_value=StubAgent())
    cleanup = Mock()
    monkeypatch.setattr("api.fetcher_cleanup", cleanup)

    with TestClient(create_app(agent_factory=factory)):
        assert factory.call_count == 1

    assert factory.call_count == 1
    cleanup.assert_called_once_with()


def test_overlong_question_is_rejected(api_client, monkeypatch):
    client, agent, _ = api_client
    monkeypatch.setattr(config, "MAX_QUESTION_LENGTH", 10)

    response = client.post(
        "/api/v1/ask",
        headers={"Authorization": f"Bearer {API_KEY}"},
        json={"question": "x" * 11},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_request"
    assert "terlalu panjang" in response.json()["error"]["message"]
    assert agent.calls == []


def test_rate_limit_exceeded_returns_429(monkeypatch):
    monkeypatch.setattr(config, "API_ALLOWED_KEYS", (API_KEY,))
    monkeypatch.setattr(config, "RATE_LIMIT_REDIS_URL", None)
    limiter = StubLimiter(RateLimitDecision.LIMITED)

    with TestClient(create_app(agent_factory=lambda: StubAgent(), rate_limiter=limiter)) as client:
        response = client.post(
            "/api/v1/ask",
            headers={"Authorization": f"Bearer {API_KEY}"},
            json={"question": "Question"},
        )

    assert response.status_code == 429
    assert response.json() == {
        "error": {
            "code": "rate_limited",
            "message": "Terlalu banyak request. Coba lagi dalam satu menit.",
        }
    }
    assert limiter.keys == [API_KEY]
    assert 'browsing_agent_requests_total{outcome="rate_limited"} 1' in client.get("/metrics").text


def test_redis_unavailable_returns_503_and_does_not_run_agent(monkeypatch):
    """ADR-0006: limiter tidak terjangkau -> fail-closed 503, bukan diizinkan."""
    monkeypatch.setattr(config, "API_ALLOWED_KEYS", (API_KEY,))
    monkeypatch.setattr(config, "RATE_LIMIT_REDIS_URL", None)
    limiter = StubLimiter(RateLimitDecision.UNAVAILABLE)
    agent = StubAgent()

    with TestClient(create_app(agent_factory=lambda: agent, rate_limiter=limiter)) as client:
        response = client.post(
            "/api/v1/ask",
            headers={"Authorization": f"Bearer {API_KEY}"},
            json={"question": "Question"},
        )

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "dependency_unavailable"
    assert agent.calls == []


def test_concurrency_cap_returns_429_when_exhausted(monkeypatch):
    monkeypatch.setattr(config, "API_ALLOWED_KEYS", (API_KEY,))
    monkeypatch.setattr(config, "RATE_LIMIT_REDIS_URL", None)
    monkeypatch.setattr(config, "MAX_CONCURRENT_AGENT_RUNS", 1)

    with TestClient(create_app(agent_factory=lambda: StubAgent())) as client:
        semaphore = client.app.state.concurrency_semaphore
        assert semaphore.acquire(blocking=False)

        busy = client.post(
            "/api/v1/ask",
            headers={"Authorization": f"Bearer {API_KEY}"},
            json={"question": "Question"},
        )
        semaphore.release()

        ok = client.post(
            "/api/v1/ask",
            headers={"Authorization": f"Bearer {API_KEY}"},
            json={"question": "Question"},
        )

    assert busy.status_code == 429
    assert busy.json()["error"]["code"] == "server_busy"
    assert ok.status_code == 200


def test_metrics_expose_outcome_counters_and_latency(api_client):
    """ADR-0010: /metrics bisa di-scrape tanpa auth dan mencerminkan outcome request."""
    client, agent, _ = api_client
    client.post(
        "/api/v1/ask",
        headers={"Authorization": f"Bearer {API_KEY}"},
        json={"question": "What is new?"},
    )
    client.post(
        "/api/v1/ask", headers={"Authorization": "Bearer wrong-key"}, json={"question": "x"}
    )

    response = client.get("/metrics")

    assert response.status_code == 200
    assert 'browsing_agent_requests_total{outcome="ok"} 1' in response.text
    assert 'browsing_agent_requests_total{outcome="unauthorized"} 1' in response.text
    assert "browsing_agent_request_duration_seconds_count 2" in response.text
    assert len(agent.calls) == 1


def test_ask_logs_single_request_event(api_client, monkeypatch):
    """Satu event final per request (durasi/status) menggantikan pasangan ask_ok/ask_rejected."""
    client, _, _ = api_client
    events = []
    monkeypatch.setattr(
        "api.oplog.log_event", lambda event, **fields: events.append((event, fields))
    )

    client.post(
        "/api/v1/ask",
        headers={"Authorization": f"Bearer {API_KEY}"},
        json={"question": "What is new?"},
    )

    assert [event for event, _ in events] == ["api.request"]
    assert events[0][1]["outcome"] == "ok"
    assert events[0][1]["status"] == 200
    assert "duration_ms" in events[0][1]
