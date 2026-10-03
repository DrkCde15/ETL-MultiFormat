"""Camada gold: agregados de negócio por formato, calculados a partir do curated.

Cada formato tem seu agregador (registro `AGGREGATORS`); formatos sem regra
caem num resumo genérico. As tabelas saem em `data/gold/<fmt>/<tabela>.parquet`.
"""

from __future__ import annotations

from collections.abc import Callable

import pandas as pd


def _summary(df: pd.DataFrame) -> pd.DataFrame:
    """Resumo genérico: contagem de linhas e colunas."""
    return pd.DataFrame(
        {
            "metric": ["rows", "columns"],
            "value": [len(df), len(df.columns)],
        }
    )


def _csv_aggregates(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Transações bancárias por status e por mês (taxa de fraude se existir)."""
    by_status = (
        df.groupby("transaction_status")
        .agg(
            transactions=("transaction_id", "size"),
            total_amount=("transaction_amount", "sum"),
            avg_amount=("transaction_amount", "mean"),
        )
        .reset_index()
    )
    out = {"by_status": by_status}
    if "transaction_date" in df.columns:
        monthly = df.assign(month=df["transaction_date"].dt.to_period("M").astype(str))
        metrics: dict[str, tuple[str, str]] = {
            "transactions": ("transaction_id", "size"),
            "total_amount": ("transaction_amount", "sum"),
        }
        if "fraud_flag" in monthly.columns:
            monthly = monthly.assign(
                is_fraud=(monthly["fraud_flag"].str.lower() == "yes").astype(int)
            )
            metrics["fraud_rate"] = ("is_fraud", "mean")
        out["by_month"] = monthly.groupby("month").agg(**metrics).reset_index()
    return out


def _json_aggregates(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Série PTAX por mês: pregões observados e mín/máx/média da venda.

    `datahora` já chega datetime do curated (SPEC json) — sem parsing
    manual, sem ambiguidade de dayfirst.
    """
    months = df["datahora"].dt.to_period("M").astype(str)
    by_month = (
        df.assign(month=months)
        .groupby("month")
        .agg(
            days=("datahora", "size"),
            venda_min=("cotacao_venda", "min"),
            venda_max=("cotacao_venda", "max"),
            venda_avg=("cotacao_venda", "mean"),
        )
        .reset_index()
    )
    return {"by_month": by_month}


def _xml_aggregates(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Clientes por agência (`branch_id`), quando o extrato a traz."""
    if "branch_id" in df.columns:
        by_branch = df.groupby("branch_id").agg(customers=("customer_id", "size")).reset_index()
        return {"by_branch": by_branch}
    return {"summary": _summary(df)}


def _logs_aggregates(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Eventos e volume transacionado por status e por tipo."""
    by_status = (
        df.groupby("status")
        .agg(events=("timestamp", "size"), total_amount=("amount", "sum"))
        .reset_index()
    )
    by_type = (
        df.groupby("type")
        .agg(events=("timestamp", "size"), total_amount=("amount", "sum"))
        .reset_index()
    )
    return {"by_status": by_status, "by_type": by_type}


AGGREGATORS: dict[str, Callable[[pd.DataFrame], dict[str, pd.DataFrame]]] = {
    "csv": _csv_aggregates,
    "json": _json_aggregates,
    "xml": _xml_aggregates,
    "logs": _logs_aggregates,
}


def aggregate(df: pd.DataFrame, source_format: str) -> dict[str, pd.DataFrame]:
    """Constrói as tabelas gold de um dataset curado.

    Retorna {nome_da_tabela: dataframe}; formatos sem agregador registrado
    caem num resumo genérico. Entrada deve ter passado por `check_quality`.
    """
    builder = AGGREGATORS.get(source_format)
    if builder is None:
        return {"summary": _summary(df)}
    return builder(df)


__all__ = ["AGGREGATORS", "aggregate"]
