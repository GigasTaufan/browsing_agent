# Roadmap Upgrade: Browsing Agent

Goal: upgrade repo `browsing_agent` dari MVP menjadi general browsing information agent yang aman, modular, dan legal-compliant.

Context:
Current repo uses LangChain + pluggable search (DuckDuckGo/SearXNG) + HTTP-first fetch + Selenium fallback. Improve architecture without adding stealth/bypass behavior.

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
- Max URLs per query enforced; `max_fetch_depth` tidak diimplementasikan.

Phase 3 — Add safe crawling policy ✅ **COMPLETED**
- `robots.txt` checker with TTL cache (`urllib.robotparser`).
- Transparent User-Agent string.
- Per-domain rate limiter.
- Stop/backoff on HTTP 403, 429.
- No proxy rotation, fingerprint spoofing, CAPTCHA bypass, or paywall bypass.

Phase 4 — Improve fetching ✅ **COMPLETED**
- HTTP-first fetcher with `httpx`.
- Selenium only as fallback for JS-heavy pages (ambang `BROWSER_JS_HEAVY_MIN_CHARS`; template 500).
- Reuse browser session (singleton via `_browser_instance`).
- Timeout, retry with exponential backoff, content-type filtering.

Phase 5 — Improve extraction ✅ **COMPLETED**
- Extract: title, canonical URL, main text, headings, fetched_at, status_code.
- `trafilatura` primary, `BeautifulSoup` fallback.
- Truncate content to `FETCH_MAX_CONTENT_CHARS`; no chunking/retrieval.

Phase 6 — Evidence and citations ✅ **COMPLETED**
- Structured evidence store (`EvidenceStore`) with SHA256 dedup.
- Citations in final answer.
- Prefer multiple sources.

Phase 7 — Search and ranking ✅ **COMPLETED**
- Provider from `SEARCH_PROVIDER` (template `searxng`); DDG retry ladder from `DDG_RETRY_BACKENDS`.
- Rank by domain quality (`.edu`, `.gov`, Wikipedia, etc.).
- URL deduplication.

Phase 8 — Agent behavior ✅ **COMPLETED**
- Standard flow: query → search → rank → policy → fetch → extract → synthesize + cite.
- Guardrails: block illegal scraping, login, paywall, personal data.

Phase 9 — Config and environment ✅ **COMPLETED**
- Centralized `config.py` + `.env.example`.
- All operational settings are required in `.env`; see `.env.example`.

Phase 10 — Tests ✅ **COMPLETED**
- `tests/` suite (20+ files) covering config, API, search, fetch/extract, evidence, research/synthesis, tracing, frontend, evaluation, integration.

Phase 11 — CLI ✅ **COMPLETED**
- One-shot mode: `uv run main.py "your question"`
- Interactive mode: `uv run main.py`
- Verbose flag: `uv run main.py "query" --verbose`
- Sources (citations) appended to final answer.

---

## Acceptance Criteria (All Met ✅)

- [x] Agent can answer general information queries using search + browsing.
- [x] Released answers always have valid citations; no-evidence requests refuse without citations.
- [x] `robots.txt` is checked before fetch.
- [x] Rate limit works per domain.
- [x] Tool-call limit resets per user query.
- [x] Browser is reused / only used as fallback.
- [x] No stealth, proxy rotation, CAPTCHA bypass, or paywall bypass.
