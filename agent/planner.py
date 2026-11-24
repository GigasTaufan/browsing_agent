"""
Orkestrasi agen: state per-query, eksekusi, dan synthesize jawaban dengan citations.
Menggantikan counter global di tool_selenium.py lama.
"""

from contextvars import ContextVar, Token
from dataclasses import dataclass

from storage.evidence import EvidenceItem, EvidenceStore


class ToolLimitReached(Exception):
    """Exception yang dilempar saat batas pemanggilan tool tercapai."""


class AgentRunState:
    """State yang terisolasi untuk satu sesi query pengguna."""

    _active: ContextVar[AgentRunState | None] = ContextVar("agent_run_state", default=None)

    def __init__(self):
        self.tool_calls: dict[str, int] = {"browse_tool": 0, "search_tool": 0}
        self.urls_fetched: set[str] = set()
        self.evidence_store = EvidenceStore()
        self.blocked_domains: set[str] = set()
        self._token: Token | None = None

    def __enter__(self) -> AgentRunState:
        self._token = self._active.set(self)
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        if self._token is not None:
            self._active.reset(self._token)
            self._token = None


def get_run_state() -> AgentRunState | None:
    """Mengembalikan state untuk sesi query yang sedang berjalan."""
    return AgentRunState._active.get()


@dataclass
class AgentRunResult:
    """Jawaban final beserta evidence terstruktur yang mendasarinya."""

    answer: str
    citations: list[EvidenceItem]


def check_and_increment(tool_name: str, max_calls: int) -> None:
    """Increment counter tool dan raise ToolLimitReached jika melebihi batas."""
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
