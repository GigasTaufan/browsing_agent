# Desain FastAPI, frontend, dan Docker

## Tujuan

Menyediakan Browsing Agent sebagai API intranet yang dapat dipanggil aplikasi lain, beserta halaman uji sederhana. Nginx menjadi satu-satunya pintu masuk. CLI bukan antarmuka utama.

## Arsitektur

Docker Compose menjalankan dua service:

- **Nginx** menyajikan frontend statis dan reverse proxy.
- **FastAPI** memproses API, mengorkestrasi agent, dan menghubungi Azure OpenAI atau ModelHub.

Port FastAPI tidak dipublikasikan langsung ke intranet. Aplikasi pemanggil masuk melalui Nginx dan meneruskan API key-nya sendiri. Kredensial provider LLM hanya tersedia di environment backend.

## Autentikasi

Aplikasi pemanggil mengirim `Authorization: Bearer <API_KEY>`; Nginx meneruskan header tersebut ke FastAPI. FastAPI memvalidasi key terhadap daftar key yang dikonfigurasi di server.

Halaman uji menggunakan jalur proxy khusus, misalnya `/ui-api/v1/ask`. Nginx meneruskan request ke endpoint API yang sama, mengganti header Authorization dengan key UI dari environment server. Key UI tidak dikirim ke browser. HTTPS digunakan untuk melindungi key dalam transit; header autentikasi tidak dicatat dalam access log.

## Kontrak API

### `POST /api/v1/ask`

Request:

```json
{"question":"Apa perkembangan terbaru energi surya?"}
```

Response `200`:

```json
{
  "answer": "Jawaban berdasarkan informasi yang ditemukan.",
  "citations": [
    {"id": 1, "title": "Contoh sumber", "url": "https://example.com/article", "snippet": "Cuplikan singkat dari halaman sumber."}
  ]
}
```

`answer` berisi teks jawaban; citations dikembalikan terpisah. `citations` selalu array dan kosong bila tidak ada sumber yang berhasil dikumpulkan.

Error menggunakan envelope:

```json
{"error":{"code":"invalid_request","message":"question wajib diisi."}}
```

Status: `401` untuk key hilang/tidak valid, `422` untuk request tidak valid atau pertanyaan kosong, dan `500` untuk kegagalan internal tanpa membocorkan detail sensitif.

### Halaman uji

Halaman menyediakan input pertanyaan, tombol submit, indikator proses, jawaban, citations tertaut, pesan error, dan tombol **New Question**. Tombol tersebut menghapus hasil sebelumnya dan memulai query mandiri yang baru; tidak ada riwayat atau percakapan multi-turn.

## Isolasi dan lifecycle

State planner, evidence, batas tool, dan blocked-domain harus terisolasi untuk setiap request. Pemanggilan agent yang sinkron dijalankan di worker, bukan di event loop. Browser Selenium singleton tidak aman dipakai paralel; akses webdriver diserialisasi. Agent/model diinisialisasi saat startup, dan fetcher/browser ditutup saat shutdown.

## Verifikasi penerimaan

- Request API valid mengembalikan jawaban dan citations terstruktur.
- Key invalid, body invalid, dan kegagalan internal menghasilkan status serta error envelope yang ditetapkan.
- Dua query yang berjalan tumpang-tindih tidak mencampur batas tool, evidence, atau citations.
- Halaman uji dapat menjalankan query tanpa mengekspos key UI, menampilkan citations/error, dan tombol New Question membersihkan hasil untuk query baru.
- Compose menjalankan Nginx dan FastAPI; FastAPI tidak dapat diakses langsung dari intranet.
