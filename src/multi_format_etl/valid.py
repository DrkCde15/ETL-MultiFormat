"""Schema contracts and quality checks per format.

SPEC is the single source of truth: column presence at load time
(check_columns) and quality checks after cleaning (check_quality)
both derive from it.
"""

from __future__ import annotations

import pandas as pd

from multi_format_etl.load import LoadError

SPEC: dict[str, dict[str, list[str]]] = {
    "csv": {
        "required": ["transaction_id", "account_id", "amount", "timestamp"],
        "key": ["transaction_id"],
        "numeric": ["amount"],
        "temporal": ["timestamp"],
    },
    "json": {
        "required": ["transaction_id", "account_id", "amount"],
        "key": ["transaction_id"],
        "numeric": ["amount"],
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
    """Raised when quality checks fail after cleaning."""


def check_columns(df: pd.DataFrame, source_format: str) -> None:
    """Raise LoadError if expected columns are missing. Unknown formats are skipped."""
    expected = EXPECTED_COLUMNS.get(source_format)
    if expected is None:
        return
    missing = [c for c in expected if c not in df.columns]
    if missing:
        raise LoadError(f"Missing expected columns [{source_format}]: {missing}")


def check_quality(df: pd.DataFrame, source_format: str) -> None:
    """Null, duplicate-key and type checks on cleaned data.

    Raises CheckError listing every failing check at once.
    Unknown formats are skipped.
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
