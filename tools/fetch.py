"""
Tool browsing halaman web.
Strategi: HTTP-first (httpx), fallback ke Selenium untuk JS-heavy pages.
Browser session di-reuse (tidak launch per URL).
Mematuhi robots.txt, rate limit, dan guardrails.
"""

import threading
import time

import httpx
from langchain.tools import tool
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager

import config
from agent.planner import (
    ToolLimitReached,
    block_domain_for_run,
    check_and_increment,
    get_run_state,
    is_domain_blocked_for_run,
)
from policy.guardrails import is_url_blocked
from policy.rate_limit import DomainRateLimiter
from policy.robots import is_url_allowed
from tools.extract import extract_page

# --- Singleton Browser Session ---
_browser_instance: webdriver.Chrome | None = None
_browser_lock = threading.Lock()


def _get_browser() -> webdriver.Chrome:
    """Mengembalikan instance browser Chrome (singleton). Launch once, reuse many."""
    global _browser_instance
    if _browser_instance is None:
        print("[Browser Fetcher]: Meluncurkan Chrome (headless)...")
        chrome_options = Options()
        chrome_binary = config.CHROME_BIN
        if chrome_binary:
            chrome_options.binary_location = chrome_binary
        chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument(f"--user-agent={config.USER_AGENT}")

        chromedriver_path = config.CHROMEDRIVER_PATH
        if chromedriver_path:
            service = Service(chromedriver_path)
        else:
            service = Service(ChromeDriverManager().install())
        _browser_instance = webdriver.Chrome(service=service, options=chrome_options)
    return _browser_instance


def close_browser() -> None:
    """Menutup instance browser. Panggil saat program exit."""
    global _browser_instance
    with _browser_lock:
        if _browser_instance is not None:
            print("[Browser Fetcher]: Menutup Chrome...")
            driver, _browser_instance = _browser_instance, None
            driver.quit()


# --- HTTP Fetcher ---
class HttpFetcher:
    """Fetcher berbasis HTTP dengan timeout, retry, dan exponential backoff."""

    def __init__(self):
        self.client = httpx.Client(
            headers={"User-Agent": config.USER_AGENT},
            timeout=config.REQUEST_TIMEOUT,
            follow_redirects=True,
        )
        self.max_retries = config.FETCH_MAX_RETRIES

    def fetch(self, url: str) -> tuple[int, str, str]:
        """
        Fetch URL via HTTP.

        Returns:
            (status_code, content_type, content_text)
        """
        for attempt in range(1, self.max_retries + 1):
            try:
                response = self.client.get(url)
                content_type = response.headers.get("content-type", "").lower()
                return response.status_code, content_type, response.text

            except (httpx.TimeoutException, httpx.ConnectError) as e:
                wait = config.FETCH_BACKOFF_BASE_SECONDS**attempt
                print(
                    f"[HTTP Fetch]: Retry {attempt}/{self.max_retries} untuk {url} (error: {e}). Menunggu {wait}s..."
                )
                time.sleep(wait)

            except Exception as e:
                print(f"[HTTP Fetch]: Gagal fetch {url}: {e}")
                return 0, "", ""

        # Semua retry gagal
        return 0, "", ""

    def close(self) -> None:
        """Menutup HTTP client."""
        self.client.close()


# Global HTTP fetcher instance: satu per satu request agar client tidak dipakai
# bersamaan oleh beberapa thread API (retry/backoff pun tidak saling rebut).
_http_fetcher: HttpFetcher | None = None
_fetcher_lock = threading.Lock()


def _get_http_fetcher() -> HttpFetcher:
    """Mengembalikan singleton HttpFetcher."""
    global _http_fetcher
    if _http_fetcher is None:
        _http_fetcher = HttpFetcher()
    return _http_fetcher


def close_http_fetcher() -> None:
    """Menutup HTTP fetcher."""
    global _http_fetcher
    with _fetcher_lock:
        if _http_fetcher is not None:
            _http_fetcher.close()
            _http_fetcher = None


# Global rate limiter
_rate_limiter = DomainRateLimiter()


def _is_js_heavy(content_type: str, body_text: str) -> bool:
    """
    Deteksi halaman yang mungkin perlu browser (JS-heavy).

    Heuristik: HTML dengan teks bersih < BROWSER_JS_HEAVY_MIN_CHARS. `body_text` adalah
    teks yang sudah diekstrak `extract_page`, agar HTML tidak diparse dua kali.
    """
    if "html" not in content_type:
        return False  # Bukan HTML — tidak ada gunanya pakai browser

    return len(body_text) < config.BROWSER_JS_HEAVY_MIN_CHARS


@tool(
    "browse_tool",
    description="Buka URL dengan HTTP-first (fallback browser) dan ambil teks dari <body>.",
)
def browse_tool(url: str) -> str:
    """
    Mengambil konten dari URL menggunakan HTTP-first strategy.
    Fallback ke Selenium jika halaman JS-heavy.
    Mematuhi: limit tool, guardrails, robots.txt, rate limit.
    """
    # 1) Guardrails + cek domain yang sudah diblokir (403/429) untuk query ini
    blocked, reason = is_url_blocked(url)
    if blocked:
        return reason
    if is_domain_blocked_for_run(url):
        return "[Browser Tool]: Domain ini sudah diblokir untuk query ini (403/429 sebelumnya)."

    # 2) Tool limit check
    try:
        check_and_increment("browse_tool", config.MAX_TOOL_CALLS)
    except ToolLimitReached as e:
        return str(e)

    # Batasi URL unik sebelum akses jaringan, termasuk pengecekan robots.txt.
    state = get_run_state()
    if state is not None and url not in state.urls_fetched:
        if len(state.urls_fetched) >= config.MAX_URLS_PER_QUERY:
            return (
                f"[URL Limit]: Batas URL untuk query ini telah tercapai "
                f"(maksimum {config.MAX_URLS_PER_QUERY} URL unik)."
            )

    # 3) Robots.txt check
    if not is_url_allowed(url):
        return f"[Robots Policy]: URL '{url}' tidak diizinkan oleh robots.txt."

    # 4) Rate limit
    _rate_limiter.wait_if_needed(url)

    # Percobaan gagal tetap memakai kuota; retry/fallback URL yang sama tidak.
    if state is not None:
        state.urls_fetched.add(url)

    # 5) HTTP fetch (primary)
    print(f"\n[Browser Tool]: Fetching {url} via HTTP...")
    with _fetcher_lock:
        fetcher = _get_http_fetcher()
        status, content_type, html = fetcher.fetch(url)

    if status == 0:
        return f"[Browser Tool]: Gagal fetch {url} setelah {fetcher.max_retries} retry."

    if status in (403, 429):
        block_domain_for_run(url)
        return (
            f"[Browser Tool]: Server menolak request ({status}). "
            "Mungkin terkena rate limit atau blokir."
        )

    if not 200 <= status < 300:
        return f"[Browser Tool]: HTTP {status}; halaman gagal tidak dipakai sebagai sumber."

    # 6) Skip non-HTML content
    if "html" not in content_type:
        return (
            f"[Browser Tool]: Content-Type '{content_type}' bukan HTML. "
            "Skip konten non-halaman web."
        )

    # 7) Ekstraksi sekali; HTML tidak diparse ulang untuk deteksi JS-heavy.
    extracted = extract_page(html, url, status_code=status)
    if config.BROWSER_FALLBACK_ENABLED and _is_js_heavy(content_type, extracted.main_text):
        print("[Browser Tool]: Teks halaman terlalu pendek, mencoba fallback via Selenium...")
        try:
            with _browser_lock:
                driver = _get_browser()
                driver.get(url)
                # Explicit wait: deteksi <body> hadir, maksimal BROWSER_WAIT_TIMEOUT detik.
                body_element = WebDriverWait(driver, config.BROWSER_WAIT_TIMEOUT).until(
                    EC.presence_of_element_located((By.TAG_NAME, "body"))
                )
                body_text = body_element.text
                cleaned = " ".join(body_text.split())

            # Fallback HTML: tidak ada raw HTML dari Selenium, simulasi body
            fallback_html = f"<html><body>{body_text}</body></html>"
            extracted = extract_page(fallback_html, url, status_code=200)
            _store_evidence(extracted)

            print(f"[Browser Tool]: Sukses fetch via fallback browser ({len(cleaned)} chars).")
            return _truncated_for_llm(extracted)
        except Exception as e:
            return f"[Browser Tool]: Fallback browser gagal: {e}"

    # 8) Store evidence
    _store_evidence(extracted)

    print(f"[Browser Tool]: Sukses fetch via HTTP ({len(extracted.main_text)} chars).")
    return _truncated_for_llm(extracted)


def _store_evidence(extracted) -> None:
    """Simpan hasil ekstraksi ke evidence store di state query ini."""
    state = get_run_state()
    if state is not None:
        state.evidence_store.add(extracted)


def _truncated_for_llm(extracted, max_chars: int | None = None) -> str:
    """
    Konversi extracted page ke string yang siap dikirim ke LLM.
    Termasuk title + text (truncate jika terlalu panjang).
    """
    if max_chars is None:
        max_chars = config.FETCH_MAX_CONTENT_CHARS
    parts = []
    if extracted.title:
        parts.append(f"Judul: {extracted.title}")
    parts.append(f"URL: {extracted.url}")
    if extracted.headings:
        parts.append(f"Headings: {' | '.join(extracted.headings[: config.FETCH_MAX_HEADINGS])}")
    text = extracted.main_text[:max_chars]
    parts.append(f"Konten:\n{text}")
    return "\n\n".join(parts)


def fetcher_cleanup() -> None:
    """Panggil ini saat program exit untuk menutup semua session."""
    close_http_fetcher()
    close_browser()
