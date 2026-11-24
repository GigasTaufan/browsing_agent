"""
Tool pencarian web dengan provider pluggable (DuckDuckGo / SearXNG),
ranking dan deduplikasi URL. Counter state per query (bukan global).
"""

import re
import time

import httpx
from ddgs import DDGS
from langchain.tools import tool

import config
from agent.planner import ToolLimitReached, check_and_increment

# --- Search Provider Abstraction ---
# Provider mengembalikan string mentah berformat baris:
#   "snippet: ..., title: ..., link: ..."
# sehingga ranking/dedup dan alur evidence tidak berubah antar provider.

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


def _extract_url(result_line: str) -> str | None:
    """Ekstrak URL dari satu baris hasil pencarian."""
    match = re.search(r"https?://[^\s,;\"\')\]]+", result_line)
    if match:
        return match.group().rstrip(",").rstrip("]").rstrip(";")
    return None


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


def _rank_and_dedup(raw_results: str, max_results: int | None = None) -> str:
    """
    Deduplikasi hasil pencarian berdasarkan URL,
    lalu rank berdasarkan kualitas domain.
    Mengembalikan string hasil ter-filter.
    """
    max_results = max_results or config.MAX_SEARCH_RESULTS

    lines = raw_results.splitlines()

    # Ekstrak URL dari setiap baris: (line, url, score)
    entries: list[tuple[str, str, int]] = []
    for line in lines:
        url = _extract_url(line)
        if url:
            entries.append((line, url, _score_url(url)))

    # Dedup berdasarkan URL (canonical: lowercase, tanpa trailing slash)
    seen = set()
    unique: list[tuple[str, str, int]] = []
    for entry in entries:
        canon = entry[1].rstrip("/").lower()
        if canon not in seen:
            seen.add(canon)
            unique.append(entry)

    # Sort descending by score, lalu batasi jumlah
    ranked = sorted(unique, key=lambda entry: entry[2], reverse=True)[:max_results]

    return "\n".join(entry[0] for entry in ranked) if ranked else ""


def _format_results(raw_results: str) -> str:
    """Rank, dedup, dan log link hasil mentah; kembalikan string ter-format."""
    filtered = _rank_and_dedup(raw_results)
    formatted = ", ".join(filtered.splitlines())

    # Ekstraksi URL untuk log transparansi
    links = re.findall(r"https?://[^\s,;\"\')\]]+", formatted)
    if links:
        print(f"[Search Tool]: Ditemukan {len(links)} sumber relevan (setelah ranking):")
        for i, link in enumerate(links[:3], 1):
            clean_link = link.rstrip(",").rstrip("]").rstrip(";")
            print(f"   {i}. {clean_link}")

    return formatted


def _search_ddgs(query: str) -> str:
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
                return "\n".join(
                    f"snippet: {result['body']}, title: {result['title']}, link: {result['href']}"
                    for result in results
                )

            # Hasil kosong — coba backend berikutnya
            print(f"[Search Tool]: Backend '{backend}' return kosong, coba fallback...")

        except Exception as e:
            last_error = e
            print(f"[Search Tool]: Gagal dengan backend '{backend}' (attempt {attempt}/3): {e}")
            if attempt < len(backends):
                wait = attempt  # 1s, 2s
                time.sleep(wait)
            continue

    raise RuntimeError(f"DuckDuckGo gagal setelah 3 attempts. Error: {last_error}")


def _search_searxng(query: str) -> str:
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

    return "\n".join(
        f"snippet: {result.get('content', '')}, title: {result.get('title', '')}, "
        f"link: {result.get('url', '')}"
        for result in results[: config.MAX_SEARCH_RESULTS]
    )


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

    providers: dict[str, object] = {"duckduckgo": _search_ddgs, "searxng": _search_searxng}
    primary = config.SEARCH_PROVIDER
    if primary not in providers:
        return (
            f"[Search Tool]: SEARCH_PROVIDER tidak dikenal: {primary!r} "
            "(pilihan: duckduckgo, searxng)."
        )

    # SearXNG hanya tersedia jika base URL dikonfigurasi.
    available = dict(providers)
    if not config.SEARXNG_BASE_URL:
        available.pop("searxng")

    order = [primary]
    if config.SEARCH_FALLBACK_ENABLED:
        order += [name for name in available if name != primary]

    last_error: Exception | None = None
    for provider_name in order:
        try:
            raw_results = providers[provider_name](query)  # type: ignore[operator]
            formatted = _format_results(raw_results)
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
