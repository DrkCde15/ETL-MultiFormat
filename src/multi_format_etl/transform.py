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


def clean(df: pd.DataFrame, source_format: str) -> pd.DataFrame:
    """Limpeza do estágio 1 guiada por SPEC: strip em strings, conversão de
    colunas numéricas/temporais, remoção de linhas sem obrigatórios, dedup por
    chave. Função pura."""
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
    if required:
        out = out.dropna(subset=required)
    key = spec.get("key", [])
    if key and all(c in out.columns for c in key):
        out = out.drop_duplicates(subset=key, keep="last")
    return out.reset_index(drop=True)
