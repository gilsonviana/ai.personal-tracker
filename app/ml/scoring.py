from __future__ import annotations


def compute_score(summaries: list) -> float:
    if not summaries:
        return 0.0

    scores = []
    for s in summaries:
        if s.total_income == 0:
            scores.append(0.0)
            continue
        savings_rate = s.net / s.total_income
        # Clamp: savings_rate of 0.3+ → score of 1.0
        scores.append(min(max(savings_rate / 0.3, 0.0), 1.0))

    return round(sum(scores) / len(scores) * 100, 1)
