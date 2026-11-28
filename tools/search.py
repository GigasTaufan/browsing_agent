"""
Tool pencarian web dengan provider pluggable (DuckDuckGo / SearXNG),
ranking dan deduplikasi hasil. Counter state per query (bukan global).
"""

import time
from collections.abc import Callable

import httpx
from ddgs import DDGS
from pydantic import BaseModel

import config
from agent.planner import check_and_increment


class SearchResult(BaseModel):
    """Satu hasil pencarian: judul, URL, dan cuplikan teks."""

    title: str
    url: str
    snippet: str


def _score_url(url: str) -> int:
    """
    Skor kualitas URL (higher = lebih baik).
    Prefer domain kredibel sesuai SEARCH_TRUSTED_DOMAINS.
    """
    domain = url.lower()
    for trusted in config.SEARCH_TRUSTED_DOMAINS:
        if trusted in domain:
            return config.SEARCH_TRUSTED_SCORE
    return config.SEARCH_DEFAULT_SCORE


def _rank_and_dedup(results: list[SearchResult], max_results: int) -> list[SearchResult]:
    """Deduplikasi berdasarkan URL (lowercase, tanpa trailing slash) lalu rank domain kualitas."""
    seen: set[str] = set()
    unique: list[SearchResult] = []
    for result in results:
        canonical = result.url.rstrip("/").lower()
        if canonical not in seen:
            seen.add(canonical)
            unique.append(result)

    ranked = sorted(unique, key=lambda result: _score_url(result.url), reverse=True)
    return ranked[:max_results]


def _search_ddgs(query: str) -> list[SearchResult]:
    """Pencarian via DuckDuckGo (ddgs). Retry ladder dari DDG_RETRY_BACKENDS."""
    backends = config.DDG_RETRY_BACKENDS
    last_error: Exception | None = None

    for attempt, backend in enumerate(backends, start=1):
        try:
            ddgs_backend = "duckduckgo" if backend == "lite" else backend
            with DDGS() as ddgs:
                results = ddgs.text(
                    query,
                    backend=ddgs_backend,
                    max_results=config.SEARCH_CANDIDATE_LIMIT,
                )

            if results:
                return [
                    SearchResult(title=result["title"], url=result["href"], snippet=result["body"])
                    for result in results
                ]

            # Hasil kosong — coba backend berikutnya
            print(f"[Search Tool]: Backend '{backend}' return kosong, coba fallback...")

        except Exception as e:
            last_error = e
            print(
                f"[Search Tool]: Gagal dengan backend '{backend}' "
                f"(attempt {attempt}/{len(backends)}): {e}"
            )
            if attempt < len(backends):
                time.sleep(attempt * config.DDG_RETRY_DELAY_SECONDS)
            continue

    raise RuntimeError(f"DuckDuckGo gagal setelah {len(backends)} attempts. Error: {last_error}")


def _search_searxng(query: str) -> list[SearchResult]:
    """Pencarian via SearXNG JSON API (self-hosted, tanpa API key)."""
    if not config.SEARXNG_BASE_URL:
        raise RuntimeError("SEARXNG_BASE_URL belum dikonfigurasi.")

    url = f"{config.SEARXNG_BASE_URL.rstrip('/')}/search"
    with httpx.Client(timeout=config.REQUEST_TIMEOUT) as client:
        response = client.get(
            url,
            params={"q": query, "format": "json", "safesearch": config.SEARXNG_SAFESEARCH},
        )
        response.raise_for_status()
        payload = response.json()

    results = payload.get("results", [])
    if not results:
        raise RuntimeError("SearXNG mengembalikan hasil kosong.")

    return [
        SearchResult(
            title=result.get("title", ""),
            url=result.get("url", ""),
            snippet=result.get("content", ""),
        )
        for result in results[: config.SEARCH_CANDIDATE_LIMIT]
    ]


def _record_provider_attributes(provider_name: str, fallback_used: bool) -> None:
    """
    Catat provider pencarian sebagai atribut span MLflow aktif (best-effort).
    No-op jika MLflow tidak tersedia, tracing nonaktif, atau tidak ada span aktif.
    """
    try:
        import mlflow

        span = mlflow.get_current_active_span()
        if span is not None:
            span.set_attributes(
                {
                    "search.provider": provider_name,
                    "search.fallback_used": fallback_used,
                }
            )
    except Exception:
        pass


def search_web(query: str) -> list[SearchResult]:
    """Pencarian bertipe dengan provider/fallback dan kuota search_tool."""
    check_and_increment("search_tool", config.MAX_TOOL_CALLS)
    print(f"\n[Search Tool]: Searching '{query}'...")
    providers: dict[str, Callable[[str], list[SearchResult]]] = {
        "duckduckgo": _search_ddgs,
        "searxng": _search_searxng,
    }
    primary = config.SEARCH_PROVIDER
    if primary not in providers:
        raise RuntimeError(
            f"[Search Tool]: SEARCH_PROVIDER tidak dikenal: {primary!r} "
            "(pilihan: duckduckgo, searxng)."
        )
    order = [primary]
    if config.SEARCH_FALLBACK_ENABLED:
        order += [
            name
            for name in providers
            if name != primary and (name != "searxng" or config.SEARXNG_BASE_URL)
        ]
    last_error: Exception | None = None
    for provider_name in order:
        try:
            results = _rank_and_dedup(
                providers[provider_name](query), config.SEARCH_CANDIDATE_LIMIT
            )
            if results:
                _record_provider_attributes(provider_name, fallback_used=provider_name != primary)
                return results
        except Exception as exc:
            last_error = exc
            print(f"[Search Tool]: Provider '{provider_name}' gagal: {exc}")
    if last_error is not None:
        raise RuntimeError(
            f"[Search Tool]: Tidak dapat melakukan pencarian. Error: {last_error}"
        ) from last_error
    return []
