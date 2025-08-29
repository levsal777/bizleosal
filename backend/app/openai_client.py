import os, json, httpx
from typing import Optional

BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com")
API_KEY  = os.environ.get("OPENAI_API_KEY")
MODEL    = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

if not API_KEY:
    raise RuntimeError("OPENAI_API_KEY не задан в окружении")

def _chat_completions_url():
    return f"{BASE_URL.rstrip('/')}/v1/chat/completions"

def llm_complete(prompt: str,
                 model: Optional[str] = None,
                 temperature: float = 0.2,
                 max_output_tokens: int = 800) -> str:
    m = model or MODEL
    if isinstance(prompt, bytes):
        prompt = prompt.decode("utf-8", errors="replace")
    else:
        prompt = str(prompt)

    payload = {
        "model": m,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
        "max_completion_tokens": max_output_tokens,  # для новых эндпоинтов
        "max_tokens": max_output_tokens             # на случай старых реализаций
    }

    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json; charset=utf-8",
        "Accept": "application/json",
    }

    # Игнорируем любые переменные окружения сети (trust_env=False), отключаем HTTP/2.
    with httpx.Client(timeout=60, http2=False, trust_env=False) as client:
        r = client.post(_chat_completions_url(), content=data, headers=headers)
        r.raise_for_status()
        js = r.json()
        try:
            return js["choices"][0]["message"]["content"]
        except Exception:
            return json.dumps(js, ensure_ascii=False)
