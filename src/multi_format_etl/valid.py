"""Contratos de schema, checks de qualidade e relatório por formato.

SPEC é a fonte única de verdade: presença de colunas na carga
(`check_columns`), regras de qualidade pós-limpeza (`check_quality` —
nulos, chave, tipos, faixas, enums e frescor) e o relatório JSON
gravado pelo `run_load` derivam dela.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from multi_format_etl.load import LoadError

SPEC: dict[str, dict] = {
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
        "ranges": {"transaction_amount": {"min": 0}},
        "enums": {
            "transaction_status": ["Failed", "Pending", "Success"],
            "fraud_flag": ["No", "Yes"],
        },
        "freshness": ["transaction_date"],
    },
    # json: série BCB SGS (fonte real — fetch_json.py). `data` permanece
    # string dd/mm/yyyy: parsing livre é ambíguo (dayfirst) e foi adiado
    # junto com o trabalho de fuso horário (achado A7 da revisão).
    "json": {
        "required": ["data", "valor"],
        "key": ["data"],
        "numeric": ["valor"],
        "temporal": [],
        "ranges": {"valor": {"min": 0}},
        "enums": {},
        "freshness": [],
    },
    "xml": {
        "required": ["customer_id", "full_name"],
        "key": ["customer_id"],
        "numeric": [],
        "temporal": [],
        "ranges": {},
        "enums": {},
        "freshness": [],
    },
    "logs": {
        "required": ["timestamp", "account", "type", "amount", "status"],
        "key": ["timestamp", "account", "type", "amount"],
        "numeric": ["amount"],
        "temporal": ["timestamp"],
        "ranges": {"amount": {"min": 0}},
        "enums": {
            "type": ["deposit", "fee", "payment", "withdrawal"],
            "status": ["completed", "failed"],
        },
        "freshness": ["timestamp"],
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


def check_quality(df: pd.DataFrame, source_format: str) -> list[str]:
    """Checks de qualidade nos dados limpos: nulos, chave, tipos, faixas,
    enums e frescor (datas futuras).

    Retorna os checks executados (ids `categoria:coluna`). Lança CheckError
    listando todos os problemas de uma vez. Formatos desconhecidos são
    ignorados (lista vazia).
    """
    spec = SPEC.get(source_format)
    if spec is None:
        return []
    problems: list[str] = []
    executed: list[str] = []

    required = [c for c in spec["required"] if c in df.columns]
    for col in required:
        executed.append(f"null:{col}")
        nulls = int(df[col].isna().sum())
        if nulls:
            problems.append(f"{nulls} null(s) in required column '{col}'")

    key = spec["key"]
    if key and all(c in df.columns for c in key):
        executed.append(f"key:{'+'.join(key)}")
        duplicates = int(df.duplicated(subset=key).sum())
        if duplicates:
            problems.append(f"{duplicates} duplicate key(s) on {key}")

    for col in spec["numeric"]:
        if col in df.columns:
            executed.append(f"type:{col}")
            if not pd.api.types.is_numeric_dtype(df[col]):
                problems.append(f"column '{col}' is {df[col].dtype}, expected numeric")

    for col in spec["temporal"]:
        if col in df.columns:
            executed.append(f"time:{col}")
            if not pd.api.types.is_datetime64_any_dtype(df[col]):
                problems.append(f"column '{col}' is {df[col].dtype}, expected datetime")

    for col, bounds in spec.get("ranges", {}).items():
        if col in df.columns and pd.api.types.is_numeric_dtype(df[col]):
            executed.append(f"range:{col}")
            if "min" in bounds:
                below = int((df[col] < bounds["min"]).sum())
                if below:
                    problems.append(
                        f"{below} value(s) below min {bounds['min']} in column '{col}'"
                    )
            if "max" in bounds:
                above = int((df[col] > bounds["max"]).sum())
                if above:
                    problems.append(
                        f"{above} value(s) above max {bounds['max']} in column '{col}'"
                    )

    for col, allowed in spec.get("enums", {}).items():
        if col in df.columns:
            executed.append(f"enum:{col}")
            outside = int((df[col].notna() & ~df[col].isin(allowed)).sum())
            if outside:
                problems.append(
                    f"{outside} value(s) outside the allowed set in column '{col}'"
                )

    for col in spec.get("freshness", []):
        if col in df.columns and pd.api.types.is_datetime64_any_dtype(df[col]):
            executed.append(f"freshness:{col}")
            future = int((df[col] > pd.Timestamp.now(tz=df[col].dt.tz)).sum())
            if future:
                problems.append(
                    f"{future} future value(s) in temporal column '{col}'"
                )

    if problems:
        raise CheckError(
            f"Quality checks failed [{source_format}]: " + "; ".join(problems)
        )
    return executed


def write_report(report: dict, path: Path) -> Path:
    """Grava o relatório de qualidade como JSON UTF-8 indentado e retorna o caminho."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, default=str) + "\n",
        encoding="utf-8",
    )
    return path


__all__ = [
    "CheckError",
    "EXPECTED_COLUMNS",
    "SPEC",
    "check_columns",
    "check_quality",
    "write_report",
]
