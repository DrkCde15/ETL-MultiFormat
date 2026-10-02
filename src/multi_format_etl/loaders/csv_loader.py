"""CSV loader (structured transactions extract)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd


class LoadError(RuntimeError):
    """Raised when a source file cannot be loaded."""


def load_csv(path: Path) -> pd.DataFrame:
    """Load a CSV file. Raises LoadError on missing/unreadable file."""
    if not path.exists():
        raise LoadError(f"CSV file not found: {path}")
    try:
        return pd.read_csv(path)
    except Exception as exc:
        raise LoadError(f"Failed to read CSV {path}: {exc}") from exc
