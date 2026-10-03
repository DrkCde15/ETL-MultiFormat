"""Disponibilização opcional: replica a camada gold no PostgreSQL.

Só é usado quando `DATABASE_URL` está definido (ver `scripts/load_postgres.py`
e o `docker-compose.yml`, lido por `podman compose` ou `docker compose`);
o pipeline de arquivos nunca depende deste módulo.
Carga em full refresh (TRUNCATE + INSERT), DDL derivado dos dtypes pandas e
identificadores validados por regex.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from pathlib import Path

import pandas as pd

from multi_format_etl.config import Settings

DEFAULT_SCHEMA = "gold"

_IDENTIFIER = re.compile(r"^[a-z][a-z0-9_]*$")


class DbError(RuntimeError):
    """Lançado quando a carga no PostgreSQL falha."""


def _quote(ident: str, kind: str = "identifier") -> str:
    """Valida um identificador snake_case e devolve entre aspas duplas."""
    if not _IDENTIFIER.match(ident):
        raise DbError(f"Invalid {kind}: {ident!r}")
    return f'"{ident}"'


def _column_ddl(dtype: object) -> str:
    """Mapeia um dtype do pandas para o tipo SQL equivalente no Postgres."""
    if pd.api.types.is_bool_dtype(dtype):
        return "BOOLEAN"
    if pd.api.types.is_integer_dtype(dtype):
        return "BIGINT"
    if pd.api.types.is_float_dtype(dtype):
        return "DOUBLE PRECISION"
    if pd.api.types.is_datetime64_any_dtype(dtype):
        return "TIMESTAMP"
    return "TEXT"


def _python_value(value: object) -> object:
    """Converte célula pandas/numpy para tipo nativo adaptável pelo psycopg."""
    if value is None or value is pd.NaT:
        return None
    if isinstance(value, float) and pd.isna(value):
        return None
    if isinstance(value, (datetime, date)):
        return value
    if hasattr(value, "item"):
        try:
            return value.item()
        except (AttributeError, ValueError):
            return value
    return value


def table_name(parquet_path: Path) -> str:
    """Nome da tabela Postgres para um parquet gold (`<fmt>_<arquivo>`)."""
    return f"{parquet_path.parent.name}_{parquet_path.stem}"


def create_table_sql(table: str, df: pd.DataFrame, schema: str = DEFAULT_SCHEMA) -> str:
    """SQL idempotente de CREATE SCHEMA + CREATE TABLE com colunas tipadas."""
    columns = ", ".join(
        f"{_quote(str(name))} {_column_ddl(dtype)}" for name, dtype in df.dtypes.items()
    )
    return (
        f"CREATE SCHEMA IF NOT EXISTS {_quote(schema)}; "
        f"CREATE TABLE IF NOT EXISTS {_quote(schema)}.{_quote(table)} ({columns})"
    )


def load_table(conn, table: str, df: pd.DataFrame, schema: str = DEFAULT_SCHEMA) -> int:
    """Cria schema/tabela se necessário e faz full refresh (TRUNCATE + INSERT)."""
    qualified = f"{_quote(schema)}.{_quote(table)}"
    columns = [_quote(str(c)) for c in df.columns]
    placeholders = ", ".join(["%s"] * len(columns))
    insert = f"INSERT INTO {qualified} ({', '.join(columns)}) VALUES ({placeholders})"
    rows = [tuple(_python_value(v) for v in row) for row in df.itertuples(index=False, name=None)]
    with conn.cursor() as cur:
        cur.execute(create_table_sql(table, df, schema))
        cur.execute(f"TRUNCATE TABLE {qualified}")
        if rows:
            cur.executemany(insert, rows)
    conn.commit()
    return len(rows)


def load_gold(settings: Settings, dsn: str) -> dict[str, int]:
    """Lê todos os parquets de `data/gold/` e carrega no Postgres (full refresh).

    Retorna {tabela: linhas_carregadas}. Falha de conexão, dependência
    ausente ou tabela problemática vira DbError.
    """
    paths = sorted(settings.gold_dir.glob("*/*.parquet"))
    if not paths:
        raise DbError(f"Nenhum parquet em {settings.gold_dir} — rode scripts/run_load.py antes")
    try:
        import psycopg
    except ImportError as exc:
        raise DbError("psycopg não instalado. Rode: uv pip install -e '.[dev]'") from exc
    try:
        conn = psycopg.connect(dsn)
    except Exception as exc:
        raise DbError(f"Conexão falhou: {exc}") from exc
    loaded: dict[str, int] = {}
    try:
        with conn:
            for path in paths:
                name = table_name(path)
                try:
                    loaded[name] = load_table(conn, name, pd.read_parquet(path))
                except DbError:
                    raise
                except Exception as exc:
                    raise DbError(f"Falha ao carregar {name}: {exc}") from exc
    except DbError:
        raise
    except Exception as exc:
        raise DbError(f"Carga no PostgreSQL falhou: {exc}") from exc
    finally:
        conn.close()
    return loaded


__all__ = ["DEFAULT_SCHEMA", "DbError", "create_table_sql", "load_gold", "load_table", "table_name"]
