"""Authenticated FastAPI interface for the browsing agent."""

import hmac
import os
import threading
from collections.abc import Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, field_validator
from starlette.concurrency import run_in_threadpool

import config
from main import build_system_prompt, define_agent, load_llm, run_agent, setup_tracing
from policy.inbound_rate_limit import RateLimiterProtocol, build_rate_limiter
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


def _authenticate(authorization: str | None) -> str:
    """Validasi Bearer key; mengembalikan key yang cocok (untuk rate limiting)."""
    scheme = ""
    candidate = ""
    if authorization is not None:
        scheme, separator, credential = authorization.partition(" ")
        if separator and credential and " " not in credential:
            candidate = credential

    candidate_bytes = candidate.encode("utf-8")
    allowed_keys = (
        value.strip()
        for value in os.environ.get("API_ALLOWED_KEYS", "").split(",")
        if value.strip()
    )
    matches = False
    for allowed_key in allowed_keys:
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

    @app.post("/api/v1/ask", response_model=AskResponse)
    async def ask(
        payload: AskRequest,
        authorization: str | None = Header(default=None),
    ) -> AskResponse | JSONResponse:
        api_key = _authenticate(authorization)

        if len(payload.question) > config.MAX_QUESTION_LENGTH:
            return JSONResponse(
                status_code=422,
                content=_error(
                    "invalid_request",
                    f"Pertanyaan terlalu panjang (maksimal {config.MAX_QUESTION_LENGTH} karakter).",
                ),
            )

        limiter = app.state.rate_limiter
        if limiter is not None and not await limiter.check(api_key):
            return JSONResponse(
                status_code=429,
                content=_error(
                    "rate_limited", "Terlalu banyak request. Coba lagi dalam satu menit."
                ),
            )

        semaphore = app.state.concurrency_semaphore
        if not semaphore.acquire(blocking=False):
            return JSONResponse(
                status_code=429,
                content=_error("server_busy", "Server sedang sibuk. Coba lagi nanti."),
            )
        try:
            result = await run_in_threadpool(run_agent, app.state.agent, payload.question)
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
        return AskResponse(answer=result.answer, citations=citations)

    return app
