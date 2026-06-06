from __future__ import annotations

import httpx

from app.core.config import settings

_PROMPT = """\
You are a personal finance advisor. Respond in English.

Financial Health Score: {score}/100
(Score = 70% savings component + 30% budget compliance. \
Max savings component is reached at a 30% savings rate.)

Monthly summaries (most recent first, amounts in BRL):
{summaries}

Structure your response in exactly two parts:

1. Analysis — 2 to 3 sentences identifying concrete patterns: spending spikes, \
income volatility, months where expenses exceeded income, and whether the savings \
rate is improving or declining. Reference specific months or amounts where helpful.

2. Next steps — exactly 2 to 3 numbered, specific, actionable recommendations \
that would directly raise the health score. Each step must name a category or \
behaviour and a measurable target (e.g. "Reduce recurring expenses in March by \
10% to push your savings rate above 30% and reach a score of 80+").\
"""


async def get_reflection(summaries: list, score: float) -> str:
    if not summaries:
        return "No data available for analysis."

    def fmt(cents: int) -> str:
        return f"R$ {cents / 100:,.2f}"

    summary_text = "\n".join(
        f"- {s.period}: income={fmt(s.total_income)}, expenses={fmt(s.total_expenses)}, net={fmt(s.net)}"
        for s in reversed(summaries[:12])
    )
    prompt = _PROMPT.format(score=round(score, 1), summaries=summary_text)

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
