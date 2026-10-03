"""Camada de transformação (estágio 1: padronização + limpeza mínima).

- standardize(): nomes de colunas + marcação de proveniência, sem regra de negócio.
- clean(): strip, conversão de tipos, remoção de linhas sem campos obrigatórios,
  dedup por chave — regras guiadas por valid.SPEC; agregação fica para um estágio futuro.
"""

from __future__ import annotations

import pandas as pd

from multi_format_etl.valid import SPEC


def standardize(df: pd.DataFrame, source_format: str, source_file: str) -> pd.DataFrame:
    """Normaliza nomes de colunas e marca proveniência (sem lógica de negócio ainda)."""
    out = df.copy()
    out.columns = [c.strip().lower() for c in out.columns]
    out["_source_format"] = source_format
    out["_source_file"] = source_file
    return out


def clean_with_stats(df: pd.DataFrame, source_format: str) -> tuple[pd.DataFrame, dict]:
    """Limpeza do estágio 1 guiada por SPEC: strip em strings, conversão de
    colunas numéricas/temporais, remoção de linhas sem obrigatórios, dedup por
    chave. Função pura; retorna (df_limpo, estatísticas de descarte)."""
    spec = SPEC.get(source_format, {})
    out = df.copy()
    for col in out.select_dtypes(include=["object", "str"]).columns:
        out[col] = out[col].str.strip()
    for col in spec.get("numeric", []):
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="raise")
    for col in spec.get("temporal", []):
        if col in out.columns:
            out[col] = pd.to_datetime(out[col], errors="raise")
    required = [c for c in spec.get("required", []) if c in out.columns]
    dropped_by_column: dict[str, int] = {}
    dropped_null = 0
    if required:
        for col in required:
            nulls = int(out[col].isna().sum())
            if nulls:
                dropped_by_column[col] = nulls
        mask = out[required].isna().any(axis=1)
        dropped_null = int(mask.sum())
        out = out[~mask]
    dropped_dup = 0
    key = spec.get("key", [])
    if key and all(c in out.columns for c in key):
        before = len(out)
        out = out.drop_duplicates(subset=key, keep="last")
        dropped_dup = before - len(out)
    out = out.reset_index(drop=True)
    stats = {
        "rows_in": len(df),
        "rows_out": len(out),
        "dropped_null_required": dropped_null,
        "dropped_duplicate_key": dropped_dup,
        "dropped_by_column": dropped_by_column,
    }
    return out, stats


def clean(df: pd.DataFrame, source_format: str) -> pd.DataFrame:
    """Variante de `clean_with_stats` sem as estatísticas de descarte."""
    out, _ = clean_with_stats(df, source_format)
    return out
