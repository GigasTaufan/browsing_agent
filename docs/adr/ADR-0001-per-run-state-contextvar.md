# ADR-0001: State per-run berbasis ContextVar

**Status:** Accepted

## Context

Agen menjalankan banyak query secara konkuren (API FastAPI + threadpool). Tool limits
(`MAX_TOOL_CALLS`, `MAX_URLS_PER_QUERY`), evidence store, dan blocked domains harus
terisolasi per query. Counter global akan bocor antar request dan tidak bisa di-reset
dengan aman.

## Decision

State per-run disimpan dalam `ContextVar` (`agent/planner.py`), di-set via context
manager `AgentRunState()` yang dibuka per pemanggilan `run_agent`. Semua tool
membaca state dari ContextVar, bukan dari variabel modul. Tidak ada global counter.

## Consequences

- Query konkuren sepenuhnya terisolasi; unit test `test_limits.py` memverifikasi reset per query.
- Tool yang dijalankan di thread lain tetap melihat state yang sama (ContextVar ter-propagasi).
- Kode yang tidak berjalan dalam `AgentRunState` mendapat error eksplisit, bukan state basi.