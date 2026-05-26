"""
Entry point utama Browsing Agent.
Memuat LLM, tools, dan menjalankan CLI (interaktif atau via argumen).
Menampilkan citations di akhir jawaban.
"""

import argparse
import sys
import os
from dotenv import load_dotenv

from langchain_openai import AzureChatOpenAI
from langchain.agents import create_agent

import config
from agent.planner import reset_run_state, get_run_state
from policy.guardrails import is_query_blocked
from tools.search import search_tool
from tools.fetch import browse_tool, fetcher_cleanup


def _parse_args() -> argparse.Namespace:
    """Parse argumen command-line."""
    parser = argparse.ArgumentParser(
        description="Browsing Agent — Agen browsing web dengan sumber terpercaya.",
    )
    parser.add_argument(
        "question",
        nargs="?",
        help="Pertanyaan yang ingin dijawab (opsional — tanpa ini, mode interaktif).",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Tampilkan log detail dari setiap step.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version="%(prog)s 1.0",
    )
    return parser.parse_args()


# 1) Inisialisasi LLM (AzureChatOpenAI)
def load_llm(verbose: bool = False):
    """
    Memuat Azure LLM dari environment variables.
    """
    if verbose:
        print("[Config]: Load LLM Azure ...")
    llm = AzureChatOpenAI(
        api_key=config.AZURE_OPENAI_API_KEY,
        azure_deployment=config.AZURE_OPENAI_DEPLOYMENT_NAME,
        api_version=config.AZURE_OPENAI_PREVIEW_API_VERSION,
        temperature=0.7,
        max_tokens=1500,
        timeout=60,
        max_retries=2,
    )
    if verbose:
        print("[Config]: LLM Azure loaded.")
    return llm


# 2) Definisikan Agent
def define_agent(model, tools, system_prompt):
    """Membuat dan mengembalikan agent dengan model, tools, dan system prompt."""
    agent = create_agent(
        model=model,
        tools=tools,
        system_prompt=system_prompt,
    )
    return agent


# 3) Jalankan Agent
def run_agent(agent, question: str, verbose: bool = False):
    """
    Menjalankan agent untuk satu pertanyaan pengguna.
    Reset state per-query, terapkan guardrails, outputkan citations.
    """
    reset_run_state()

    # Guardrail: cek query user
    blocked, reason = is_query_blocked(question)
    if blocked:
        print("\n--- Jawaban Final Agent ---")
        return reason

    if verbose:
        print(f"[Planner]: Menerima query: {question!r}")
        print("[Planner]: Mengirim ke agent...")

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

    final_answer = final_msg.content if final_msg else result

    # Tambahkan citations di akhir jawaban
    state = get_run_state()
    if state and state.evidence_store.items:
        final_answer += state.evidence_store.get_citations_text()

    return final_answer


def main():
    """
    Fungsi utama: muat config, buat agent, jalankan sesuai mode CLI.
    """
    args = _parse_args()
    verbose = args.verbose

    # 0) Load .env variables
    load_dotenv()

    if verbose:
        print(f"[Config]: Deployment = {config.AZURE_OPENAI_DEPLOYMENT_NAME}")
        print(f"[Config]: MAX_TOOL_CALLS = {config.MAX_TOOL_CALLS}")
        print(f"[Config]: USER_AGENT = {config.USER_AGENT}")
        print(f"[Config]: BROWSER_FALLBACK = {config.BROWSER_FALLBACK_ENABLED}")

    # 1) Load LLM
    llm = load_llm(verbose=verbose)

    # 2) Daftar Tools
    tools = [browse_tool, search_tool]

    # 3) Create Agent
    system_prompt = (
        "You are an agent that can use tools to answer questions. "
        "Use the provided tools (browse_tool & search_tool) to gather information and provide accurate answers."
    )
    agent = define_agent(model=llm, tools=tools, system_prompt=system_prompt)

    # 4) Run sesuai mode
    if args.question:
        # Mode argumen: langsung jawab lalu exit
        if isinstance(args.question, list):
            question = " ".join(args.question)
        else:
            question = args.question

        answer = run_agent(agent, question, verbose=verbose)
        print(answer)
    else:
        # Mode interaktif: loop input()
        print("\nBrowsing Agent is ready... (mode interaktif)")
        try:
            while True:
                user_question = input("Masukkan pertanyaan Anda (atau ketik 'exit' untuk keluar): ")

                if user_question.lower() in ["exit", "quit"]:
                    print("Terima kasih! Sampai jumpa.")
                    break

                agent_answer = run_agent(agent, question=user_question, verbose=verbose)
                print(agent_answer)
        finally:
            fetcher_cleanup()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n[Exit]: Program dihentikan oleh pengguna.")
        fetcher_cleanup()
        sys.exit(0)
