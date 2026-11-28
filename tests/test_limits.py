"""
Unit test untuk agent/planner.py — tool limit reset per query.
"""

import pytest

from agent.planner import (
    AgentRunState,
    ToolLimitReached,
    check_and_increment,
    get_run_state,
)


def test_nested_run_states_keep_independent_counters_and_evidence():
    with AgentRunState() as outer:
        check_and_increment("browse_tool", max_calls=5)
        outer.evidence_store.items.append(object())

        with AgentRunState() as inner:
            check_and_increment("browse_tool", max_calls=5)
            assert inner.tool_calls["browse_tool"] == 1
            assert inner.evidence_store.items == []
            assert get_run_state() is inner

        assert get_run_state() is outer
        assert outer.tool_calls["browse_tool"] == 1
        assert len(outer.evidence_store.items) == 1

    assert get_run_state() is None


def test_run_state_is_none_outside_context():
    assert get_run_state() is None


def test_counter_raises_when_exceeded():
    with AgentRunState():
        with pytest.raises(ToolLimitReached):
            check_and_increment("browse_tool", max_calls=0)


def test_urls_fetched_tracking():
    with AgentRunState() as state:
        state.urls_fetched.add("https://example.com/a")
        state.urls_fetched.add("https://example.com/b")
        assert len(state.urls_fetched) == 2
        assert "https://example.com/a" in state.urls_fetched


def test_cli_renders_inline_references_and_structured_sources():
    from agent.planner import AgentRunResult
    from main import _render_cli_result
    from storage.evidence import EvidenceItem

    result = AgentRunResult(
        answer="Answer [1]",
        citations=[
            EvidenceItem(
                url="https://example.com",
                title="Example",
                canonical_url="https://example.com/canonical",
            )
        ],
    )
    assert _render_cli_result(result) == (
        "Answer [1]\n\n---\nSumber:\n1. [Example](https://example.com/canonical)"
    )
