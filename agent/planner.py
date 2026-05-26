"""
Orkestrasi agen: state per-query, eksekusi, dan synthesize jawaban dengan citations.
Menggantikan counter global di tool_selenium.py lama.
"""

from typing import Dict, Set, Any

from storage.evidence import EvidenceStore


class ToolLimitReached(Exception):
    """Exception yang dilempar saat batas pemanggilan tool tercapai."""
    pass


class AgentRunState:
    """
    Menyimpan state untuk satu sesi query pengguna.
    Digunakan untuk menggantikan counter global di tool_selenium.py lama.
    """

    def __init__(self):
        # Counter per jenis tool
        self.tool_calls: Dict[str, int] = {"browse_tool": 0, "search_tool": 0}
        # Set URL yang sudah di-fetch untuk query ini
        self.urls_fetched: Set[str] = set()
        # Evidence store untuk citations
        self.evidence_store = EvidenceStore()
        # Status blocked domain untuk query ini (403/429/CAPTCHA)
        self.blocked_domains: Set[str] = set()


# --- Global per-run state (di-reset sebelum setiap agent.invoke) ---
_current_run_state: AgentRunState | None = None


def reset_run_state() -> AgentRunState:
    """
    Reset state agar counter tool calls dimulai dari nol untuk query baru.
    Dipanggil di awal setiap run_agent().
    """
    global _current_run_state
    _current_run_state = AgentRunState()
    return _current_run_state


def get_run_state() -> AgentRunState | None:
    """Mengembalikan state untuk sesi query yang sedang berjalan."""
    return _current_run_state


def check_and_increment(tool_name: str, max_calls: int) -> None:
    """
    Increment counter tool dan raise ToolLimitReached jika melebihi batas.
    """
    state = get_run_state()
    if state is None:
        return

    state.tool_calls[tool_name] += 1
    if state.tool_calls[tool_name] > max_calls:
        raise ToolLimitReached(
            f"[Tool Limit]: Batas panggilan untuk {tool_name} telah tercapai "
            f"(maksimum {max_calls} kali)."
        )


def is_domain_blocked_for_run(url: str) -> bool:
    """Cek apakah domain URL ini di-block untuk query ini (403/429/CAPTCHA)."""
    from urllib.parse import urlparse
    state = get_run_state()
    if state is None:
        return False
    domain = urlparse(url).netloc.lower()
    return domain in state.blocked_domains


def block_domain_for_run(url: str) -> None:
    """Tandai domain sebagai blocked untuk query ini (dipanggil saat 403/429)."""
    from urllib.parse import urlparse
    state = get_run_state()
    if state is None:
        return
    domain = urlparse(url).netloc.lower()
    state.blocked_domains.add(domain)
