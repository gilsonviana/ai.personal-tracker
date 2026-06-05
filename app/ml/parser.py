from __future__ import annotations

from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from io import BytesIO

import pandas as pd
import pdfplumber


def to_cents(raw_value: str) -> int:
    cleaned = str(raw_value).strip().replace(" ", "").lstrip("-")
    has_comma = "," in cleaned
    has_dot   = "." in cleaned

    if has_comma and has_dot:
        # Whichever separator appears LAST is the decimal separator
        if cleaned.rfind(",") > cleaned.rfind("."):
            # BR format: "1.234,56" — dot = thousands, comma = decimal
            cleaned = cleaned.replace(".", "").replace(",", ".")
        else:
            # US format: "1,234.56" — comma = thousands, dot = decimal
            cleaned = cleaned.replace(",", "")
    elif has_comma and not has_dot:
        # BR decimal only: "26,27" → "26.27"
        cleaned = cleaned.replace(",", ".")
    # dot only ("26.27") or integer ("100") — already valid

    decimal = Decimal(cleaned).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return int(decimal * 100)


_DATE_KEYWORDS    = ("date", "data", "dt ", "dt.", "lançamento", "lancamento", "vencimento")
_DESC_KEYWORDS    = ("desc", "memo", "histor", "moviment", "detail", "narrative")
_AMOUNT_KEYWORDS  = ("amount", "valor", "value", "vlr", "credit", "debit", "débito", "crédito", "quantia", "montante")
_TYPE_KEYWORDS    = ("type", "tipo", "natureza", "operacao", "operação")

_ENCODINGS  = ("utf-8-sig", "utf-8", "latin-1", "cp1252")
_SEPARATORS = (";", ",", "\t", "|")   # semicolon first — most common in BR exports


def _detect_col(columns: list[str], keywords: tuple[str, ...]) -> str | None:
    return next((c for c in columns if any(k in c for k in keywords)), None)


def _col_score(columns: list[str]) -> int:
    """Score how many of our three required columns we can detect."""
    cols = [c.strip().lower() for c in columns]
    return sum([
        _detect_col(cols, _DATE_KEYWORDS)   is not None,
        _detect_col(cols, _DESC_KEYWORDS)   is not None,
        _detect_col(cols, _AMOUNT_KEYWORDS) is not None,
    ])


def _read_csv_robust(bio: BytesIO) -> pd.DataFrame | None:
    """Try every combination of encoding × separator × skiprows.

    Returns the candidate with the highest column-keyword score (≥3 columns, ≥1 match).
    This prevents a data row being mistaken for the header when an earlier skip+sep
    combination accidentally produces ≥3 columns with no recognisable names.
    """
    best_df: pd.DataFrame | None = None
    best_score = 0

    for encoding in _ENCODINGS:
        for sep in _SEPARATORS:
            for skip in range(0, 10):
                try:
                    bio.seek(0)
                    df = pd.read_csv(bio, sep=sep, dtype=str, encoding=encoding, skiprows=skip)
                    if len(df.columns) < 3 or df.empty:
                        continue
                    score = _col_score(df.columns.tolist())
                    if score > best_score:
                        best_score = score
                        best_df = df
                        if score == 3:  # perfect match — stop searching
                            return best_df
                except Exception:
                    continue

    if best_df is not None:
        return best_df

    # Headerless fallback — file has no recognisable column names in the first row
    for encoding in _ENCODINGS:
        for sep in _SEPARATORS:
            try:
                bio.seek(0)
                df = pd.read_csv(bio, sep=sep, header=None, dtype=str, encoding=encoding)
                if len(df.columns) < 3 or df.empty:
                    continue
                df.columns = [str(i) for i in range(len(df.columns))]
                return df
            except Exception:
                continue

    return None


def _parse_csv(bio: BytesIO) -> list[dict]:
    df = _read_csv_robust(bio)
    if df is None:
        return []

    df.columns = [c.strip().lower() for c in df.columns]
    cols = list(df.columns)

    date_col   = _detect_col(cols, _DATE_KEYWORDS)
    desc_col   = _detect_col(cols, _DESC_KEYWORDS)
    amount_col = _detect_col(cols, _AMOUNT_KEYWORDS)
    type_col   = _detect_col(cols, _TYPE_KEYWORDS)

    # Positional fallback: date | description | amount
    if not (date_col and desc_col and amount_col) and len(cols) >= 3:
        date_col   = date_col   or cols[0]
        desc_col   = desc_col   or cols[1]
        amount_col = amount_col or cols[2]

    if not (date_col and desc_col and amount_col):
        return []

    # Detect split credit/debit columns (e.g. Payoneer: "Credit amount" + "Debit amount")
    credit_col = next((c for c in cols if "credit" in c), None)
    debit_col  = next((c for c in cols if "debit"  in c), None)
    split_amounts = bool(credit_col and debit_col and credit_col != debit_col)

    # Detect status column — only import completed/succeeded rows when present
    status_col = next((c for c in cols if c in ("status", "estado", "situação")), None)
    _OK_STATUSES = {"completed", "complete", "succeeded", "aprovado", "concluído", "concluido"}

    rows = []
    for _, row in df.iterrows():
        try:
            # Status filter
            if status_col:
                status_val = str(row[status_col]).strip().lower()
                if status_val not in _OK_STATUSES:
                    continue

            d = pd.to_datetime(row[date_col], dayfirst=True).date()

            if split_amounts:
                # Each row has a credit column (income) and a debit column (expense)
                raw_credit = str(row[credit_col]).strip()
                raw_debit  = str(row[debit_col]).strip()
                credit_cents = to_cents(raw_credit) if raw_credit not in ("0", "0.0", "", "nan") else 0
                debit_cents  = to_cents(raw_debit)  if raw_debit  not in ("0", "0.0", "", "nan") else 0
                if credit_cents > 0:
                    cents, tx_type = credit_cents, "income"
                elif debit_cents > 0:
                    cents, tx_type = debit_cents, "expense"
                else:
                    continue
            else:
                raw_amount = str(row[amount_col])
                if not raw_amount or raw_amount.lower() in ("nan", "none", ""):
                    continue
                negative = raw_amount.strip().startswith("-")
                cents = to_cents(raw_amount)
                if cents == 0:
                    continue
                if type_col:
                    tx_type = (
                        "income"
                        if str(row[type_col]).lower() in ("credit", "income", "receita", "entrada", "crédito", "credito")
                        else "expense"
                    )
                else:
                    tx_type = "expense" if negative else "income"

            rows.append(
                {"date": d, "description": str(row[desc_col]).strip(), "amount": cents, "type": tx_type}
            )
        except Exception:
            continue
    return rows


def _parse_pdf(bio: BytesIO) -> list[dict]:
    rows = []
    bio.seek(0)
    with pdfplumber.open(bio) as pdf:
        for page in pdf.pages:
            for table in page.extract_tables():
                for row in table[1:]:
                    if not row or len(row) < 3:
                        continue
                    try:
                        d = pd.to_datetime(row[0], dayfirst=True).date()
                        desc = str(row[1]).strip()
                        raw_amount = str(row[2])
                        negative = raw_amount.strip().startswith("-")
                        cents = to_cents(raw_amount)
                        tx_type = "expense" if negative else "income"
                        rows.append({"date": d, "description": desc, "amount": cents, "type": tx_type})
                    except Exception:
                        continue
    return rows


def parse_file(bio: BytesIO, filename: str) -> list[dict]:
    if filename.lower().endswith(".pdf"):
        return _parse_pdf(bio)
    return _parse_csv(bio)
