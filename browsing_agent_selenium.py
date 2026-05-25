import os
import time
from dotenv import load_dotenv

# LangChain
from langchain_openai import AzureChatOpenAI
from langchain.agents import create_agent

from conf.tool_selenium import browse_tool, search_tool

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
        # endpoint=endpoint,
        temperature=0.7,
        max_tokens=1500,
        timeout=60,
        max_retries=2,
        # streaming=True,
        # callbacks=[StreamingStdOutCallbackHandler()],
    )
    print("LLM Azure loaded.")
    
    return llm

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
    tools = [browse_tool, search_tool]

    # 3) Create Agent
    ## Sytem Prompt or System Message
    system_prompt = (
        "You are an agent that can use tools to answer questions. "
        "Use the provided tools (browse_tool & search_tool) to gather information and provide accurate answers."
    )

    ## Define the agent with llm model, tools, and system prompt
    agent = define_agent(model=llm, tools=tools, system_prompt=system_prompt)

    # 4) Run agent
    print("\nBrowsing Agent is ready...")
    while True:
        # Dapatkan pertanyaan pengguna
        user_question = input("Masukkan pertanyaan Anda (atau ketik 'exit' untuk keluar): ")
        
        # Loop exit condition 
        if user_question.lower() in ["exit", "quit"]:
            print("Terima kasih! Sampai jumpa.")
            break
        
        # Dapatkan jawaban dari agen
        agent_answer = run_agent(agent, question=user_question)
        print(agent_answer)

if __name__ == "__main__":
    main()