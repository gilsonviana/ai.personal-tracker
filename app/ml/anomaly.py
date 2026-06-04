from __future__ import annotations

from collections import defaultdict
from pathlib import Path

import joblib
import numpy as np
from sklearn.ensemble import IsolationForest

MODELS_DIR = Path(__file__).parent.parent.parent / "models" / "anomaly"

_models: dict[str, IsolationForest] = {}


def _model_path(user_id: str, category: str) -> Path:
    safe_cat = category.replace(" ", "_").lower()
    return MODELS_DIR / f"{user_id}_{safe_cat}.joblib"


def load_model(user_id: str, category: str) -> IsolationForest | None:
    key = f"{user_id}_{category}"
    if key not in _models:
        path = _model_path(user_id, category)
        if path.exists():
            _models[key] = joblib.load(path)
    return _models.get(key)


def train_user_models(user_id: str, transactions: list[dict]) -> None:
    by_cat: dict[str, list[int]] = defaultdict(list)
    for tx in transactions:
        if tx.get("type") == "expense" and tx.get("category"):
            by_cat[tx["category"]].append(tx["amount"])

    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    for cat, amounts in by_cat.items():
        if len(amounts) < 10:
            continue
        X = np.array(amounts).reshape(-1, 1)
        model = IsolationForest(contamination=0.05, random_state=42)
        model.fit(X)
        key = f"{user_id}_{cat}"
        _models[key] = model
        joblib.dump(model, _model_path(user_id, cat))


def is_anomaly(user_id: str, category: str, amount: int) -> bool:
    model = load_model(user_id, category)
    if model is None:
        return False
    pred = model.predict([[amount]])
    return int(pred[0]) == -1
