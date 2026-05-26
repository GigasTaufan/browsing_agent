"""
Unit test untuk agent/planner.py — tool limit reset per query.
"""

import pytest
from agent.planner import (
    reset_run_state, get_run_state, check_and_increment, ToolLimitReached,
)


def test_counter_starts_at_zero():
    """Counter baru harus mulai dari nol."""
    state = reset_run_state()
    assert state.tool_calls["browse_tool"] == 0
    assert state.tool_calls["search_tool"] == 0


def test_counter_increments():
    """Counter bertambah setelah check_and_increment."""
    reset_run_state()
    check_and_increment("browse_tool", max_calls=5)

    state = get_run_state()
    assert state.tool_calls["browse_tool"] == 1


def test_counter_raises_when_exceeded():
    """Raise ToolLimitReached saat melebihi batas."""
    reset_run_state()
    with pytest.raises(ToolLimitReached):
        check_and_increment("browse_tool", max_calls=0)


def test_counter_resets_between_queries():
    """Counter reset antara query — simulasi 2 query berbeda."""
    # Query 1: increment 2x
    reset_run_state()
    check_and_increment("browse_tool", max_calls=5)
    check_and_increment("browse_tool", max_calls=5)
    state1 = get_run_state()
    assert state1.tool_calls["browse_tool"] == 2

    # Query 2: reset, harus kembali ke 0 lalu bisa increment lagi
    reset_run_state()
    check_and_increment("browse_tool", max_calls=5)
    state2 = get_run_state()
    assert state2.tool_calls["browse_tool"] == 1


def test_urls_fetched_tracking():
    """Set URLs fetched melacak URL per query."""
    state = reset_run_state()
    state.urls_fetched.add("https://example.com/a")
    state.urls_fetched.add("https://example.com/b")

    assert len(state.urls_fetched) == 2
    assert "https://example.com/a" in state.urls_fetched
