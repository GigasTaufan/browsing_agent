Goal: upgrade repo `browsing_agent` dari MVP menjadi general browsing information agent yang aman, modular, dan legal-compliant.

Context:
Current repo uses LangChain agent + DuckDuckGo search + Selenium browser fetch. Improve architecture without adding stealth/bypass behavior.

Phase 1 — Refactor structure
- Split `browsing_agent.py` into modules:
  - `agent/planner.py`
  - `tools/search.py`
  - `tools/fetch.py`
  - `tools/extract.py`
  - `policy/robots.py`
  - `policy/rate_limit.py`
  - `storage/evidence.py`
  - `config.py`
  - `main.py`
- Add type hints and dataclasses/Pydantic models.

Phase 2 — Fix tool execution limits
- Reset tool-call counter per user query.
- Replace global counter with per-run state.
- Ensure max tool calls actually stops execution.
- Add max URLs per query and max fetch depth.

Phase 3 — Add safe crawling policy
- Implement robots.txt checker using `urllib.robotparser`.
- Add transparent User-Agent:
  `GigasBrowsingAgent/0.1 (+https://github.com/GigasTaufan/browsing_agent; contact: gigastaufan@gmail.com)`
- Add per-domain rate limiter.
- Stop or backoff on HTTP 403, 429, CAPTCHA-like pages, or robots disallow.
- Do not implement proxy rotation, fingerprint spoofing, CAPTCHA bypass, or paywall bypass.

Phase 4 — Improve fetching
- Use HTTP-first fetcher with `httpx`.
- Use Selenium/Playwright only as fallback for JS-heavy pages.
- Reuse browser session instead of launching one browser per URL.
- Add timeout, retry with exponential backoff, and content-type filtering.
- Skip non-HTML unless explicitly requested.

Phase 5 — Improve extraction
- Extract:
  - title
  - canonical URL
  - main text
  - headings
  - links
  - fetched_at
  - status_code
- Replace raw `body.text[:1500]` with cleaner extraction using Readability/trafilatura/BeautifulSoup.
- Chunk long pages instead of truncating blindly.

Phase 6 — Evidence and citations
- Store every fetched source as structured evidence:
  - url
  - title
  - snippet
  - fetched_at
  - text chunks
- Final answer must cite source URLs.
- Add deduplication by canonical URL/content hash.
- Prefer multiple sources for factual answers.

Phase 7 — Search and ranking
- Keep DuckDuckGo as default.
- Add interface for pluggable search providers:
  - DuckDuckGo
  - Google Custom Search later
  - Brave Search later
- Rank URLs by relevance, freshness, source quality, and duplication.

Phase 8 — Agent behavior
- Agent should follow this flow:
  User query
  → plan search terms
  → search
  → filter/rank URLs
  → policy check
  → fetch
  → extract
  → synthesize answer with citations
- Add guardrails:
  - refuse illegal scraping
  - no login/paywall bypass
  - no personal data harvesting
  - stop when blocked

Phase 9 — Config and environment
- Move env loading into `config.py`.
- Add `.env.example`.
- Pin dependency versions.
- Add settings:
  - MAX_TOOL_CALLS
  - MAX_URLS_PER_QUERY
  - REQUEST_TIMEOUT
  - RATE_LIMIT_PER_DOMAIN_SECONDS
  - USER_AGENT
  - BROWSER_FALLBACK_ENABLED

Phase 10 — Tests
- Add unit tests for:
  - robots checker
  - rate limiter
  - URL normalization
  - extractor
  - tool-call limit reset
- Add mocked fetch tests, no real websites in CI.

Phase 11 — CLI
- Keep simple CLI:
  `python main.py "your question"`
- Add verbose mode:
  `python main.py "query" --verbose`
- Print sources used at the end.

Acceptance criteria:
- Agent can answer general information queries using search + browsing.
- Every answer includes sources.
- Robots.txt is checked before fetch.
- Rate limit works per domain.
- Tool-call limit resets per user query.
- Browser is reused or only used as fallback.
- No stealth, proxy rotation, CAPTCHA bypass, or paywall bypass.