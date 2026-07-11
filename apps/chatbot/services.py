import requests
from django.conf import settings
from .prompts import SYSTEM_PROMPT

GEMINI_API_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"


def ask_gemini(message: str) -> str:
    """
    Stateless call: system prompt + pesan user saja, tanpa riwayat.
    Raises requests.RequestException kalau gagal — ditangani di view.
    """
    api_key = settings.GEMINI_API_KEY
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY belum diset di .env")

    model = getattr(settings, "GEMINI_MODEL", "gemini-3.1-flash-lite")

    payload = {
        "system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "contents": [{"role": "user", "parts": [{"text": message}]}],
    }
    resp = requests.post(
        f"{GEMINI_API_BASE_URL}/{model}:generateContent?key={api_key}",
        json=payload,
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()
    return data["candidates"][0]["content"]["parts"][0]["text"]
