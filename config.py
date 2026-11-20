"""
Konfigurasi utama aplikasi Browsing Agent.
Mengambil variabel lingkungan dari .env dan mendefinisikan konstanta.
"""

import os
from dotenv import load_dotenv

# Muat variabel dari .env saat modul di-import
load_dotenv()


# --- Azure OpenAI ---
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_DEPLOYMENT_NAME = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")
AZURE_OPENAI_PREVIEW_API_VERSION = os.getenv("AZURE_OPENAI_PREVIEW_API_VERSION")

# --- ModelHub ---
MODELHUB_API_KEY = os.getenv("MODELHUB_API_KEY")
MODELHUB_BASE_URL = os.getenv("MODELHUB_BASE_URL")
MODELHUB_MODEL_NAME = os.getenv("MODELHUB_MODEL_NAME")


# --- Tool Limits ---
MAX_TOOL_CALLS = int(os.getenv("MAX_TOOL_CALLS"))
MAX_URLS_PER_QUERY = int(os.getenv("MAX_URLS_PER_QUERY"))
MAX_SEARCH_RESULTS = int(os.getenv("MAX_SEARCH_RESULTS"))


# --- Fetching ---
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT"))
BROWSER_FALLBACK_ENABLED = os.getenv("BROWSER_FALLBACK_ENABLED").lower() == "true"


# --- Safe Crawling ---
USER_AGENT = os.getenv("USER_AGENT")
RATE_LIMIT_PER_DOMAIN_SECONDS = float(os.getenv("RATE_LIMIT_PER_DOMAIN_SECONDS"))


# --- Content Extraction ---
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE"))
