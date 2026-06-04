from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.ml.categoriser import train

SAMPLE_DATA = [
    ("SALARY PAYMENT", "Salary"),
    ("PAYROLL DEPOSIT", "Salary"),
    ("PAGAMENTO SALARIO", "Salary"),
    ("FREELANCE PROJECT", "Freelance"),
    ("DIVIDENDOS", "Investment"),
    ("RENT PAYMENT", "Housing"),
    ("ALUGUEL", "Housing"),
    ("SUPERMERCADO", "Food & Groceries"),
    ("PADARIA", "Food & Groceries"),
    ("UBER", "Transport"),
    ("IFOOD", "Food & Groceries"),
    ("FARMACIA", "Health"),
    ("HOSPITAL", "Health"),
    ("SPOTIFY", "Entertainment"),
    ("NETFLIX", "Entertainment"),
    ("ENERGIA ELETRICA", "Utilities"),
    ("AGUA", "Utilities"),
    ("AMAZON", "Other Expense"),
    ("ESCOLA", "Education"),
    ("COMBUSTIVEL", "Transport"),
]


def main():
    data_path = Path(__file__).parent / "labelled_data.json"
    if data_path.exists():
        with open(data_path) as f:
            data = json.load(f)
        descriptions = [d["description"] for d in data]
        labels = [d["category"] for d in data]
    else:
        descriptions = [d for d, _ in SAMPLE_DATA]
        labels = [label for _, label in SAMPLE_DATA]
        print(f"Using {len(descriptions)} built-in samples (no labelled_data.json found)")

    train(descriptions, labels)
    print(f"Trained on {len(descriptions)} samples. Model saved to models/categoriser.joblib")


if __name__ == "__main__":
    main()
