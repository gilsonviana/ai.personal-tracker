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

    def fmt(cents: int) -> str:
        return f"R$ {cents / 100:,.2f}"

    summary_text = "\n".join(
        f"- {s.period}: income={fmt(s.total_income)}, expenses={fmt(s.total_expenses)}, net={fmt(s.net)}"
        for s in summaries[:6]
    )
    prompt = _PROMPT.format(summaries=summary_text)

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{settings.OLLAMA_BASE_URL}/api/generate",
                json={"model": settings.OLLAMA_MODEL, "prompt": prompt, "stream": False},
            )
            resp.raise_for_status()
            return resp.json().get("response", "").strip()
    except Exception:
        return f"LLM reflection unavailable. Please ensure Ollama is running with the {settings.OLLAMA_MODEL} model."
