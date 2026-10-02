"""CLI: load every raw format -> processed parquet (standardized, no cleaning yet).

Usage:
    python scripts/run_load.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from multi_format_etl.config import load_settings, setup_logging
from multi_format_etl.loaders import load_csv, load_json, load_logs, load_xml
from multi_format_etl.transformation import standardize

logger = setup_logging()

SOURCES = [
    ("csv", "csv/transactions.csv", load_csv),
    ("json", "json/transactions.json", load_json),
    ("xml", "xml/customers.xml", load_xml),
    ("logs", "logs/transactions.log", load_logs),
]


def main() -> int:
    """Load + standardize + write processed parquet. Returns exit code."""
    settings = load_settings()
    settings.ensure_dirs()
    total = 0
    for fmt, rel, loader in SOURCES:
        raw_path = settings.raw_dir / rel
        try:
            df = standardize(loader(raw_path), fmt, raw_path.name)
        except Exception as exc:
            logger.error("Load FAILED [%s] %s: %s", fmt, raw_path, exc)
            return 1
        out = settings.processed_dir / fmt / "data.parquet"
        out.parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(out, index=False)
        logger.info("Processed OK [%s] rows=%d -> %s", fmt, len(df), out)
        print(f"  - {fmt:<6} rows={len(df):<4} -> {out}")
        total += len(df)
    logger.info("Load DONE: %d rows total", total)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
