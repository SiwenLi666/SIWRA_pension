import os
import openai

# You can set this in your .env or config
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Model name for GPT-4.1 nano (update if OpenAI changes naming)
GPT41NANO_MODEL = "gpt-4.1-nano"

def ask_llm_gpt41nano(prompt: str, api_key: str = None, temperature: float = 0.2) -> str:
    """
    Calls OpenAI's GPT-4.1 nano model with the given prompt (OpenAI >=1.0.0 syntax).
    Returns the response text.
    """
    api_key = api_key or OPENAI_API_KEY
    if not api_key:
        raise ValueError("OPENAI_API_KEY must be set in environment or provided explicitly.")
    client = openai.OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model=GPT41NANO_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=temperature
    )
    return response.choices[0].message.content
