from openai import OpenAI

import config

client = OpenAI(
    api_key=config.MODELHUB_API_KEY,
    base_url=config.MODELHUB_BASE_URL,
    default_headers={"User-Agent": config.MODELHUB_USER_AGENT},
)

response = client.chat.completions.create(
    model=config.MODELHUB_MODEL_NAME,  # type: ignore[arg-type]
    messages=[
        {"role": "system", "content": "Anda adalah asisten yang membantu user."},
        {"role": "user", "content": "Bagaimana cara memanggil 911?"},
    ],
    temperature=config.LLM_TEMPERATURE,
)

print(response.choices[0].message.content)
