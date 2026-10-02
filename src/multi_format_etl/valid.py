"""Contratos de schema e checks de qualidade por formato.

SPEC é a fonte única de verdade: presença de colunas na carga
(check_columns) e checks de qualidade após a limpeza (check_quality)
derivam dela.
"""

from __future__ import annotations

import pandas as pd

from multi_format_etl.load import LoadError

SPEC: dict[str, dict[str, list[str]]] = {
    # csv: Kaggle usa-banking-transactions (fonte real — fetch_kaggle.py)
    "csv": {
        "required": [
            "transaction_id",
            "transaction_date",
            "transaction_amount",
            "transaction_status",
        ],
        "key": ["transaction_id"],
        "numeric": ["transaction_amount"],
        "temporal": ["transaction_date"],
    },
    # json: série BCB SGS (fonte real — fetch_json.py). `data` permanece
    # string dd/mm/yyyy: parsing livre é ambíguo (dayfirst) e foi adiado
    # junto com o trabalho de fuso horário (achado A7 da revisão).
    "json": {
        "required": ["data", "valor"],
        "key": ["data"],
        "numeric": ["valor"],
        "temporal": [],
    },
    "xml": {
        "required": ["customer_id", "full_name"],
        "key": ["customer_id"],
        "numeric": [],
        "temporal": [],
    },
    "logs": {
        "required": ["timestamp", "account", "type", "amount", "status"],
        "key": ["timestamp", "account", "type", "amount"],
        "numeric": ["amount"],
        "temporal": ["timestamp"],
    },
}

EXPECTED_COLUMNS: dict[str, list[str]] = {
    fmt: spec["required"] for fmt, spec in SPEC.items()
}


class CheckError(RuntimeError):
    """Lançado quando os checks de qualidade falham após a limpeza."""


def check_columns(df: pd.DataFrame, source_format: str) -> None:
    """Lança LoadError se as colunas esperadas faltarem. Desconhecidos são ignorados."""
    expected = EXPECTED_COLUMNS.get(source_format)
    if expected is None:
        return
    missing = [c for c in expected if c not in df.columns]
    if missing:
        raise LoadError(f"Missing expected columns [{source_format}]: {missing}")


def check_quality(df: pd.DataFrame, source_format: str) -> None:
    """Checks de nulos, chave duplicada e tipos nos dados limpos.

    Lança CheckError listando todos os checks que falharam de uma vez.
    Formatos desconhecidos são ignorados.
    """
    spec = SPEC.get(source_format)
    if spec is None:
        return
    problems: list[str] = []
    required = [c for c in spec["required"] if c in df.columns]
    for col, nulls in df[required].isna().sum().items():
        if nulls:
            problems.append(f"{nulls} null(s) in required column '{col}'")
    key = spec["key"]
    if key and all(c in df.columns for c in key):
        duplicates = int(df.duplicated(subset=key).sum())
        if duplicates:
            problems.append(f"{duplicates} duplicate key(s) on {key}")
    for col in spec["numeric"]:
        if col in df.columns and not pd.api.types.is_numeric_dtype(df[col]):
            problems.append(f"column '{col}' is {df[col].dtype}, expected numeric")
    for col in spec["temporal"]:
        if col in df.columns and not pd.api.types.is_datetime64_any_dtype(df[col]):
            problems.append(f"column '{col}' is {df[col].dtype}, expected datetime")
    if problems:
        raise CheckError(
            f"Quality checks failed [{source_format}]: " + "; ".join(problems)
        )
