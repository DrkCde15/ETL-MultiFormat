"""Testes: camada Postgres opcional (SQL, identificadores, tipos) — sem banco."""

from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from multi_format_etl.config import Settings
from multi_format_etl.db import (
    DbError,
    _column_ddl,
    _python_value,
    _quote,
    create_table_sql,
    load_gold,
    table_name,
)


def test_quote_accepts_snake_case() -> None:
    """Identificadores válidos saem entre aspas duplas."""
    assert _quote("csv_by_status") == '"csv_by_status"'
    assert _quote("gold", "schema") == '"gold"'


@pytest.mark.parametrize("bad", ["Bad-Name", "drop table x", "a b", "1abc", 'x"y', "UPPER"])
def test_quote_rejects_bad_identifiers(bad: str) -> None:
    """Identificador fora do padrão snake_case falha com DbError."""
    with pytest.raises(DbError, match="Invalid"):
        _quote(bad)


def test_column_ddl_maps_pandas_types() -> None:
    """dtypes pandas viram tipos SQL do Postgres."""
    assert _column_ddl(np.dtype("int64")) == "BIGINT"
    assert _column_ddl(np.dtype("float64")) == "DOUBLE PRECISION"
    assert _column_ddl(np.dtype("datetime64[ns]")) == "TIMESTAMP"
    assert _column_ddl(np.dtype("bool")) == "BOOLEAN"
    assert _column_ddl(np.dtype("O")) == "TEXT"


def test_create_table_sql_includes_schema_and_columns() -> None:
    """DDL idempotente cria schema e tabela com as colunas tipadas."""
    df = pd.DataFrame(
        {
            "events": [1],
            "total": [1.5],
            "when": pd.to_datetime(["2024-01-01"]),
            "label": ["ok"],
        }
    )
    sql = create_table_sql("logs_by_status", df)
    assert 'CREATE SCHEMA IF NOT EXISTS "gold"' in sql
    assert '"logs_by_status"' in sql
    assert '"events" BIGINT' in sql
    assert '"total" DOUBLE PRECISION' in sql
    assert '"when" TIMESTAMP' in sql
    assert '"label" TEXT' in sql


def test_python_value_converts_scalars() -> None:
    """Numpy vira nativo, nulos viram None, datetime passa adiante."""
    assert _python_value(np.int64(7)) == 7
    assert isinstance(_python_value(np.int64(7)), int)
    assert _python_value(np.float64(1.5)) == 1.5
    assert _python_value(np.float64("nan")) is None
    assert _python_value(pd.NaT) is None
    assert _python_value(None) is None
    assert _python_value("texto") == "texto"
    ts = pd.Timestamp("2024-06-01T10:00:00")
    assert _python_value(ts) is ts


def test_table_name_from_path() -> None:
    """Tabela gold recebe o padrão <fmt>_<arquivo parquet>."""
    assert table_name(Path("/x/gold/csv/by_status.parquet")) == "csv_by_status"


def test_load_gold_without_parquets_raises(tmp_path: Path) -> None:
    """Sem parquets em gold o erro vem antes de tentar conexão."""
    settings = Settings(
        project_root=tmp_path,
        raw_dir=tmp_path / "raw",
        processed_dir=tmp_path / "processed",
        curated_dir=tmp_path / "curated",
        gold_dir=tmp_path / "gold",
        quality_dir=tmp_path / "quality",
        log_level="INFO",
    )
    with pytest.raises(DbError, match="Nenhum parquet"):
        load_gold(settings, "postgresql://invalid-host:1/db")


def test_load_gold_roundtrip(tmp_path: Path) -> None:
    """Integração ao vivo: parquet gold criado no teste carrega e bate com COUNT(*).

    Hermético: não depende de `run_load` ter rodado (o CI nasce sem
    data/gold, que é gitignored). A tabela de teste é removida no final.
    """
    dsn = os.getenv("DATABASE_URL")
    if not dsn:
        pytest.skip("DATABASE_URL não definido (camada Postgres opcional)")

    gold_subdir = tmp_path / "gold" / "csv"
    gold_subdir.mkdir(parents=True)
    pd.DataFrame({"status": ["Success", "Failed"], "transacoes": [2, 1]}).to_parquet(
        gold_subdir / "ci_roundtrip.parquet", index=False
    )
    settings = Settings(
        project_root=tmp_path,
        raw_dir=tmp_path / "raw",
        processed_dir=tmp_path / "processed",
        curated_dir=tmp_path / "curated",
        gold_dir=tmp_path / "gold",
        quality_dir=tmp_path / "quality",
        log_level="INFO",
    )
    import psycopg

    try:
        loaded = load_gold(settings, dsn)
        assert loaded == {"csv_ci_roundtrip": 2}
        with psycopg.connect(dsn) as conn, conn.cursor() as cur:
            cur.execute('SELECT COUNT(*) FROM "gold"."csv_ci_roundtrip"')
            assert cur.fetchone()[0] == 2
    finally:
        with psycopg.connect(dsn) as conn, conn.cursor() as cur:
            cur.execute('DROP TABLE IF EXISTS "gold"."csv_ci_roundtrip"')
