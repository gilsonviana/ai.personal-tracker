from __future__ import annotations

import httpx

from app.core.config import settings

_PROMPT = """\
You are a personal finance advisor. Respond in English regardless of the language of the transaction data provided.

Given the following monthly financial summaries (amounts in cents):
{summaries}

Provide a concise 2-3 sentence narrative analysis of the user's financial health, \
highlighting trends, strengths, and areas for improvement.\
"""


async def get_reflection(summaries: list) -> str:
    if not summaries:
        return "No data available for analysis."

    summary_text = "\n".join(
        f"- {s.period}: income={s.total_income}, expenses={s.total_expenses}, net={s.net}"
        for s in summaries[:6]
    )
    prompt = _PROMPT.format(summaries=summary_text)

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{settings.OLLAMA_BASE_URL}/api/generate",
                json={"model": "mistral:7b", "prompt": prompt, "stream": False},
            )
            resp.raise_for_status()
            return resp.json().get("response", "").strip()
    except Exception:
        return "LLM reflection unavailable. Please ensure Ollama is running with the mistral:7b model."
