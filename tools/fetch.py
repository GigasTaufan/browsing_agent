"""
Tool browsing halaman web.
Strategi: HTTP-first (httpx), fallback ke Selenium untuk JS-heavy pages.
Browser session di-reuse (tidak launch per URL).
Mematuhi robots.txt, rate limit, dan guardrails.
"""

import time
from typing import Optional

import httpx
from langchain.tools import tool
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

import config
from agent.planner import (
    check_and_increment, ToolLimitReached,
    is_domain_blocked_for_run, block_domain_for_run, get_run_state,
)
from policy.robots import is_url_allowed
from policy.rate_limit import DomainRateLimiter
from policy.guardrails import is_url_blocked
from tools.extract import extract_page

# --- Singleton Browser Session ---
_browser_instance: Optional[webdriver.Chrome] = None


def _get_browser() -> webdriver.Chrome:
    """Mengembalikan instance browser Chrome (singleton). Launch once, reuse many."""
    global _browser_instance
    if _browser_instance is None:
        print("[Browser Fetcher]: Meluncurkan Chrome (headless)...")
        chrome_options = Options()
        chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument(f"--user-agent={config.USER_AGENT}")

        service = Service(ChromeDriverManager().install())
        _browser_instance = webdriver.Chrome(service=service, options=chrome_options)
    return _browser_instance


def close_browser() -> None:
    """Menutup instance browser. Panggil saat program exit."""
    global _browser_instance
    if _browser_instance is not None:
        print("[Browser Fetcher]: Menutup Chrome...")
        _browser_instance.quit()
        _browser_instance = None


# --- HTTP Fetcher ---
class HttpFetcher:
    """Fetcher berbasis HTTP dengan timeout, retry, dan exponential backoff."""

    def __init__(self):
        self.client = httpx.Client(
            headers={"User-Agent": config.USER_AGENT},
            timeout=config.REQUEST_TIMEOUT,
            follow_redirects=True,
        )
        self.max_retries = 3

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
                wait = 2 ** attempt
                print(f"[HTTP Fetch]: Retry {attempt}/{self.max_retries} untuk {url} (error: {e}). Menunggu {wait}s...")
                time.sleep(wait)

            except Exception as e:
                print(f"[HTTP Fetch]: Gagal fetch {url}: {e}")
                return 0, "", ""

        # Semua retry gagal
        return 0, "", ""

    def close(self) -> None:
        """Menutup HTTP client."""
        self.client.close()


# Global HTTP fetcher instance
_http_fetcher: Optional[HttpFetcher] = None


def _get_http_fetcher() -> HttpFetcher:
    """Mengembalikan singleton HttpFetcher."""
    global _http_fetcher
    if _http_fetcher is None:
        _http_fetcher = HttpFetcher()
    return _http_fetcher


def close_http_fetcher() -> None:
    """Menutup HTTP fetcher."""
    global _http_fetcher
    if _http_fetcher is not None:
        _http_fetcher.close()
        _http_fetcher = None


# Global rate limiter
_rate_limiter = DomainRateLimiter()


def _is_js_heavy(content_type: str, html: str) -> bool:
    """
    Deteksi halaman yang mungkin perlu browser (JS-heavy).
    Simple heuristic: jika content-type bukan HTML atau body terlalu kecil.
    """
    if "html" not in content_type:
        return False  # Bukan HTML — tidak ada gunanya pakai browser

    # Jika body text terlalu pendek mungkin JS belum render
    # Threshold: < 500 karakter teks bersih
    text_length = len(" ".join(BeautifulSoup(html, "lxml").get_text().split()))
    if text_length < 500:
        return True
    return False


@tool("browse_tool", description="Buka URL dengan HTTP-first (fallback browser) dan ambil teks dari <body>.")
def browse_tool(url: str) -> str:
    """
    Mengambil konten dari URL menggunakan HTTP-first strategy.
    Fallback ke Selenium jika halaman JS-heavy.
    Mematuhi: limit tool, guardrails, robots.txt, rate limit.
    """
    # 1) Cek domain yang sudah diblokir (403/429) untuk query ini
    if is_domain_blocked_for_run(url):
        return f"[Browser Tool]: Domain ini sudah diblokir untuk query ini (403/429 sebelumnya)."

    # 2) Tool limit check
    try:
        check_and_increment("browse_tool", config.MAX_TOOL_CALLS)
    except ToolLimitReached as e:
        return str(e)

    # 3) Guardrails
    blocked, reason = is_url_blocked(url)
    if blocked:
        return reason

    # 4) Robots.txt check
    if not is_url_allowed(url):
        return f"[Robots Policy]: URL '{url}' tidak diizinkan oleh robots.txt."

    # 5) Rate limit
    _rate_limiter.wait_if_needed(url)

    # 6) HTTP fetch (primary)
    print(f"\n[Browser Tool]: Fetching {url} via HTTP...")
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

    # 7) Skip non-HTML content
    if "html" not in content_type:
        return (
            f"[Browser Tool]: Content-Type '{content_type}' bukan HTML. "
            "Skip konten non-halaman web."
        )

    # 8) Cek apakah perlu fallback ke browser (JS-heavy detection)
    from bs4 import BeautifulSoup
    soup_text = " ".join(BeautifulSoup(html, "lxml").get_text().split())
    is_js = len(soup_text) < 500

    if is_js and config.BROWSER_FALLBACK_ENABLED:
        print(f"[Browser Tool]: Halaman terlalu ringan ({len(soup_text)} chars), "
              "mencoba fallback via Selenium...")
        try:
            driver = _get_browser()
            driver.get(url)
            time.sleep(2)
            body_element = driver.find_element(By.TAG_NAME, 'body')
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

    # 9) Extract structured content & store evidence
    extracted = extract_page(html, url, status_code=status)
    _store_evidence(extracted)

    print(f"[Browser Tool]: Sukses fetch via HTTP ({len(soup_text)} chars).")
    return _truncated_for_llm(extracted)


def _store_evidence(extracted) -> None:
    """Simpan hasil ekstraksi ke evidence store di state query ini."""
    state = get_run_state()
    if state is not None:
        state.evidence_store.add(extracted)
        state.urls_fetched.add(extracted.url)


def _truncated_for_llm(extracted, max_chars: int = 3000) -> str:
    """
    Konversi extracted page ke string yang siap dikirim ke LLM.
    Termasuk title + text (truncate jika terlalu panjang).
    """
    parts = []
    if extracted.title:
        parts.append(f"Judul: {extracted.title}")
    parts.append(f"URL: {extracted.url}")
    if extracted.headings:
        parts.append(f"Headings: {' | '.join(extracted.headings[:5])}")
    text = extracted.main_text[:max_chars]
    parts.append(f"Konten:\n{text}")
    return "\n\n".join(parts)


def fetcher_cleanup() -> None:
    """Panggil ini saat program exit untuk menutup semua session."""
    close_http_fetcher()
    close_browser()
