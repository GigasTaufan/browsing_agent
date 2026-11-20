from openai import OpenAI
import os
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(
    api_key=os.getenv("MODELHUB_API_KEY"),
    base_url=os.getenv("MODELHUB_BASE_URL"),
    default_headers={"User-Agent": "curl/8.0"}
)

response = client.chat.completions.create(
    model=os.getenv("MODELHUB_MODEL_NAME"),
    messages=[
        {"role": "system", "content": "Anda adalah asisten layanan pelanggan."},
        {"role": "user", "content": "Bagaimana cara mengaktifkan paket data?"}
    ],
    temperature=0.7
)

print(response.choices[0].message.content)