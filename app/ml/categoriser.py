from __future__ import annotations

from pathlib import Path

import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

_MODEL_DIR = Path(__file__).parent.parent.parent / "models"
_DEFAULT_PATH = _MODEL_DIR / "categoriser.joblib"

# In-process cache: None key = default/shared model, str key = per-user model
_cache: dict[str | None, Pipeline] = {}

MIN_TRAIN_SAMPLES = 15


def get_categoriser(user_id: str | None = None) -> Pipeline | None:
    """Return the best available model: user-specific first, then shared default."""
    if user_id is not None:
        if user_id in _cache:
            return _cache[user_id]
        user_path = _MODEL_DIR / f"categoriser_{user_id}.joblib"
        if user_path.exists():
            _cache[user_id] = joblib.load(user_path)
            return _cache[user_id]

    # Fall back to default model
    if None not in _cache and _DEFAULT_PATH.exists():
        _cache[None] = joblib.load(_DEFAULT_PATH)
    return _cache.get(None)


def train(descriptions: list[str], labels: list[str], user_id: str | None = None) -> Pipeline:
    pipeline = Pipeline([
        ("tfidf", TfidfVectorizer(ngram_range=(1, 2), max_features=10000, sublinear_tf=True)),
        ("clf", LogisticRegression(max_iter=500, C=5.0)),
    ])
    pipeline.fit(descriptions, labels)

    _MODEL_DIR.mkdir(parents=True, exist_ok=True)
    path = _MODEL_DIR / (f"categoriser_{user_id}.joblib" if user_id else "categoriser.joblib")
    joblib.dump(pipeline, path)

    _cache[user_id] = pipeline
    return pipeline
