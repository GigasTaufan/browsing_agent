"""
Entry point utama Browsing Agent.
Memuat LLM, tools, dan menjalankan CLI (interaktif atau via argumen).
Menampilkan citations di akhir jawaban.
"""

import argparse
import sys
from datetime import datetime

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain_openai import AzureChatOpenAI, ChatOpenAI

import config
from agent.planner import AgentRunResult, AgentRunState
from policy.guardrails import is_query_blocked
from tools.fetch import browse_tool, fetcher_cleanup
from tools.search import search_tool


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
        "--verbose",
        "-v",
        action="store_true",
        help="Tampilkan log detail dari setiap step.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version="%(prog)s 1.0",
    )
    return parser.parse_args()


# 1) Inisialisasi LLM
def setup_tracing(verbose: bool = False):
    """
    Aktifkan MLflow GenAI tracing untuk LangChain (opsional, non-fatal).
    Jika server MLflow tidak terjangkau, aplikasi tetap berjalan tanpa tracing.
    """
    if not config.MLFLOW_TRACING_ENABLED:
        if verbose:
            print("[Tracing]: MLflow tracing dinonaktifkan (MLFLOW_TRACING_ENABLED=false).")
        return None

    try:
        import mlflow

        mlflow.set_tracking_uri(config.MLFLOW_TRACKING_URI)
        mlflow.set_experiment(config.MLFLOW_EXPERIMENT_NAME)
        # Autolog LangChain: trace otomatis untuk LLM, tools, dan agent graph.
        mlflow.langchain.autolog()
        if verbose:
            print(
                f"[Tracing]: MLflow tracing aktif -> {config.MLFLOW_TRACKING_URI} "
                f"(experiment: {config.MLFLOW_EXPERIMENT_NAME})"
            )
        return mlflow
    except Exception as e:
        print(f"[Tracing]: Gagal mengaktifkan MLflow tracing ({e}). Lanjutkan tanpa tracing.")
        return None


def load_llm(verbose: bool = False):
    """Memuat ModelHub (provider utama); fallback ke Azure OpenAI jika dikonfigurasi."""
    if config.MODELHUB_API_KEY:
        if not config.MODELHUB_BASE_URL or not config.MODELHUB_MODEL_NAME:
            raise ValueError(
                "MODELHUB_BASE_URL dan MODELHUB_MODEL_NAME wajib diisi jika MODELHUB_API_KEY digunakan."
            )
        if verbose:
            print("[Config]: Load LLM ModelHub ...")
        llm = ChatOpenAI(
            api_key=config.MODELHUB_API_KEY,
            base_url=config.MODELHUB_BASE_URL,
            model=config.MODELHUB_MODEL_NAME,
            default_headers={"User-Agent": "curl/8.0"},
            temperature=0.7,
            max_tokens=1500,
            timeout=60,
            max_retries=2,
        )
        if verbose:
            print("[Config]: LLM ModelHub loaded.")
        return llm

    # Fallback: Azure OpenAI hanya jika API key-nya dikonfigurasi.
    if config.AZURE_OPENAI_API_KEY:
        missing = [
            name
            for name, value in (
                ("AZURE_OPENAI_ENDPOINT", config.AZURE_OPENAI_ENDPOINT),
                ("AZURE_OPENAI_PREVIEW_API_VERSION", config.AZURE_OPENAI_PREVIEW_API_VERSION),
            )
            if not value
        ]
        if missing:
            raise ValueError(
                f"Kredensial Azure OpenAI tidak lengkap: {', '.join(missing)}. "
                "Isi di file .env (lihat .env.example)."
            )

        if verbose:
            print("[Config]: Load LLM Azure ...")
        azure_llm = AzureChatOpenAI(
            api_key=config.AZURE_OPENAI_API_KEY,
            azure_endpoint=config.AZURE_OPENAI_ENDPOINT,
            azure_deployment=config.AZURE_OPENAI_DEPLOYMENT_NAME,
            api_version=config.AZURE_OPENAI_PREVIEW_API_VERSION,
            temperature=0.7,
            max_tokens=1500,
            timeout=60,
            max_retries=2,
        )
        if verbose:
            print("[Config]: LLM Azure loaded.")
        return azure_llm

    raise ValueError(
        "Tidak ada provider LLM terkonfigurasi. "
        "Isi MODELHUB_API_KEY (provider utama) atau kredensial Azure OpenAI (fallback) "
        "di file .env (lihat .env.example)."
    )


# 2) Definisikan Agent
def build_system_prompt() -> str:
    """System prompt dengan grounding tanggal dan prioritas bukti dari tools."""
    today = datetime.now().strftime("%Y-%m-%d")
    return (
        "You are an agent that can use tools to answer questions. "
        "Use the provided tools (browse_tool & search_tool) to gather information "
        "and provide accurate answers.\n"
        f"Today's date is {today}.\n"
        "Results from search_tool and browse_tool are real, current web evidence. "
        "If they conflict with your prior knowledge, trust the tool results — "
        "your training data may be outdated. "
        "Ground your answer in the evidence and cite the source URLs."
    )


def define_agent(model, tools, system_prompt):
    """Membuat dan mengembalikan agent dengan model, tools, dan system prompt."""
    agent = create_agent(
        model=model,
        tools=tools,
        system_prompt=system_prompt,
    )
    return agent


# 3) Jalankan Agent
def run_agent(agent, question: str, verbose: bool = False) -> AgentRunResult:
    """Run one isolated agent query and return its answer and evidence."""
    with AgentRunState() as state:
        blocked, reason = is_query_blocked(question)
        if blocked:
            return AgentRunResult(answer=reason, citations=[])

        if verbose:
            print(f"[Planner]: Menerima query: {question!r}")
            print("[Planner]: Mengirim ke agent...")

        result = agent.invoke({"messages": [{"role": "user", "content": question}]})

        messages = result.get("messages", [])
        final_msg = None
        for message in reversed(messages):
            role = getattr(message, "role", None) or getattr(message, "type", None)
            if role in ("assistant", "ai"):
                final_msg = message
                break

        answer = final_msg.content if final_msg else result
        return AgentRunResult(answer=str(answer), citations=list(state.evidence_store.items))


def _render_cli_result(result: AgentRunResult) -> str:
    """Render structured evidence using the legacy CLI citation format."""
    answer = result.answer
    if result.citations:
        citations = "\n".join(
            f"{index}. [{item.title or item.canonical_url}]({item.canonical_url})"
            for index, item in enumerate(result.citations, start=1)
        )
        answer += "\n\n---\nSumber:\n" + citations
    return answer


def main():
    """
    Fungsi utama: muat config, buat agent, jalankan sesuai mode CLI.
    """
    args = _parse_args()
    verbose = args.verbose

    # 0) Load .env variables
    load_dotenv()

    if verbose:
        if config.MODELHUB_API_KEY:
            print(f"[Config]: ModelHub model = {config.MODELHUB_MODEL_NAME}")
        else:
            print(f"[Config]: Deployment = {config.AZURE_OPENAI_DEPLOYMENT_NAME}")
        print(f"[Config]: MAX_TOOL_CALLS = {config.MAX_TOOL_CALLS}")
        print(f"[Config]: USER_AGENT = {config.USER_AGENT}")
        print(f"[Config]: BROWSER_FALLBACK = {config.BROWSER_FALLBACK_ENABLED}")

    # 0) Aktifkan MLflow tracing (opsional)
    setup_tracing(verbose=verbose)

    # 1) Load LLM
    llm = load_llm(verbose=verbose)

    # 2) Daftar Tools
    tools = [browse_tool, search_tool]

    # 3) Create Agent
    agent = define_agent(model=llm, tools=tools, system_prompt=build_system_prompt())

    # 4) Run sesuai mode
    if args.question:
        # Mode argumen: langsung jawab lalu exit
        if isinstance(args.question, list):
            question = " ".join(args.question)
        else:
            question = args.question

        answer = run_agent(agent, question, verbose=verbose)
        print(_render_cli_result(answer))
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
                print(_render_cli_result(agent_answer))
        finally:
            fetcher_cleanup()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n[Exit]: Program dihentikan oleh pengguna.")
        fetcher_cleanup()
        sys.exit(0)
