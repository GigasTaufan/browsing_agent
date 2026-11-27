# ADR-0007: Cakupan guardrails mengikuti PRD (automation, bukan kata)

**Status:** Accepted

## Context

`policy/guardrails.py` memblokir kata tunggal `login`, `password`, dan `credential`.
PRD §1.3/§9 menetapkan yang dilarang adalah **login automation**, paywall bypass,
dan personal data harvesting — bukan pertanyaan sah seperti "cara ganti password akun
email". Akibatnya pertanyaan umum ikut ditolak, sementara pola automation tetap lolos
via sinonim lain.

## Decision

- Keyword diblokir hanya dalam **konteks otomasi**: `automate login`, `login automation`,
  `bypass`, `paywall`, `credential stuffing`, `brute force`, `harvest`,
  `personal data`, `scrape private`.
- `login`/`password`/`credential` sebagai kata tunggal **tidak diblokir**.
- Domain diblokir dicocokkan per label (domain persis atau subdomain), bukan substring;
  daftar duplikat dihapus dan `bank` (substring terlalu lebar) dihilangkan.
  Halaman login/signin di path tetap diblokir (tidak berubah).

## Consequences

- Pertanyaan sah ("reset password saya", "tren passwordless") lolos; "cara automate
  login instagram" tetap ditolak.
- Perubahan perilaku terlihat pengguna: dicatat di CHANGELOG.
- Penolakan URL internal/IP privat dikerjakan terpisah di ADR-0008.
