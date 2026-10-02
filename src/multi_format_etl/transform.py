"""Transformation layer (stage 1: standardization + minimal cleaning).

- standardize(): column names + provenance tags, no business rules.
- clean(): strip, type coercion, drop rows missing required fields,
  dedup by key — rules driven by valid.SPEC, aggregation belongs to a future stage.
"""

from __future__ import annotations

import pandas as pd

from multi_format_etl.valid import SPEC


def standardize(df: pd.DataFrame, source_format: str, source_file: str) -> pd.DataFrame:
    """Normalize column names and tag provenance (no business logic yet)."""
    out = df.copy()
    out.columns = [c.strip().lower() for c in out.columns]
    out["_source_format"] = source_format
    out["_source_file"] = source_file
    return out


def clean(df: pd.DataFrame, source_format: str) -> pd.DataFrame:
    """Stage-1 cleaning driven by SPEC: strip strings, coerce numeric/temporal
    columns, drop rows missing required fields, dedup by key. Pure function."""
    spec = SPEC.get(source_format, {})
    out = df.copy()
    for col in out.select_dtypes(include=["object", "str"]).columns:
        out[col] = out[col].str.strip()
    for col in spec.get("numeric", []):
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="raise")
    for col in spec.get("temporal", []):
        if col in out.columns:
            out[col] = pd.to_datetime(out[col], errors="raise")
    required = [c for c in spec.get("required", []) if c in out.columns]
    if required:
        out = out.dropna(subset=required)
    key = spec.get("key", [])
    if key and all(c in out.columns for c in key):
        out = out.drop_duplicates(subset=key, keep="last")
    return out.reset_index(drop=True)
