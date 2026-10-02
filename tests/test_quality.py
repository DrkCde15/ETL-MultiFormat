"""Testes: regras de negócio de qualidade, estatísticas de descarte e relatório."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from multi_format_etl.config import load_settings
from multi_format_etl.load import load_json
from multi_format_etl.transform import clean, clean_with_stats, standardize
from multi_format_etl.valid import CheckError, check_quality, write_report


def _json_curated() -> pd.DataFrame:
    """Fixture JSON no estado curated (standardize + clean)."""
    path = load_settings().project_root / "data" / "raw" / "json" / "transactions.json"
    return clean(standardize(load_json(path), "json", path.name), "json")


def test_range_violation_raises() -> None:
    """Valor negativo viola a faixa min do SPEC (json: valor >= 0)."""
    df = _json_curated()
    df.loc[0, "valor"] = -1.0
    with pytest.raises(CheckError, match="below min 0"):
        check_quality(df, "json")


def test_enum_violation_raises() -> None:
    """Status fora do conjunto permitido é reportado (csv: transaction_status)."""
    df = pd.DataFrame(
        {
            "transaction_id": ["T1", "T2"],
            "transaction_date": pd.to_datetime(["2024-06-01", "2024-06-02"]),
            "transaction_amount": [10.0, 20.0],
            "transaction_status": ["Success", "bogus"],
        }
    )
    with pytest.raises(CheckError, match="outside the allowed set"):
        check_quality(df, "csv")


def test_freshness_violation_raises() -> None:
    """Data no futuro viola o frescor (csv: transaction_date)."""
    df = pd.DataFrame(
        {
            "transaction_id": ["T1"],
            "transaction_date": [pd.Timestamp.now() + pd.Timedelta(days=1)],
            "transaction_amount": [10.0],
            "transaction_status": ["Success"],
        }
    )
    with pytest.raises(CheckError, match="future value"):
        check_quality(df, "csv")


def test_check_quality_returns_executed_checks() -> None:
    """A lista de checks executados traz as categorias rodadas por formato."""
    executed = check_quality(_json_curated(), "json")
    assert "null:data" in executed
    assert "null:valor" in executed
    assert "key:data" in executed
    assert "type:valor" in executed
    assert "range:valor" in executed
    assert check_quality(pd.DataFrame({"a": [1]}), "desconhecido") == []


def test_clean_with_stats_counts_dropped_nulls() -> None:
    """A fixture JSON registra o valor nulo removido, por coluna."""
    path = load_settings().project_root / "data" / "raw" / "json" / "transactions.json"
    df = standardize(load_json(path), "json", path.name)
    out, stats = clean_with_stats(df, "json")
    assert stats["rows_in"] == 4
    assert stats["rows_out"] == 3
    assert stats["dropped_null_required"] == 1
    assert stats["dropped_by_column"] == {"valor": 1}
    assert stats["dropped_duplicate_key"] == 0


def test_clean_with_stats_counts_dropped_duplicates() -> None:
    """Chaves duplicadas são contadas à parte dos nulos."""
    df = pd.DataFrame(
        {
            "data": ["01/06/2024", "01/06/2024", "02/06/2024"],
            "valor": [5.1, 5.2, 5.3],
        }
    )
    out, stats = clean_with_stats(df, "json")
    assert len(out) == 2
    assert stats["dropped_null_required"] == 0
    assert stats["dropped_duplicate_key"] == 1


def test_clean_matches_clean_with_stats() -> None:
    """`clean` devolve exatamente o dataframe de `clean_with_stats`."""
    path = load_settings().project_root / "data" / "raw" / "json" / "transactions.json"
    df = standardize(load_json(path), "json", path.name)
    out, _ = clean_with_stats(df, "json")
    pd.testing.assert_frame_equal(clean(df, "json"), out)


def test_write_report(tmp_path: Path) -> None:
    """O relatório é gravado como JSON legível com status e totais."""
    report = {
        "pipeline": "multi-format-etl",
        "status": "passed",
        "totals": {"rows_processed": 10, "rows_curated": 9},
    }
    out = write_report(report, tmp_path / "quality_report.json")
    loaded = json.loads(out.read_text(encoding="utf-8"))
    assert loaded["status"] == "passed"
    assert loaded["totals"]["rows_curated"] == 9
    assert write_report.__doc__ is not None
