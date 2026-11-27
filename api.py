"""Authenticated FastAPI interface for the browsing agent."""

import hmac
import threading
import time
from collections.abc import Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.datastructures import State
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import BaseModel, field_validator
from starlette.concurrency import run_in_threadpool

import config
import oplog
from main import build_system_prompt, define_agent, load_llm, run_agent, setup_tracing
from policy.inbound_rate_limit import (
    RateLimitDecision,
    RateLimiterProtocol,
    build_rate_limiter,
)
from tools.fetch import browse_tool, fetcher_cleanup
from tools.search import search_tool


class AskRequest(BaseModel):
    question: str

    @field_validator("question")
    @classmethod
    def question_must_not_be_blank(cls, question: str) -> str:
        if not question.strip():
            raise ValueError("question wajib diisi.")
        return question


class Citation(BaseModel):
    id: int
    title: str
    url: str
    snippet: str


class AskResponse(BaseModel):
    answer: str
    citations: list[Citation]


def _default_agent_factory():
    model = load_llm()
    return define_agent(
        model=model, tools=[browse_tool, search_tool], system_prompt=build_system_prompt()
    )


def _error(code: str, message: str) -> dict[str, dict[str, str]]:
    return {"error": {"code": code, "message": message}}


def _rejected(
    state: State,
    reason: str,
    status_code: int,
    code: str,
    message: str,
    started: float,
) -> JSONResponse:
    """Tutup request yang ditolak (setelah auth lolos) dan kembalikan envelope error."""
    return _finish(state, reason, started, status_code=status_code, body=_error(code, message))


def _finish(
    state: State,
    outcome: str,
    started: float,
    *,
    status_code: int,
    body: dict,
) -> JSONResponse:
    """Tutup satu request: hitung metrik + event log dengan durasi."""
    duration_seconds = time.monotonic() - started
    counter = state.metrics["browsing_agent_requests_total"]
    counter[outcome] = counter.get(outcome, 0) + 1
    duration = state.metrics["browsing_agent_request_duration_seconds"]
    duration["count"] += 1
    duration["sum"] += duration_seconds
    duration["max"] = max(duration["max"], duration_seconds)
    oplog.log_event(
        "api.request",
        outcome=outcome,
        status=status_code,
        duration_ms=round(duration_seconds * 1000),
    )
    return JSONResponse(status_code=status_code, content=body)


def _render_metrics(metrics: dict) -> str:
    """Format eksposisi Prometheus untuk dua metrik in-process (ADR-0010)."""
    lines = ["# TYPE browsing_agent_requests_total counter"]
    lines += [
        f'browsing_agent_requests_total{{outcome="{outcome}"}} {count}'
        for outcome, count in sorted(metrics["browsing_agent_requests_total"].items())
    ]
    duration = metrics["browsing_agent_request_duration_seconds"]
    lines += [
        "# TYPE browsing_agent_request_duration_seconds summary",
        f"browsing_agent_request_duration_seconds_count {duration['count']}",
        f"browsing_agent_request_duration_seconds_sum {duration['sum']:.6f}",
        f"browsing_agent_request_duration_seconds_max {duration['max']:.6f}",
    ]
    return "\n".join(lines) + "\n"


def _authenticate(authorization: str | None) -> str:
    """Validasi Bearer key; mengembalikan key yang cocok (untuk rate limiting)."""
    scheme = ""
    candidate = ""
    if authorization is not None:
        scheme, separator, credential = authorization.partition(" ")
        if separator and credential and " " not in credential:
            candidate = credential

    candidate_bytes = candidate.encode("utf-8")
    matches = False
    for allowed_key in config.API_ALLOWED_KEYS:
        match = hmac.compare_digest(candidate_bytes, allowed_key.encode("utf-8"))
        matches = matches | match

    if scheme.casefold() != "bearer" or not candidate or not matches:
        raise HTTPException(status_code=401, detail="Unauthorized")

    return candidate


def create_app(
    agent_factory: Callable[[], object] | None = None,
    rate_limiter: RateLimiterProtocol | None = None,
) -> FastAPI:
    """Create the API app; its agent factory runs once for each app lifespan."""
    factory = agent_factory or _default_agent_factory

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        setup_tracing()
        limiter = rate_limiter
        owns_limiter = False
        if limiter is None:
            limiter = build_rate_limiter()
            owns_limiter = limiter is not None
        app.state.rate_limiter = limiter
        app.state.concurrency_semaphore = threading.BoundedSemaphore(
            config.MAX_CONCURRENT_AGENT_RUNS
        )
        app.state.metrics = {
            "browsing_agent_requests_total": {},
            "browsing_agent_request_duration_seconds": {"count": 0, "sum": 0.0, "max": 0.0},
        }
        try:
            app.state.agent = factory()
            yield
        finally:
            if owns_limiter and limiter is not None:
                await limiter.aclose()
            fetcher_cleanup()

    app = FastAPI(lifespan=lifespan)

    @app.exception_handler(HTTPException)
    async def handle_http_error(_request: Request, exc: HTTPException) -> JSONResponse:
        if exc.status_code == 401:
            return JSONResponse(
                status_code=401,
                content=_error("unauthorized", "API key tidak valid."),
            )
        return JSONResponse(
            status_code=exc.status_code,
            content=_error("http_error", "Request tidak dapat diproses."),
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        _request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        question_error = any(
            error.get("loc") == ("body", "question")
            and error.get("type") in {"missing", "value_error"}
            for error in exc.errors()
        )
        message = "question wajib diisi." if question_error else "Request tidak valid."
        return JSONResponse(
            status_code=422,
            content=_error("invalid_request", message),
        )

    @app.exception_handler(Exception)
    async def handle_internal_error(_request: Request, _exc: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=500,
            content=_error("internal_error", "Terjadi kesalahan internal."),
        )

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/metrics", response_class=PlainTextResponse)
    async def metrics() -> str:
        # Counter dibaca/ditulis tanpa await di antara -> konsisten di event loop.
        return _render_metrics(app.state.metrics)

    @app.post("/api/v1/ask", response_model=AskResponse)
    async def ask(
        payload: AskRequest,
        authorization: str | None = Header(default=None),
    ) -> AskResponse | JSONResponse:
        started = time.monotonic()
        state = app.state
        try:
            api_key = _authenticate(authorization)
        except HTTPException as exc:
            return _finish(
                state,
                "unauthorized",
                started,
                status_code=exc.status_code,
                body=_error("unauthorized", "API key tidak valid."),
            )

        if len(payload.question) > config.MAX_QUESTION_LENGTH:
            return _rejected(
                state,
                "overlong",
                422,
                "invalid_request",
                f"Pertanyaan terlalu panjang (maksimal {config.MAX_QUESTION_LENGTH} karakter).",
                started,
            )

        limiter = state.rate_limiter
        if limiter is not None:
            decision = await limiter.check(api_key)
            if decision is RateLimitDecision.UNAVAILABLE:
                # Fail-closed (ADR-0006): tanpa limiter, quota caller tidak dapat dijamin.
                return _rejected(
                    state,
                    "dependency_unavailable",
                    503,
                    "dependency_unavailable",
                    "Layanan pembatas request sedang tidak tersedia. Coba lagi nanti.",
                    started,
                )
            if decision is RateLimitDecision.LIMITED:
                return _rejected(
                    state,
                    "rate_limited",
                    429,
                    "rate_limited",
                    "Terlalu banyak request. Coba lagi dalam satu menit.",
                    started,
                )

        semaphore = state.concurrency_semaphore
        if not semaphore.acquire(blocking=False):
            return _rejected(
                state,
                "server_busy",
                429,
                "server_busy",
                "Server sedang sibuk. Coba lagi nanti.",
                started,
            )
        try:
            result = await run_in_threadpool(run_agent, state.agent, payload.question)
        except Exception:
            # Handler 500 global tidak tahu outcome; catat agar error agent terlihat di metrik.
            _finish(state, "error", started, status_code=500, body={})
            raise
        finally:
            semaphore.release()
        citations = [
            Citation(
                id=index,
                title=item.title or item.url,
                url=item.canonical_url or item.url,
                snippet=item.snippet,
            )
            for index, item in enumerate(result.citations, start=1)
        ]
        outcome = "ok" if citations else "ok_no_citations"
        body = AskResponse(answer=result.answer, citations=citations).model_dump()
        return _finish(state, outcome, started, status_code=200, body=body)

    return app
