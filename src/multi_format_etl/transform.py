"""Minimal transformation layer (stage 1: standardization only).

Full cleaning (nulls, dedup, typing, aggregation) belongs to a future stage.
Here we only: strip column names, add _source_format, keep row counts.
"""

from __future__ import annotations

import pandas as pd


def standardize(df: pd.DataFrame, source_format: str, source_file: str) -> pd.DataFrame:
    """Normalize column names and tag provenance (no business logic yet)."""
    out = df.copy()
    out.columns = [c.strip().lower() for c in out.columns]
    out["_source_format"] = source_format
    out["_source_file"] = source_file
    return out
