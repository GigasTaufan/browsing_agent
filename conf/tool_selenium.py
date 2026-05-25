import time
import re

from langchain.tools import tool

# Tool web search DuckDuckGo
from langchain_community.tools import DuckDuckGoSearchResults

# Selenium Webdriver
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

# 2) Definisikan Tools

## Max Tool Calls
max_tool_calls = 5
tool_calls_counter = {
    "browse_tool_counter": 0,
    "search_tool_counter": 0,
}

## Limit tool calls
def limit_tool_calls(tool_name):
    tool_calls_counter[tool_name] += 1
    if tool_calls_counter[tool_name] > max_tool_calls:
        print(f"[Tool Limit]: Batas panggilan untuk {tool_name} telah tercapai.")
    return None

## TOOL 1: Selenium Web Browser
@tool("browse_tool", description="Buka URL dengan Selenium dan ambil teks dari <body> (dipotong 1500 char).")
def browse_tool(url: str) -> str:
    """
    Menggunakan Selenium untuk membuka URL yang diberikan dan mengekstrak teks dari tag <body>.
    Mengembalikan 1500 karakter pertama dari teks yang dibersihkan.
    """
    limit_tool_calls("browse_tool_counter")
    
    try:
        print(f"\n[Browser Tool]: Mencoba membuka {url}...")
        chrome_options = Options()
        chrome_options.add_argument("--headless=new")  # headless modern
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")

        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)

        driver.get(url)
        time.sleep(2)  # beri waktu konten dinamis

        body_element = driver.find_element(By.TAG_NAME, 'body')
        page_text = body_element.text

        driver.quit()

        cleaned_text = " ".join(page_text.split())
        truncated_text = cleaned_text[:1500]

        print(f"[Browser Tool]: Sukses mengambil konten (dipotong 1500 karakter).")
        return truncated_text

    except Exception as e:
        print(f"[Browser Tool]: Gagal membuka {url}. Error: {e}")
        return f"Error: Tidak dapat mengambil konten dari {url}. Detail: {e}"


## TOOL 2: DuckDuckGo Web Search
@tool("search_tool", description="Lakukan pencarian web menggunakan DuckDuckGo untuk mendapatkan daftar link dan ringkasan.")
def search_tool(query: str) -> str:
    limit_tool_calls("search_tool_counter")
    
    try:
        print(f"\n[Search Tool]: Searching '{query}'...")
        
        # Inisialisasi SearchResults untuk mendapatkan data terstruktur
        search = DuckDuckGoSearchResults()
        raw_results = search.run(query)
        
        # Ekstraksi URL menggunakan Regex untuk log transparansi
        links = re.findall(r'link: (https?://\S+)', raw_results)
        
        if links:
            print(f"[Search Tool]: Ditemukan {len(links)} sumber relevan:")
            for i, link in enumerate(links[:3], 1):  # Tampilkan 3 link teratas di log
                # Bersihkan karakter koma atau kurung siku di akhir link
                clean_link = link.rstrip(',').rstrip(']')
                print(f"   {i}. {clean_link}")
        
        print(f"[Search Tool]: Sukses mendapatkan hasil pencarian.")
        
        # Kembalikan raw_results (Snippet, Title, Link) ke AI Agent
        return raw_results
        
    except Exception as e:
        print(f"[Search Tool]: Gagal melakukan pencarian untuk '{query}'. Detail error: {e}")
        return f"Error: {e}"




