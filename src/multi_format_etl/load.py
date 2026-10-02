"""Loaders for every supported raw format, in one module.

Suffix -> (format name, reader) registry: to add a format, write one
function and register it in FORMAT_BY_SUFFIX.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from xml.etree import ElementTree as ET

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


def load_json(path: Path) -> pd.DataFrame:
    """Load a JSON array file (flat or nested-one-level)."""
    if not path.exists():
        raise LoadError(f"JSON file not found: {path}")
    try:
        return pd.read_json(path)
    except Exception as exc:
        raise LoadError(f"Failed to read JSON {path}: {exc}") from exc


def load_xml(path: Path, record_tag: str = "customer") -> pd.DataFrame:
    """Parse a simple record-per-element XML file into a DataFrame (stdlib only)."""
    if not path.exists():
        raise LoadError(f"XML file not found: {path}")
    try:
        root = ET.parse(path).getroot()
    except Exception as exc:
        raise LoadError(f"Failed to parse XML {path}: {exc}") from exc
    rows: list[dict] = []
    for record in root.findall(f".//{record_tag}"):
        row = {child.tag: (child.text or "").strip() for child in record}
        if row:
            rows.append(row)
    if not rows:
        raise LoadError(f"No <{record_tag}> records found in {path}")
    return pd.DataFrame(rows)


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
    """Load a transaction log file (pipe-separated, one event per line)."""
    if not path.exists():
        raise LoadError(f"Log file not found: {path}")
    try:
        lines = [ln for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    except Exception as exc:
        raise LoadError(f"Failed to read log {path}: {exc}") from exc
    if not lines:
        raise LoadError(f"Log file is empty: {path}")
    return pd.DataFrame([parse_log_line(ln) for ln in lines])


FORMAT_BY_SUFFIX: dict[str, tuple[str, Callable[[Path], pd.DataFrame]]] = {
    ".csv": ("csv", load_csv),
    ".json": ("json", load_json),
    ".xml": ("xml", load_xml),
    ".log": ("logs", load_logs),
}


def load_file(path: Path) -> tuple[str, pd.DataFrame]:
    """Detect the format by suffix and load. Returns (format_name, dataframe)."""
    entry = FORMAT_BY_SUFFIX.get(path.suffix.lower())
    if entry is None:
        supported = ", ".join(sorted(FORMAT_BY_SUFFIX))
        raise LoadError(f"Unsupported format '{path.suffix}' for {path}. Supported: {supported}")
    fmt, reader = entry
    return fmt, reader(path)


__all__ = [
    "FORMAT_BY_SUFFIX",
    "LoadError",
    "load_csv",
    "load_file",
    "load_json",
    "load_logs",
    "load_xml",
    "parse_log_line",
]
