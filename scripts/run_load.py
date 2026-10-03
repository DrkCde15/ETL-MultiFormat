"""CLI: carga -> processed -> curated -> gold, com relatório de qualidade.

Uso:
    python scripts/run_load.py
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from multi_format_etl.aggregate import aggregate
from multi_format_etl.config import Settings, load_settings, setup_logging
from multi_format_etl.load import load_file
from multi_format_etl.transform import clean_with_stats, standardize
from multi_format_etl.valid import check_columns, check_quality, write_report

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


def _run(settings: Settings, report: dict) -> int:
    """Executa as quatro camadas, preenchendo o relatório; retorna o exit code."""
    total = 0
    curated_total = 0
    gold_total = 0
    for rel in SOURCES:
        raw_path = settings.raw_dir / rel
        if not raw_path.exists():
            hint = FETCH_HINT.get(rel)
            suffix = f" — run `{hint}` first" if hint else ""
            logger.error("Missing raw source %s%s", raw_path, suffix)
            report["error"] = f"missing raw source: {rel}"
            return 1
        try:
            fmt, df = load_file(raw_path)
            processed = standardize(df, fmt, raw_path.name)
            check_columns(processed, fmt)
        except Exception as exc:
            logger.error("Load FAILED [%s] %s: %s", rel, raw_path, exc)
            report["error"] = f"load [{rel}]: {exc}"
            return 1
        processed_out = settings.processed_dir / fmt / "data.parquet"
        processed_out.parent.mkdir(parents=True, exist_ok=True)
        processed.to_parquet(processed_out, index=False)
        logger.info("Processed OK [%s] rows=%d -> %s", fmt, len(processed), processed_out)

        try:
            curated, clean_stats = clean_with_stats(processed, fmt)
        except Exception as exc:
            logger.error("Clean FAILED [%s] %s: %s", rel, raw_path, exc)
            report["error"] = f"clean [{rel}]: {exc}"
            return 1
        try:
            quality_checks = check_quality(curated, fmt)
        except Exception as exc:
            logger.error("Quality FAILED [%s] %s: %s", rel, raw_path, exc)
            report["error"] = f"quality [{rel}]: {exc}"
            return 1
        curated_out = settings.curated_dir / fmt / "data.parquet"
        curated_out.parent.mkdir(parents=True, exist_ok=True)
        curated.to_parquet(curated_out, index=False)
        logger.info("Curated OK [%s] rows=%d -> %s", fmt, len(curated), curated_out)

        try:
            gold_tables = aggregate(curated, fmt)
        except Exception as exc:
            logger.error("Gold FAILED [%s] %s: %s", rel, raw_path, exc)
            report["error"] = f"gold [{rel}]: {exc}"
            return 1
        for table_name, gold_df in gold_tables.items():
            gold_out = settings.gold_dir / fmt / f"{table_name}.parquet"
            gold_out.parent.mkdir(parents=True, exist_ok=True)
            gold_df.to_parquet(gold_out, index=False)
        logger.info("Gold OK [%s] tables=%d -> %s", fmt, len(gold_tables), settings.gold_dir / fmt)

        print(
            f"  - {fmt:<6} processed={len(processed):<4} curated={len(curated):<4} "
            f"gold={len(gold_tables)} -> {curated_out}"
        )
        report["formats"][fmt] = {
            "source_file": raw_path.name,
            "rows_processed": len(processed),
            "rows_curated": len(curated),
            "clean": clean_stats,
            "quality_checks": quality_checks,
            "gold_tables": sorted(gold_tables),
        }
        total += len(processed)
        curated_total += len(curated)
        gold_total += len(gold_tables)
    report["totals"] = {
        "rows_processed": total,
        "rows_curated": curated_total,
        "gold_tables": gold_total,
    }
    logger.info(
        "Load DONE: %d rows processed, %d rows curated, %d gold tables",
        total,
        curated_total,
        gold_total,
    )
    return 0


def main() -> int:
    """Executa a carga completa e grava o relatório de qualidade."""
    settings = load_settings()
    settings.ensure_dirs()
    report = {
        "pipeline": "multi-format-etl",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "formats": {},
        "totals": {},
        "status": "running",
    }
    code = _run(settings, report)
    report["status"] = "passed" if code == 0 else "failed"
    out = write_report(report, settings.quality_dir / "quality_report.json")
    logger.info("Quality report [%s] -> %s", report["status"], out)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
