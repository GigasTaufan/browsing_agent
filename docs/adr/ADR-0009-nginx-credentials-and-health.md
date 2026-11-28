# ADR-0009: Kredensial dan health indicator untuk Nginx

**Status:** Accepted

## Context

Sebelumnya satu `UI_API_KEY` dipakai bersama Nginx (suntik key) dan API (auth). Satu
key untuk dua peran membuat rotasi harus menyentuh dua service dan mencampur "identitas
UI" dengan "kunci yang diizinkan API". Selain itu `/healthz` Nginx selalu 200 walau API
mati, sehingga health check port publish menganggap Nginx sehat padahal UI/API tidak.

## Decision

- Credential terpisah: `UI_API_KEY` (browser → Nginx `/ui-api/*`) harus terdaftar di
  `API_ALLOWED_KEYS`; `UI_TO_API_KEY` (Nginx → API) boleh berbeda dan juga wajib terdaftar.
  Nginx menyuntik `Authorization: Bearer ${UI_TO_API_KEY}`; `UI_API_KEY` hanya divalidasi
  saat startup (harus ada di `API_ALLOWED_KEYS`); request UI memakai `UI_TO_API_KEY` yang
  disuntik Nginx dan tidak pernah dipakai di template.
- Nginx mengekspos dua health check: `/healthz` (Nginx hidup, tidak berubah) dan
  `/healthz/ready` (proxy ke API `/healthz`; 502 bila API mati). Health check port Docker
  dan staging memakai `/healthz/ready`.
- Nginx menolak start bila `UI_TO_API_KEY`/`UI_API_KEY` kosong: Compose mewajibkannya via
  `${UI_TO_API_KEY:?...}` / `${UI_API_KEY:?...}`.

## Consequences

- Rotasi key terpisah per peran; staging tidak bisa memakai `UI_API_KEY` yang sama tanpa
  sadar — key berbeda per instance.
- `.env` lama tanpa `UI_TO_API_KEY` gagal-fast di `config.py` (pesan menyebut variabelnya).
