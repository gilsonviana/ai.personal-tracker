from __future__ import annotations

import httpx

from app.core.config import settings

_PROMPT = """\
You are a personal finance advisor. Respond in English. Be specific and concise.

Financial Health Score: {score}/100
(Savings component: 70% of score, maxes out at a 30% monthly savings rate.
Budget component: 30% of score. Months with negative net or savings below 10% drag the score down.)

Monthly data, most recent first (all amounts in {currency}):
{summaries}

Rules:
- Only reference months and categories listed above.
- Do not invent numbers or categories.
- For [SPIKE] months, name the specific categories driving the high expenses.

Respond in exactly two parts, with no preamble:

1. Analysis — 2 to 3 sentences. Identify the month(s) with the worst expense-to-income ratio, \
name the specific categories that caused spikes (use the breakdown lines for [SPIKE] months), \
and state whether the overall savings rate is trending up, down, or flat.

2. Next steps — exactly 2 to 3 numbered actions. Each must: name a specific expense category, \
give a concrete reduction target in {currency}, and state the expected savings rate impact. \
Prioritise the categories that appear in [SPIKE] months.\
"""


async def get_reflection(
    summaries: list,
    score: float,
    category_expenses: dict[str, dict[str, int]] | None = None,
    main_currency: str = "BRL",
) -> str:
    if not summaries:
        return "No data available for analysis."

    def fmt(cents: int) -> str:
        return f"{cents / 100:,.0f}"

    # Compute average expenses to identify spike months
    expense_values = [s.total_expenses for s in summaries if s.total_expenses > 0]
    avg_exp = sum(expense_values) / len(expense_values) if expense_values else 0

    lines: list[str] = []
    for s in reversed(summaries[:12]):
        savings_pct = (s.net / s.total_income * 100) if s.total_income else 0
        is_spike = s.total_expenses > avg_exp * 1.2 or s.net < 0

        marker = "  [SPIKE]" if is_spike else ""
        lines.append(
            f"- {s.period}: income {fmt(s.total_income)} | "
            f"expenses {fmt(s.total_expenses)} | "
            f"net {fmt(s.net)} | "
            f"savings {savings_pct:.0f}%"
            f"{marker}"
        )

        if is_spike and category_expenses and s.period in category_expenses:
            cats = category_expenses[s.period]
            top = sorted(cats.items(), key=lambda x: x[1], reverse=True)[:5]
            breakdown = " · ".join(f"{name} {fmt(amt)}" for name, amt in top)
            lines.append(f"  → Top expenses: {breakdown}")

    summary_text = "\n".join(lines)

    prompt = _PROMPT.format(
        score=round(score, 1),
        currency=main_currency,
        summaries=summary_text,
    )

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{settings.OLLAMA_BASE_URL}/api/generate",
                json={"model": settings.OLLAMA_MODEL, "prompt": prompt, "stream": False},
            )
            resp.raise_for_status()
            return resp.json().get("response", "").strip()
    except Exception:
        return (
            f"LLM reflection unavailable. "
            f"Please ensure Ollama is running with the {settings.OLLAMA_MODEL} model."
        )
