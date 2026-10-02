"""Minimal schema contracts per format (presence checks only)."""

from __future__ import annotations

import pandas as pd

from multi_format_etl.load import LoadError

EXPECTED_COLUMNS: dict[str, list[str]] = {
    "csv": ["transaction_id", "account_id", "amount", "timestamp"],
    "json": ["transaction_id", "account_id", "amount"],
    "xml": ["customer_id", "full_name"],
    "logs": ["timestamp", "account", "type", "amount", "status"],
}


def check_columns(df: pd.DataFrame, source_format: str) -> None:
    """Raise LoadError if expected columns are missing. Unknown formats are skipped."""
    expected = EXPECTED_COLUMNS.get(source_format)
    if expected is None:
        return
    missing = [c for c in expected if c not in df.columns]
    if missing:
        raise LoadError(f"Missing expected columns [{source_format}]: {missing}")
