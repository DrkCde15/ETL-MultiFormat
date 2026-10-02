"""CLI: carrega todo formato bruto -> parquet processado (padronizado, sem limpeza ainda).

Uso:
    python scripts/run_load.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from multi_format_etl.aggregate import aggregate
from multi_format_etl.config import load_settings, setup_logging
from multi_format_etl.load import load_file
from multi_format_etl.transform import clean, standardize
from multi_format_etl.valid import check_columns, check_quality

logger = setup_logging()

# csv/json vêm das APIs (faça o fetch antes); xml/logs não têm API pública
# equivalente e ficam nas fixtures sintéticas versionadas.
SOURCES = [
    "csv/Banking_Transactions_USA_2023_2024.csv",
    "json/bcb_sgs_1.json",
    "xml/customers.xml",
    "logs/transactions.log",
]

FETCH_HINT = {
    "csv/Banking_Transactions_USA_2023_2024.csv": "python scripts/fetch_kaggle.py",
    "json/bcb_sgs_1.json": "python scripts/fetch_json.py",
}


def main() -> int:
    """Carga -> processed -> curated (limpo + verificado) -> gold (agregados)."""
    settings = load_settings()
    settings.ensure_dirs()
    total = 0
    curated_total = 0
    gold_total = 0
    for rel in SOURCES:
        raw_path = settings.raw_dir / rel
        if not raw_path.exists():
            hint = FETCH_HINT.get(rel)
            suffix = f" — run `{hint}` first" if hint else ""
            logger.error("Missing raw source %s%s", raw_path, suffix)
            return 1
        try:
            fmt, df = load_file(raw_path)
            processed = standardize(df, fmt, raw_path.name)
            check_columns(processed, fmt)
        except Exception as exc:
            logger.error("Load FAILED [%s] %s: %s", rel, raw_path, exc)
            return 1
        processed_out = settings.processed_dir / fmt / "data.parquet"
        processed_out.parent.mkdir(parents=True, exist_ok=True)
        processed.to_parquet(processed_out, index=False)
        logger.info("Processed OK [%s] rows=%d -> %s", fmt, len(processed), processed_out)

        try:
            curated = clean(processed, fmt)
            check_quality(curated, fmt)
        except Exception as exc:
            logger.error("Clean FAILED [%s] %s: %s", rel, raw_path, exc)
            return 1
        curated_out = settings.curated_dir / fmt / "data.parquet"
        curated_out.parent.mkdir(parents=True, exist_ok=True)
        curated.to_parquet(curated_out, index=False)
        logger.info("Curated OK [%s] rows=%d -> %s", fmt, len(curated), curated_out)

        try:
            gold_tables = aggregate(curated, fmt)
        except Exception as exc:
            logger.error("Gold FAILED [%s] %s: %s", rel, raw_path, exc)
            return 1
        for table_name, gold_df in gold_tables.items():
            gold_out = settings.gold_dir / fmt / f"{table_name}.parquet"
            gold_out.parent.mkdir(parents=True, exist_ok=True)
            gold_df.to_parquet(gold_out, index=False)
        logger.info(
            "Gold OK [%s] tables=%d -> %s", fmt, len(gold_tables), settings.gold_dir / fmt
        )

        print(
            f"  - {fmt:<6} processed={len(processed):<4} curated={len(curated):<4} "
            f"gold={len(gold_tables)} -> {curated_out}"
        )
        total += len(processed)
        curated_total += len(curated)
        gold_total += len(gold_tables)
    logger.info(
        "Load DONE: %d rows processed, %d rows curated, %d gold tables",
        total,
        curated_total,
        gold_total,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
