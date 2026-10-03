"""Testes: loaders + contratos para fixtures (offline) e fontes reais baixadas."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from multi_format_etl.config import load_settings
from multi_format_etl.load import LoadError, load_csv, load_file, load_json, load_logs, load_xml
from multi_format_etl.transform import clean, standardize
from multi_format_etl.valid import CheckError, check_columns, check_quality


def _raw() -> Path:
    """Retorna o diretório de dados brutos do projeto (fixtures + downloads)."""
    return load_settings().project_root / "data" / "raw"


def test_load_csv() -> None:
    """A fixture CSV espelha o schema real do Kaggle (5 linhas, 20 colunas)."""
    df = load_csv(_raw() / "csv" / "transactions.csv")
    assert len(df) == 5
    lowered = {c.lower() for c in df.columns}
    assert {"transaction_id", "transaction_date", "transaction_amount"} <= lowered


def test_load_json() -> None:
    """A fixture JSON espelha o envelope cru do PTAX (camelCase, 1 venda nula)."""
    df = load_json(_raw() / "json" / "transactions.json")
    assert len(df) == 4
    assert df["cotacaoVenda"].isna().sum() == 1


def test_load_xml() -> None:
    """O extrato legado em XML analisa 3 clientes."""
    df = load_xml(_raw() / "xml" / "customers.xml")
    assert len(df) == 3
    assert {"customer_id", "full_name"} <= set(df.columns)


def test_load_logs() -> None:
    """O arquivo de log analisa 4 eventos com campos tipados."""
    df = load_logs(_raw() / "logs" / "transactions.log")
    assert len(df) == 4
    assert {"timestamp", "account", "type", "amount", "status"} <= set(df.columns)


def test_load_missing_raises(tmp_path: Path) -> None:
    """Arquivo ausente falha rápido."""
    with pytest.raises(LoadError, match="not found"):
        load_csv(tmp_path / "nope.csv")


def test_standardize_tags_provenance() -> None:
    """Padronizar deixa colunas minúsculas e marca a origem (sem regra de negócio)."""
    df = load_csv(_raw() / "csv" / "transactions.csv")
    out = standardize(df, "csv", "transactions.csv")
    assert "_source_format" in out.columns
    assert (out["_source_format"] == "csv").all()
    assert all(c == c.lower() for c in out.columns)


def test_check_columns_accepts_raw_samples() -> None:
    """Toda fixture satisfaz o contrato de colunas esperadas após standardize."""
    cases = [
        ("csv", "csv/transactions.csv", load_csv),
        ("json", "json/transactions.json", load_json),
        ("xml", "xml/customers.xml", load_xml),
        ("logs", "logs/transactions.log", load_logs),
    ]
    for fmt, rel, loader in cases:
        df = standardize(loader(_raw() / rel), fmt, Path(rel).name)
        check_columns(df, fmt)


def test_check_columns_missing_raises() -> None:
    """Colunas esperadas ausentes falham de forma explícita listando as lacunas."""
    df = pd.DataFrame({"transaction_id": ["T1"]})
    with pytest.raises(LoadError, match="Missing expected columns"):
        check_columns(df, "csv")


def test_load_file_dispatches_by_suffix() -> None:
    """load_file escolhe o leitor pelo sufixo e retorna o nome do formato."""
    fmt, df = load_file(_raw() / "csv" / "transactions.csv")
    assert fmt == "csv"
    assert len(df) == 5
    fmt, df = load_file(_raw() / "logs" / "transactions.log")
    assert fmt == "logs"
    assert len(df) == 4


def test_load_file_unsupported_suffix_raises(tmp_path: Path) -> None:
    """Sufixo desconhecido falha listando os formatos suportados."""
    path = tmp_path / "data.yaml"
    path.write_text("x: 1", encoding="utf-8")
    with pytest.raises(LoadError, match="Unsupported format"):
        load_file(path)


def test_clean_drops_rows_missing_required() -> None:
    """A venda nula intencional da fixture JSON é removida pela limpeza."""
    df = standardize(load_json(_raw() / "json" / "transactions.json"), "json", "transactions.json")
    assert {"datahora", "cotacao_compra", "cotacao_venda"} <= set(df.columns)
    assert len(df) == 4
    out = clean(df, "json")
    assert len(out) == 3
    assert out["cotacao_venda"].notna().all()


def test_clean_coerces_types() -> None:
    """amount do log vira numérico e timestamp vira datetime."""
    df = standardize(load_logs(_raw() / "logs" / "transactions.log"), "logs", "transactions.log")
    out = clean(df, "logs")
    assert pd.api.types.is_numeric_dtype(out["amount"])
    assert pd.api.types.is_datetime64_any_dtype(out["timestamp"])


def test_clean_coerces_csv_types() -> None:
    """Fixture CSV: transaction_date vira datetime, amount numérico."""
    df = standardize(load_csv(_raw() / "csv" / "transactions.csv"), "csv", "transactions.csv")
    out = clean(df, "csv")
    assert pd.api.types.is_datetime64_any_dtype(out["transaction_date"])
    assert pd.api.types.is_numeric_dtype(out["transaction_amount"])


def test_clean_dedupes_by_key() -> None:
    """Chaves duplicadas mantêm a última ocorrência (chave json: datahora)."""
    df = pd.DataFrame(
        {
            "datahora": ["2024-06-03 13:07:12", "2024-06-03 13:07:12"],
            "cotacao_venda": [5.1, 5.2],
        }
    )
    out = clean(df, "json")
    assert len(out) == 1
    assert out["cotacao_venda"].iloc[0] == 5.2


def test_check_quality_passes_on_cleaned_fixtures() -> None:
    """Toda fixture passa nos checks de nulo/duplicado/tipo após a limpeza."""
    cases = [
        ("csv", "csv/transactions.csv", load_csv),
        ("json", "json/transactions.json", load_json),
        ("xml", "xml/customers.xml", load_xml),
        ("logs", "logs/transactions.log", load_logs),
    ]
    for fmt, rel, loader in cases:
        df = clean(standardize(loader(_raw() / rel), fmt, Path(rel).name), fmt)
        check_quality(df, fmt)


def test_check_quality_reports_every_problem() -> None:
    """Nulos, chaves duplicadas e tipos errados são reportados de uma vez."""
    df = pd.DataFrame(
        {
            "datahora": ["2024-06-01 13:07:12", "2024-06-01 13:07:12", None],
            "cotacao_venda": ["not-a-number", 2.0, 3.0],
        }
    )
    with pytest.raises(CheckError, match=r"null.*duplicate.*expected numeric"):
        check_quality(df, "json")


REAL_SOURCES = [
    ("csv/Banking_Transactions_USA_2023_2024.csv", "csv", load_csv),
    ("json/bcb_ptax_usd.json", "json", load_json),
]


@pytest.mark.parametrize("rel,fmt,loader", REAL_SOURCES, ids=["csv-kaggle", "json-ptax"])
def test_real_source_passes_contract(rel: str, fmt: str, loader) -> None:
    """Fontes reais das APIs satisfazem colunas + qualidade ponta a ponta.

    Pulado em um clone novo até os scripts de fetch rodarem (os downloads
    em raw são gitignorados).
    """
    path = _raw() / rel
    if not path.exists():
        pytest.skip(f"{rel} missing — run the fetch scripts first")
    df = standardize(loader(path), fmt, path.name)
    check_columns(df, fmt)
    curated = clean(df, fmt)
    assert len(curated) > 0
    check_quality(curated, fmt)
