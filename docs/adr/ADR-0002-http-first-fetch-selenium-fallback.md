# ADR-0002: HTTP-first fetch dengan fallback Selenium

**Status:** Accepted

## Context

Banyak halaman bisa di-fetch dengan HTTP biasa (`httpx`), jauh lebih cepat dan ringan
dibanding browser. Sebagian kecil situs (SPA berat, anti-bot ringan) hanya merender
via JavaScript. Selenium headless mahal (memori, startup Chrome) dan tidak boleh
dipakai untuk bypass anti-bot (safe crawling policy).

## Decision

`tools/fetch.py` selalu mencoba `httpx` lebih dulu. Selenium headless Chrome hanya
dipakai sebagai fallback jika HTML hasil ekstraksi lebih pendek dari
`BROWSER_JS_HEAVY_MIN_CHARS`; kegagalan HTTP/non-2xx tidak memicu fallback. Fallback
hanya aktif jika `BROWSER_FALLBACK_ENABLED=true`. Tidak ada proxy rotation, fingerprint
spoofing, atau bypass CAPTCHA/paywall.

## Consequences

- Mayoritas fetch cepat dan murah; Selenium hanya menyala untuk kasus sulit.
- Resource usage predictable; Chrome driver dikelola `webdriver-manager` atau `CHROMEDRIVER_PATH`/`CHROME_BIN`, dan dibersihkan di shutdown (`fetcher_cleanup`).
- Situs yang butuh interaksi nyata (login, CAPTCHA) memang tidak didukung — by design.
