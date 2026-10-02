"""XML loader (legacy banking extract). Uses only the standard library."""

from __future__ import annotations

from pathlib import Path
from xml.etree import ElementTree as ET

import pandas as pd

from multi_format_etl.loaders.csv_loader import LoadError


def load_xml(path: Path, record_tag: str = "customer") -> pd.DataFrame:
    """Parse a simple record-per-element XML file into a DataFrame."""
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
