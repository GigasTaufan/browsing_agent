import os
from dotenv import load_dotenv

load_dotenv()

tavily_key = os.getenv("TavilyClient")

from tavily import TavilyClient
client = TavilyClient(api_key=tavily_key)
response = client.search(
    query="Harga saham Telkom saat ini berapa?"
)
print(response)