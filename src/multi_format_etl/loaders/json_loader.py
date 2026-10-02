"""JSON loader (nested API-like payloads)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from multi_format_etl.loaders.csv_loader import LoadError


def load_json(path: Path) -> pd.DataFrame:
    """Load a JSON array file (flat or nested-one-level)."""
    if not path.exists():
        raise LoadError(f"JSON file not found: {path}")
    try:
        return pd.read_json(path)
    except Exception as exc:
        raise LoadError(f"Failed to read JSON {path}: {exc}") from exc
