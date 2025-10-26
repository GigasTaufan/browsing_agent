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
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager


# 1) Inisialisasi LLM (AzureChatOpenAI)
def load_llm():
    """
    Load Azure LLM from environment variables.
    """
    print("Load LLM Azure ...")
    api_key = os.getenv("AZURE_OPENAI_API_KEY")
    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")      
    api_version = os.getenv("AZURE_OPENAI_PREVIEW_API_VERSION")
    
    llm = AzureChatOpenAI(
        api_key=api_key,
        azure_deployment=deployment,
        api_version=api_version,
        temperature=0.7,
        streaming=True,
        # callbacks=[StreamingStdOutCallbackHandler()],
    )
    print("LLM Azure loaded.")
    
    return llm


# 2) Definisikan Tools

## TOOL 1: Selenium Web Browser
@tool("web_browser", description="Buka URL dengan Selenium dan ambil teks dari <body> (dipotong 1500 char).")
def browse_web(url: str) -> str:
    """
    Menggunakan Selenium untuk membuka URL yang diberikan dan mengekstrak teks dari tag <body>.
    Mengembalikan 1500 karakter pertama dari teks yang dibersihkan.
    """
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
search_tool = DuckDuckGoSearchRun()


# 3) Define Agent
def define_agent(model, tools, system_prompt):
    """
    Definisikan dan kembalikan agent dengan model, tools, dan system prompt yang diberikan.
    """
    ## Create Agent
    agent = create_agent(
        model=model,
        tools=tools,
        system_prompt=system_prompt,
    )
    return agent

# 4) Run Agent
def run_agent(agent, question):
    """
    Jalankan agent dengan pertanyaan pengguna dan kembalikan hasilnya.
    """
    result = agent.invoke({
        "messages": [{"role": "user", "content": question}]
    })
    
    messages = result.get("messages", [])
    final_msg = None
    for m in reversed(messages):
        role = getattr(m, "role", None) or getattr(m, "type", None)
        if role in ("assistant", "ai"):
            final_msg = m
            break

    print("\n--- Jawaban Final Agent ---")
    final_answer = final_msg.content if final_msg else result
    # print(final_answer)
    return final_answer


def main():
    """
    Main function to run the browsing agent.
    """
    # 0) Load .env variables
    load_dotenv()
    
    # 1) Load LLM
    llm = load_llm()

    # 2) Daftar Tools
    tools = [browse_web, search_tool]

    # 3) Create Agent
    ## Sytem Prompt or System Message
    system_prompt = (
        "You are an agent that can use tools to answer questions. "
        "Use the provided tools (web search & selenium browser) to gather information and provide accurate answers."
    )

    ## Define the agent with llm model, tools, and system prompt
    agent = define_agent(model=llm, tools=tools, system_prompt=system_prompt)

    # 4) Run agent
    print("\nBrowsing Agent is ready...")
    ## get user question
    user_question = input("Masukkan pertanyaan Anda: ")
    ## get agent answer
    agent_answer = run_agent(agent, question=user_question)
    print(agent_answer)

if __name__ == "__main__":
    main()