"""Tests: one loader per format + standardization contract."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from multi_format_etl.config import load_settings
from multi_format_etl.load import LoadError, load_csv, load_file, load_json, load_logs, load_xml
from multi_format_etl.transform import clean, standardize
from multi_format_etl.valid import CheckError, check_columns, check_quality


def _raw() -> Path:
    return load_settings().project_root / "data" / "raw"


def test_load_csv() -> None:
    """CSV sample loads with expected columns."""
    df = load_csv(_raw() / "csv" / "transactions.csv")
    assert len(df) == 5
    assert {"transaction_id", "account_id", "amount"} <= set(df.columns)


def test_load_json() -> None:
    """JSON sample loads (includes one null amount for future cleaning)."""
    df = load_json(_raw() / "json" / "transactions.json")
    assert len(df) == 4
    assert df["amount"].isna().sum() == 1


def test_load_xml() -> None:
    """XML legacy extract parses 3 customers."""
    df = load_xml(_raw() / "xml" / "customers.xml")
    assert len(df) == 3
    assert {"customer_id", "full_name"} <= set(df.columns)


def test_load_logs() -> None:
    """Log file parses 4 events with typed fields."""
    df = load_logs(_raw() / "logs" / "transactions.log")
    assert len(df) == 4
    assert {"timestamp", "account", "type", "amount", "status"} <= set(df.columns)


def test_load_missing_raises(tmp_path: Path) -> None:
    """Missing file fails fast."""
    with pytest.raises(LoadError, match="not found"):
        load_csv(tmp_path / "nope.csv")


def test_standardize_tags_provenance() -> None:
    """Standardize lowercases columns and tags source (no business rules)."""
    df = load_csv(_raw() / "csv" / "transactions.csv")
    out = standardize(df, "csv", "transactions.csv")
    assert "_source_format" in out.columns
    assert (out["_source_format"] == "csv").all()
    assert all(c == c.lower() for c in out.columns)


def test_check_columns_accepts_raw_samples() -> None:
    """Every raw sample satisfies its expected-columns contract."""
    check_columns(load_csv(_raw() / "csv" / "transactions.csv"), "csv")
    check_columns(load_json(_raw() / "json" / "transactions.json"), "json")
    check_columns(load_xml(_raw() / "xml" / "customers.xml"), "xml")
    check_columns(load_logs(_raw() / "logs" / "transactions.log"), "logs")


def test_check_columns_missing_raises() -> None:
    """Missing expected columns fail loudly with the gaps listed."""
    df = pd.DataFrame({"transaction_id": ["T1"]})
    with pytest.raises(LoadError, match="Missing expected columns"):
        check_columns(df, "csv")


def test_load_file_dispatches_by_suffix() -> None:
    """load_file picks the reader from the suffix and returns the format name."""
    fmt, df = load_file(_raw() / "csv" / "transactions.csv")
    assert fmt == "csv"
    assert len(df) == 5
    fmt, df = load_file(_raw() / "logs" / "transactions.log")
    assert fmt == "logs"
    assert len(df) == 4


def test_load_file_unsupported_suffix_raises(tmp_path: Path) -> None:
    """Unknown suffix fails loudly and lists the supported formats."""
    path = tmp_path / "data.yaml"
    path.write_text("x: 1", encoding="utf-8")
    with pytest.raises(LoadError, match="Unsupported format"):
        load_file(path)


def test_clean_drops_rows_missing_required() -> None:
    """The intentional null amount in the JSON fixture is removed by cleaning."""
    df = standardize(
        load_json(_raw() / "json" / "transactions.json"), "json", "transactions.json"
    )
    assert len(df) == 4
    out = clean(df, "json")
    assert len(out) == 3
    assert out["amount"].notna().all()


def test_clean_coerces_types() -> None:
    """Log amount becomes numeric and timestamp becomes datetime."""
    df = standardize(load_logs(_raw() / "logs" / "transactions.log"), "logs", "transactions.log")
    out = clean(df, "logs")
    assert pd.api.types.is_numeric_dtype(out["amount"])
    assert pd.api.types.is_datetime64_any_dtype(out["timestamp"])


def test_clean_dedupes_by_key() -> None:
    """Duplicate keys keep the last occurrence."""
    df = pd.DataFrame(
        {"transaction_id": ["T1", "T1"], "account_id": ["A1", "A1"], "amount": [1.0, 2.0]}
    )
    out = clean(df, "json")
    assert len(out) == 1
    assert out["amount"].iloc[0] == 2.0


def test_check_quality_passes_on_cleaned_fixtures() -> None:
    """Every fixture passes null/duplicate/type checks after cleaning."""
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
    """Nulls, duplicate keys and wrong types are all reported at once."""
    df = pd.DataFrame(
        {
            "transaction_id": ["T1", "T1"],
            "account_id": ["A1", None],
            "amount": ["not-a-number", 2.0],
        }
    )
    with pytest.raises(CheckError, match=r"null.*duplicate.*expected numeric"):
        check_quality(df, "json")
