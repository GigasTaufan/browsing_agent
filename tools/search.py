"""
Tool pencarian web dengan provider pluggable (DuckDuckGo / SearXNG),
ranking dan deduplikasi hasil. Counter state per query (bukan global).
"""

import time
from collections.abc import Callable

import httpx
from ddgs import DDGS
from langchain.tools import tool
from pydantic import BaseModel

import config
from agent.planner import ToolLimitReached, check_and_increment


class SearchResult(BaseModel):
    """Satu hasil pencarian: judul, URL, dan cuplikan teks."""

    title: str
    url: str
    snippet: str


_KNOWN_QUALITY_DOMAINS = {
    ".edu",
    ".gov",
    ".ac.id",
    ".go.id",
    ".or.id",
    ".wikipedia.org",
    ".britannica.com",
    ".stackoverflow.com",
}


def _score_url(url: str) -> int:
    """
    Skor kualitas URL (higher = lebih baik).
    Prefer domain kredibel seperti .edu, .gov, Wikipedia.
    """
    domain = url.lower()
    for d in _KNOWN_QUALITY_DOMAINS:
        if d in domain:
            return 10
    if "wikipedia" in domain:
        return 9
    return 1


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


def _format_results(results: list[SearchResult]) -> str:
    """Rank, dedup, log link teratas, dan kembalikan string untuk LLM."""
    ranked = _rank_and_dedup(results, config.MAX_SEARCH_RESULTS)

    if ranked:
        print(f"[Search Tool]: Ditemukan {len(ranked)} sumber relevan (setelah ranking):")
        for i, result in enumerate(ranked[:3], 1):
            print(f"   {i}. {result.url}")

    return ", ".join(
        f"snippet: {result.snippet}, title: {result.title}, link: {result.url}" for result in ranked
    )


def _search_ddgs(query: str) -> list[SearchResult]:
    """Pencarian via DuckDuckGo (ddgs). Retry ladder: lite -> lite -> auto."""
    backends = ["lite", "lite", "auto"]
    last_error: Exception | None = None

    for attempt, backend in enumerate(backends, start=1):
        try:
            ddgs_backend = "duckduckgo" if backend == "lite" else backend
            with DDGS() as ddgs:
                results = ddgs.text(
                    query,
                    backend=ddgs_backend,
                    max_results=config.MAX_SEARCH_RESULTS,
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
            print(f"[Search Tool]: Gagal dengan backend '{backend}' (attempt {attempt}/3): {e}")
            if attempt < len(backends):
                time.sleep(attempt)  # 1s, 2s
            continue

    raise RuntimeError(f"DuckDuckGo gagal setelah 3 attempts. Error: {last_error}")


def _search_searxng(query: str) -> list[SearchResult]:
    """Pencarian via SearXNG JSON API (self-hosted, tanpa API key)."""
    if not config.SEARXNG_BASE_URL:
        raise RuntimeError("SEARXNG_BASE_URL belum dikonfigurasi.")

    url = f"{config.SEARXNG_BASE_URL.rstrip('/')}/search"
    with httpx.Client(timeout=config.REQUEST_TIMEOUT) as client:
        response = client.get(
            url,
            params={"q": query, "format": "json", "safesearch": 1},
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
        for result in results[: config.MAX_SEARCH_RESULTS]
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


_PROVIDERS: dict[str, Callable[[str], list[SearchResult]]] = {
    "duckduckgo": _search_ddgs,
    "searxng": _search_searxng,
}


@tool(
    "search_tool",
    description="Lakukan pencarian web (DuckDuckGo atau SearXNG sesuai konfigurasi) untuk mendapatkan daftar link dan ringkasan.",
)
def search_tool(query: str) -> str:
    """
    Mencari web menggunakan provider terpilih (SEARCH_PROVIDER) dan
    mengembalikan hasil yang sudah di-rank dan di-deduplikasi.
    """
    try:
        check_and_increment("search_tool", config.MAX_TOOL_CALLS)
    except ToolLimitReached as e:
        return str(e)

    print(f"\n[Search Tool]: Searching '{query}'...")

    primary = config.SEARCH_PROVIDER
    if primary not in _PROVIDERS:
        return (
            f"[Search Tool]: SEARCH_PROVIDER tidak dikenal: {primary!r} "
            "(pilihan: duckduckgo, searxng)."
        )

    order = [primary]
    if config.SEARCH_FALLBACK_ENABLED:
        # SearXNG hanya tersedia jika base URL dikonfigurasi.
        order += [
            name
            for name in _PROVIDERS
            if name != primary and (name != "searxng" or config.SEARXNG_BASE_URL)
        ]

    last_error: Exception | None = None
    for provider_name in order:
        try:
            formatted = _format_results(_PROVIDERS[provider_name](query))
            if formatted:
                _record_provider_attributes(provider_name, fallback_used=provider_name != primary)
                print(
                    f"[Search Tool]: Sukses mendapatkan hasil pencarian (provider={provider_name})."
                )
                return formatted
            print(
                f"[Search Tool]: Provider '{provider_name}' tidak menghasilkan link, coba berikutnya..."
            )
        except Exception as e:
            last_error = e
            print(f"[Search Tool]: Provider '{provider_name}' gagal: {e}")

    if last_error is None:
        return "Tidak ada hasil pencarian."
    print(f"[Search Tool]: Gagal melakukan pencarian untuk '{query}'. Detail error: {last_error}")
    return f"[Search Tool]: Tidak dapat melakukan pencarian. Error: {last_error}"
