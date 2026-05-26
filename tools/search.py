"""
Tool pencarian web menggunakan DuckDuckGo dengan ranking dan deduplikasi URL.
Counter state per query (bukan global).
Pluggable: arsitektur sudah siap untuk menambah provider lain.
"""

import re
import time
from langchain.tools import tool
from langchain_community.tools import DuckDuckGoSearchResults
from langchain_community.utilities.duckduckgo_search import DuckDuckGoSearchAPIWrapper

import config
from agent.planner import check_and_increment, ToolLimitReached


# --- Search Provider Abstraction ---
# Siap untuk ditambah Google Custom Search, Brave Search, dll.

_KNOWN_QUALITY_DOMAINS = {
    ".edu", ".gov", ".ac.id", ".go.id", ".or.id",
    ".wikipedia.org", ".britannica.com", ".stackoverflow.com",
}


def _extract_url(result_line: str) -> str | None:
    """Ekstrak URL dari satu baris hasil pencarian."""
    match = re.search(r'https?://[^\s,;"\')\]]+', result_line)
    if match:
        return match.group().rstrip(',').rstrip(']').rstrip(';')
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


def _rank_and_dedup(raw_results: str, max_results: int = None) -> str:
    """
    Deduplikasi hasil pencarian berdasarkan URL,
    lalu rank berdasarkan kualitas domain.
    Mengembalikan string hasil ter-filter.
    """
    max_results = max_results or config.MAX_SEARCH_RESULTS

    lines = raw_results.splitlines()

    # Ekstrak URL dari setiap baris
    entries = []
    for line in lines:
        url = _extract_url(line)
        if url:
            entries.append({"line": line, "url": url, "score": _score_url(url)})

    # Dedup berdasarkan URL (canonical: lowercase, tanpa trailing slash)
    seen = set()
    unique = []
    for entry in entries:
        canon = entry["url"].rstrip('/').lower()
        if canon not in seen:
            seen.add(canon)
            unique.append(entry)

    # Sort descending by score, lalu batasi jumlah
    ranked = sorted(unique, key=lambda x: x["score"], reverse=True)[:max_results]

    return "\n".join(e["line"] for e in ranked) if ranked else ""


@tool("search_tool", description="Lakukan pencarian web menggunakan DuckDuckGo untuk mendapatkan daftar link dan ringkasan.")
def search_tool(query: str) -> str:
    """
    Mencari web menggunakan DuckDuckGo dan mengembalikan hasil yang sudah
    di-rank dan di-deduplikasi.
    """
    try:
        check_and_increment("search_tool", config.MAX_TOOL_CALLS)
    except ToolLimitReached as e:
        return str(e)

    print(f"\n[Search Tool]: Searching '{query}'...")

    # Retry strategy: lite (lebih stabil) dulu, lalu auto jika gagal.
    # Maksimal 3 attempts dengan exponential backoff.
    backends = ["lite", "lite", "auto"]
    last_error = None

    for attempt, backend in enumerate(backends, start=1):
        try:
            api_wrapper = DuckDuckGoSearchAPIWrapper(backend=backend)
            searcher = DuckDuckGoSearchResults(api_wrapper=api_wrapper)
            raw_results = searcher.run(query)

            # Abaikan placeholder "no result"
            if raw_results and raw_results != "No good DuckDuckGo Search Result was found":
                # Rank dan dedup hasil
                filtered = _rank_and_dedup(raw_results)

                # Ekstraksi URL untuk log transparansi
                links = re.findall(r'https?://[^\s,;"\')\]]+', filtered)

                if links:
                    print(f"[Search Tool]: Ditemukan {len(links)} sumber relevan (setelah ranking):")
                    for i, link in enumerate(links[:3], 1):
                        clean_link = link.rstrip(',').rstrip(']').rstrip(';')
                        print(f"   {i}. {clean_link}")

                print(f"[Search Tool]: Sukses mendapatkan hasil pencarian (backend={backend}).")
                return filtered if filtered else "Tidak ada hasil pencarian."

            # Hasil kosong — coba backend berikutnya
            print(f"[Search Tool]: Backend '{backend}' return kosong, coba fallback...")

        except Exception as e:
            last_error = e
            print(f"[Search Tool]: Gagal dengan backend '{backend}' (attempt {attempt}/3): {e}")
            if attempt < len(backends):
                wait = attempt  # 1s, 2s
                time.sleep(wait)
            continue

    # Semua attempts gagal
    print(f"[Search Tool]: Gagal melakukan pencarian untuk '{query}'. Detail error: {last_error}")
    return f"[Search Tool]: Tidak dapat melakukan pencarian setelah 3 attempts. Error: {last_error}"
