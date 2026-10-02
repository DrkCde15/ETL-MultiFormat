"""Testes: camada gold (agregados por formato) — cálculo puro, offline."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pandas as pd

from multi_format_etl.aggregate import aggregate
from multi_format_etl.config import load_settings
from multi_format_etl.load import load_csv, load_json, load_logs, load_xml
from multi_format_etl.transform import clean, standardize


def _curated(rel: str, fmt: str, loader: Callable[[Path], pd.DataFrame]) -> pd.DataFrame:
    """Reproduz o estado curated de uma fixture (standardize + clean)."""
    path = load_settings().project_root / "data" / "raw" / rel
    return clean(standardize(loader(path), fmt, path.name), fmt)


def test_csv_aggregates() -> None:
    """CSV: tabelas by_status e by_month; contagens somam o total de linhas."""
    df = _curated("csv/transactions.csv", "csv", load_csv)
    tables = aggregate(df, "csv")
    assert set(tables) == {"by_status", "by_month"}
    by_status = tables["by_status"]
    assert {"transaction_status", "transactions", "total_amount", "avg_amount"} <= set(
        by_status.columns
    )
    assert int(by_status["transactions"].sum()) == len(df)
    assert int(tables["by_month"]["transactions"].sum()) == len(df)


def test_json_aggregates() -> None:
    """JSON (BCB): by_month com dias observados e min <= max do valor."""
    df = _curated("json/transactions.json", "json", load_json)
    tables = aggregate(df, "json")
    assert set(tables) == {"by_month"}
    by_month = tables["by_month"]
    assert int(by_month["days"].sum()) == len(df)
    assert (by_month["valor_min"] <= by_month["valor_max"]).all()
    assert {"valor_min", "valor_max", "valor_avg"} <= set(by_month.columns)


def test_xml_aggregates() -> None:
    """XML: clientes agrupados por agência (branch_id)."""
    df = _curated("xml/customers.xml", "xml", load_xml)
    tables = aggregate(df, "xml")
    assert set(tables) == {"by_branch"}
    assert int(tables["by_branch"]["customers"].sum()) == len(df)


def test_logs_aggregates() -> None:
    """Logs: eventos por status e por tipo somam o total de eventos."""
    df = _curated("logs/transactions.log", "logs", load_logs)
    tables = aggregate(df, "logs")
    assert set(tables) == {"by_status", "by_type"}
    assert int(tables["by_status"]["events"].sum()) == len(df)
    assert int(tables["by_type"]["events"].sum()) == len(df)


def test_unknown_format_falls_back_to_summary() -> None:
    """Formato sem agregador registrado cai no resumo genérico."""
    df = pd.DataFrame({"a": [1, 2, 3]})
    tables = aggregate(df, "parquet")
    assert set(tables) == {"summary"}
    rows = tables["summary"].set_index("metric")["value"]
    assert int(rows["rows"]) == 3
    assert int(rows["columns"]) == 1
