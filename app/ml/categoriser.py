from __future__ import annotations

from pathlib import Path

import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

MODEL_PATH = Path(__file__).parent.parent.parent / "models" / "categoriser.joblib"

_categoriser: Pipeline | None = None


def get_categoriser() -> Pipeline | None:
    global _categoriser
    if _categoriser is None and MODEL_PATH.exists():
        _categoriser = joblib.load(MODEL_PATH)
    return _categoriser


def train(descriptions: list[str], labels: list[str]) -> Pipeline:
    pipeline = Pipeline([
        ("tfidf", TfidfVectorizer(ngram_range=(1, 2), max_features=10000, sublinear_tf=True)),
        ("clf", LogisticRegression(max_iter=500, C=5.0)),
    ])
    pipeline.fit(descriptions, labels)
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(pipeline, MODEL_PATH)
    global _categoriser
    _categoriser = pipeline
    return pipeline
