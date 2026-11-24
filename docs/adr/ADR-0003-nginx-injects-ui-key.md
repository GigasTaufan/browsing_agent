# ADR-0003: Nginx menyuntik UI API key, tidak pernah dikirim ke browser

**Status:** Accepted

## Context

Frontend statis (frontend/) memanggil API via ingress `/ui-api/`. Jika frontend
menyimpan API key di JavaScript, key tersebut terbuka bagi siapa pun yang membuka
halaman — kredensial bocor ke browser.

## Decision

Frontend TIDAK menyimpan key apa pun. Nginx (nginx/default.conf.template) meng-rewrite
`/ui-api/*` → `/api/*` dan menyuntik header `Authorization: Bearer ${UI_API_KEY}`
dari environment container. Browser hanya melihat path `/ui-api/` tanpa kredensial.
Caller eksternal memakai path `/api/` dengan key masing-masing (diteruskan apa adanya).

## Consequences

- Key UI tidak pernah disajikan ke browser; integration test memverifikasi `UI_API_KEY` tidak ada di index.html/app.js dan bahwa ingress menyuntik header.
- Rotasi key cukup via environment Nginx, tanpa redeploy frontend.
- `/ui-api/` menjadi endpoint publik yang di-rate-limit per key UI di backend.
