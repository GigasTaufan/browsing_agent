# ADR-0008: Blokir URL internal (SSRF) sebelum fetch

**Status:** Accepted

## Context

`browse_tool` menerima URL pilihan LLM. Sebelum M1 hanya guardrail domain bank/login
yang dicek, sehingga URL seperti `http://169.254.169.254/`, `http://redis:6379`, atau
`http://api:8000` dapat di-fetch dari container `api` yang berada di network `egress`
dan `backend`.

## Decision

`policy/guardrails.is_url_blocked` menolak URL bila:

- Skema bukan `http`/`https`.
- Hostname adalah hostname pendek tanpa titik (`redis`, `api`, `searxng`, `localhost`) —
  hanya service internal container yang memakai bentuk ini.
- Hostname adalah IP privat/loopback/link-local/multicast/reserved, termasuk bentuk
  desimal, hex, dan IPv4-embedded IPv6 (`http://2130706433/`, `::ffff:127.0.0.1`) —
  dicek setelah endpoint di-resolve.
- Setelah DNS resolve, salah satu alamat target privat/link-local/reserved.

Transport tetap memakai DNS resolver sistem; TTL TOCTOU kecil diterima karena target
adalah intranet satu host. Verifikasi memakai `fetch` yang sama lintas HTTP dan Selenium.

## Consequences

- Domain publik (mis. `example.com`) tetap dapat di-fetch; URL yang gagal di-resolve
  diperlakukan sebagai diblokir (fail-closed).
- `tests/test_guardrails.py` memverifikasi setiap kategori.
