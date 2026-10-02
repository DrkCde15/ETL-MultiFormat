"""CLI: load every raw format -> processed parquet (standardized, no cleaning yet).

Usage:
    python scripts/run_load.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from multi_format_etl.config import load_settings, setup_logging
from multi_format_etl.load import load_file
from multi_format_etl.transform import standardize
from multi_format_etl.valid import check_columns

logger = setup_logging()

SOURCES = [
    "csv/transactions.csv",
    "json/transactions.json",
    "xml/customers.xml",
    "logs/transactions.log",
]


def main() -> int:
    """Load + standardize + write processed parquet. Returns exit code."""
    settings = load_settings()
    settings.ensure_dirs()
    total = 0
    for rel in SOURCES:
        raw_path = settings.raw_dir / rel
        try:
            fmt, df = load_file(raw_path)
            df = standardize(df, fmt, raw_path.name)
            check_columns(df, fmt)
        except Exception as exc:
            logger.error("Load FAILED [%s] %s: %s", rel, raw_path, exc)
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
