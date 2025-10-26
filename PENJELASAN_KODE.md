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
    # ... (logika selenium)
```
- **`@tool(...)`**: *Decorator* ini secara otomatis mengubah fungsi `browse_tool` menjadi sebuah `Tool` yang bisa dipahami oleh LangChain.
- **`description`**: Deskripsi ini sangat penting karena menjelaskan kepada LLM kapan dan bagaimana cara menggunakan alat ini.
- **Logika Fungsi**: Menggunakan Selenium untuk membuka URL di mode *headless* (tanpa UI), mengambil konten teks, membersihkannya, dan memotongnya untuk efisiensi.

### Alat 2: `search_tool` (DuckDuckGo)

```python
search_tool = DuckDuckGoSearchRun()
```
- Ini adalah alat siap pakai dari LangChain yang berfungsi untuk melakukan pencarian web.

---

## 4. Mendefinisikan dan Menjalankan Agen

Logika untuk membuat dan menjalankan agen juga dipecah menjadi fungsi-fungsi.

### Fungsi `define_agent()`

```python
def define_agent(model, tools, system_prompt):
    """
    Definisikan dan kembalikan agent dengan model, tools, dan system prompt yang diberikan.
    """
    agent = create_agent(
        model=model,
        tools=tools,
        system_prompt=system_prompt,
    )
    return agent
```
- Fungsi ini menerima model LLM, daftar alat, dan *system prompt* (instruksi peran) sebagai input.
- `create_agent`: Ini adalah fungsi modern dari LangChain yang merakit agen, menangani bagaimana LLM harus berinteraksi dengan alat berdasarkan instruksi yang diberikan.

### Fungsi `run_agent()`

```python
def run_agent(agent, question):
    """
    Jalankan agent dengan pertanyaan pengguna dan kembalikan hasilnya.
    """
    result = agent.invoke({
        "messages": [{"role": "user", "content": question}]
    })
    # ... (logika untuk mengekstrak pesan terakhir)
    return final_answer
```
- Fungsi ini mengambil agen yang sudah jadi dan pertanyaan dari pengguna.
- `agent.invoke(...)`: Ini adalah perintah untuk memulai eksekusi agen. Input pengguna dimasukkan ke dalam daftar `messages` dengan peran `"user"`.
- **Ekstraksi Respons**: Kode setelahnya mencari pesan terakhir dari asisten (`"assistant"` atau `"ai"`) dalam riwayat percakapan, yang merupakan jawaban final untuk pengguna.

---

## 5. Eksekusi Utama (`main`)

```python
def main():
    """
    Main function to run the browsing agent.
    """
    load_dotenv()
    llm = load_llm()
    tools = [browse_tool, search_tool]
    system_prompt = (
        "You are an agent that can use tools to answer questions. ..."
    )
    agent = define_agent(model=llm, tools=tools, system_prompt=system_prompt)

    print("\nBrowsing Agent is ready...")
    user_question = input("Masukkan pertanyaan Anda: ")
    agent_answer = run_agent(agent, question=user_question)
    print(agent_answer)

if __name__ == "__main__":
    main()
```
- **`main()`**: Fungsi ini bertindak sebagai orkestrator utama. Ia memanggil semua fungsi lain secara berurutan: memuat LLM, mendefinisikan alat, membuat agen, lalu meminta input pengguna dan menjalankan agen.
- **`if __name__ == "__main__":`**: Ini adalah konstruksi standar Python yang memastikan fungsi `main()` hanya akan dijalankan ketika skrip dieksekusi secara langsung (bukan saat diimpor sebagai modul).
