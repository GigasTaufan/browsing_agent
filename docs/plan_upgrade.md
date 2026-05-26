# Roadmap Upgrade: Browsing Agent

Goal: upgrade repo `browsing_agent` dari MVP menjadi general browsing information agent yang aman, modular, dan legal-compliant.

Context:
Current repo uses LangChain agent + DuckDuckGo search + HTTP-first fetch + Selenium fallback. Improve architecture without adding stealth/bypass behavior.

---

Phase 1 — Refactor structure ✅ **COMPLETED**
- Split monolithic script into modules:
  - `agent/planner.py`
  - `tools/search.py`, `tools/fetch.py`, `tools/extract.py`
  - `policy/robots.py`, `policy/rate_limit.py`, `policy/guardrails.py`
  - `storage/evidence.py`
  - `config.py`, `main.py`
- Add type hints and Pydantic models.

Phase 2 — Fix tool execution limits ✅ **COMPLETED**
- Reset tool-call counter per user query (AgentRunState).
- Max URLs per query and max fetch depth enforced.

Phase 3 — Add safe crawling policy ✅ **COMPLETED**
- `robots.txt` checker with TTL cache (`urllib.robotparser`).
- Transparent User-Agent string.
- Per-domain rate limiter.
- Stop/backoff on HTTP 403, 429.
- No proxy rotation, fingerprint spoofing, CAPTCHA bypass, or paywall bypass.

Phase 4 — Improve fetching ✅ **COMPLETED**
- HTTP-first fetcher with `httpx`.
- Selenium only as fallback for JS-heavy pages (<500 chars).
- Reuse browser session (singleton via `_browser_instance`).
- Timeout, retry with exponential backoff, content-type filtering.

Phase 5 — Improve extraction ✅ **COMPLETED**
- Extract: title, canonical URL, main text, headings, links, fetched_at, status_code.
- `trafilatura` primary, `BeautifulSoup` fallback.
- Chunk long pages instead of blind truncate.

Phase 6 — Evidence and citations ✅ **COMPLETED**
- Structured evidence store (`EvidenceStore`) with SHA256 dedup.
- Citations in final answer.
- Prefer multiple sources.

Phase 7 — Search and ranking ✅ **COMPLETED**
- DuckDuckGo default with multi-backend retry (`lite` → `auto`).
- Rank by domain quality (`.edu`, `.gov`, Wikipedia, etc.).
- URL deduplication.

Phase 8 — Agent behavior ✅ **COMPLETED**
- Standard flow: query → search → rank → policy → fetch → extract → synthesize + cite.
- Guardrails: block illegal scraping, login, paywall, personal data.

Phase 9 — Config and environment ✅ **COMPLETED**
- Centralized `config.py` + `.env.example`.
- Settings: `MAX_TOOL_CALLS`, `MAX_URLS_PER_QUERY`, `REQUEST_TIMEOUT`, `RATE_LIMIT_PER_DOMAIN_SECONDS`, `USER_AGENT`, `BROWSER_FALLBACK_ENABLED`.

Phase 10 — Tests ✅ **COMPLETED**
- `tests/` directory with 5 test files:
  - `test_evidence.py`, `test_extract.py`, `test_limits.py`, `test_rate_limit.py`, `test_robots.py`

Phase 11 — CLI ✅ **COMPLETED**
- One-shot mode: `python main.py "your question"`
- Interactive mode: `python main.py`
- Verbose flag: `python main.py "query" --verbose`
- Sources (citations) appended to final answer.

---

## Acceptance Criteria (All Met ✅)

- [x] Agent can answer general information queries using search + browsing.
- [x] Every answer includes sources (citations).
- [x] `robots.txt` is checked before fetch.
- [x] Rate limit works per domain.
- [x] Tool-call limit resets per user query.
- [x] Browser is reused / only used as fallback.
- [x] No stealth, proxy rotation, CAPTCHA bypass, or paywall bypass.
