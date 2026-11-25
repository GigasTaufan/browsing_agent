import os

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

client = OpenAI(
    api_key=os.getenv("MODELHUB_API_KEY"),
    base_url=os.getenv("MODELHUB_BASE_URL"),
    default_headers={"User-Agent": "curl/8.0"},
)

response = client.chat.completions.create(
    model=os.getenv("MODELHUB_MODEL_NAME"),  # type: ignore[arg-type]
    messages=[
        {"role": "system", "content": "Anda adalah asisten yang membantu user."},
        {"role": "user", "content": "Bagaimana cara memanggil 911?"},
    ],
    temperature=0.7,
)

print(response.choices[0].message.content)
