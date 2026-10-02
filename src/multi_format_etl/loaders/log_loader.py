"""Log loader (semi-structured transaction logs, one event per line).

Expected line format (pipe-separated):
    2024-06-01T10:00:00|account=A00001|type=deposit|amount=100.00|status=completed
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from multi_format_etl.loaders.csv_loader import LoadError


def parse_log_line(line: str) -> dict:
    """Parse one log line into a dict. Raises LoadError on malformed lines."""
    parts = line.strip().split("|")
    if len(parts) < 2:
        raise LoadError(f"Malformed log line: {line!r}")
    record: dict[str, str] = {"timestamp": parts[0]}
    for part in parts[1:]:
        if "=" not in part:
            raise LoadError(f"Malformed log field {part!r} in line: {line!r}")
        key, value = part.split("=", 1)
        record[key.strip()] = value.strip()
    return record


def load_logs(path: Path) -> pd.DataFrame:
    """Load a transaction log file into a DataFrame."""
    if not path.exists():
        raise LoadError(f"Log file not found: {path}")
    try:
        lines = [ln for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    except Exception as exc:
        raise LoadError(f"Failed to read log {path}: {exc}") from exc
    if not lines:
        raise LoadError(f"Log file is empty: {path}")
    return pd.DataFrame([parse_log_line(ln) for ln in lines])
