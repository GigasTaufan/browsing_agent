# Penjelasan Kode: `browsing_agent.py`

Dokumen ini memberikan penjelasan rinci untuk setiap bagian dari skrip `browsing_agent.py`.

## 1. Impor Library

Kode dimulai dengan mengimpor semua library yang diperlukan:

```python
import os
import time
from dotenv import load_dotenv

# LangChain
from langchain_openai import AzureChatOpenAI
from langchain.agents import create_agent
from langchain.tools import tool

# Tool web search DuckDuckGo
from langchain_community.tools import DuckDuckGoSearchRun

# Selenium Webdriver
from selenium import webdriver
# ... dan komponen selenium lainnya
from webdriver_manager.chrome import ChromeDriverManager
```
- **`os`, `dotenv`**: Untuk mengelola variabel lingkungan.
- **`langchain`**: Library utama untuk membangun aplikasi berbasis LLM.
- **`DuckDuckGoSearchRun`**: Alat bawaan untuk pencarian web.
- **`selenium`, `webdriver_manager`**: Untuk otomatisasi browser.

---

## 2. Fungsionalisasi Kode

Struktur kode utama telah dipecah menjadi beberapa fungsi untuk keterbacaan dan modularitas, yang dieksekusi di dalam fungsi `main()`.

### Fungsi `load_llm()`

```python
def load_llm():
    """
    Load Azure LLM from environment variables.
    """
    print("Load LLM Azure ...")
    # ... (logika memuat kredensial)
    llm = AzureChatOpenAI(
        # ... (konfigurasi model)
    )
    print("LLM Azure loaded.")
    return llm
```
- Fungsi ini bertanggung jawab untuk memuat kredensial dari file `.env` dan menginisialisasi *instance* dari `AzureChatOpenAI`. Ini mengisolasi logika koneksi ke LLM.

---

## 3. Mendefinisikan Alat (Tools)

Agen memerlukan "alat" untuk berinteraksi dengan dunia luar. Skrip ini mendefinisikan dua alat.

### Alat 1: `browse_tool` (Selenium)

```python
@tool("browse_tool", description="Buka URL dengan Selenium dan ambil teks dari <body> (dipotong 1500 char).")
def browse_tool(url: str) -> str:
    """
    Menggunakan Selenium untuk membuka URL dan mengekstrak teks dari tag <body>.
    """
    limit_tool_calls("browse_tool_counter")
    # ... (logika selenium)
```
- **`@tool(...)`**: *Decorator* ini secara otomatis mengubah fungsi `browse_tool` menjadi sebuah `Tool` yang bisa dipahami oleh LangChain.
- **`description`**: Deskripsi ini sangat penting karena menjelaskan kepada LLM kapan dan bagaimana cara menggunakan alat ini.
- **Logika Fungsi**: Menggunakan Selenium untuk membuka URL di mode *headless* (tanpa UI), mengambil konten teks, membersihkannya, dan memotongnya untuk efisiensi. Di awal, fungsi ini memanggil `limit_tool_calls` untuk menghitung penggunaannya.

### Alat 2: `search_tool` (DuckDuckGo)

```python
@tool("search_tool", description="Lakukan pencarian web menggunakan DuckDuckGo.")
def search_tool(query: str) -> str:
    limit_tool_calls("search_tool_counter")
    
    try:
        # ... (logika pencarian)
        return DuckDuckGoSearchRun().run(query)
    except Exception as e:
        # ... (penanganan error)
```
- Sama seperti `browse_tool`, alat pencari sekarang didefinisikan sebagai fungsi yang dibungkus oleh *decorator* `@tool`. Ini memungkinkan penambahan logika kustom, seperti pemanggilan `limit_tool_calls`.

### Pembatasan Panggilan Alat (Tool Limiting)

```python
max_tool_calls = 5
tool_calls_counter = {
    "browse_tool_counter": 0,
    "search_tool_counter": 0,
}

def limit_tool_calls(tool_name):
    tool_calls_counter[tool_name] += 1
    if tool_calls_counter[tool_name] > max_tool_calls:
        print(f"[Tool Limit]: Batas panggilan untuk {tool_name} telah tercapai.")
    return None
```
- Untuk mencegah agen terjebak dalam *loop* pemanggilan alat yang tidak perlu, sebuah mekanisme pembatas sederhana ditambahkan.
- `max_tool_calls`: Menentukan berapa kali setiap alat dapat dipanggil.
- `tool_calls_counter`: Sebuah *dictionary* untuk melacak jumlah panggilan untuk setiap alat.
- `limit_tool_calls()`: Fungsi yang dipanggil oleh setiap alat untuk menaikkan penghitung dan memberikan peringatan jika batasnya terlampaui.

---

## 4. Mendefinisikan dan Menjalankan Agen

Logika untuk membuat dan menjalankan agen juga dipecah menjadi fungsi-fungsi.

### Fungsi `define_agent()`

```python
def define_agent(model, tools, system_prompt):
    # ...
    agent = create_agent(
        model=model,
        tools=tools,
        system_prompt=system_prompt,
    )
    return agent
```
- Fungsi ini menerima model LLM, daftar alat, dan *system prompt*. `create_agent` merakit agen, menangani bagaimana LLM harus berinteraksi dengan alat berdasarkan instruksi.

### Fungsi `run_agent()`

```python
def run_agent(agent, question):
    # ...
    result = agent.invoke({
        "messages": [{"role": "user", "content": question}]
    })
    # ... (logika untuk mengekstrak pesan terakhir)
    return final_answer
```
- Fungsi ini mengambil agen dan pertanyaan, lalu memanggil `agent.invoke()` untuk memulai eksekusi. Kode setelahnya mencari jawaban final dari riwayat percakapan.

---

## 5. Eksekusi Utama (`main`)

```python
def main():
    # ... (inisialisasi awal)
    agent = define_agent(model=llm, tools=tools, system_prompt=system_prompt)

    print("\nBrowsing Agent is ready...")
    while True:
        user_question = input("Masukkan pertanyaan Anda (atau ketik 'exit' untuk keluar): ")
        
        if user_question.lower() in ["exit", "quit"]:
            print("Terima kasih! Sampai jumpa.")
            break
        
        agent_answer = run_agent(agent, question=user_question)
        print(agent_answer)

if __name__ == "__main__":
    main()
```
- **`main()`**: Fungsi ini bertindak sebagai orkestrator utama. Ia memanggil semua fungsi lain secara berurutan.
- **Loop Interaktif**: Bagian eksekusi agen sekarang berada di dalam `while True`. Ini membuat program terus berjalan, memungkinkan pengguna untuk mengajukan pertanyaan berulang kali. Program akan berhenti jika pengguna mengetik `exit` atau `quit`.
- **`if __name__ == "__main__":`**: Konstruksi standar Python yang memastikan `main()` hanya berjalan saat skrip dieksekusi secara langsung.
