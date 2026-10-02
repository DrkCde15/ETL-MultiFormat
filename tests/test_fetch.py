"""Testes: helpers de fetch (montagem de URL, janela de datas) — sem rede."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from multi_format_etl.fetch import (
    DEFAULT_WINDOW_DAYS,
    FetchError,
    resolve_window,
    sgs_url,
)


def test_sgs_url_defaults_to_json() -> None:
    """O endpoint SGS pede o formato JSON para o código de série informado."""
    assert sgs_url(1) == (
        "https://api.bcb.gov.br/dados/serie/bcdata.sgs.1/dados?formato=json"
    )


def test_sgs_url_with_date_range() -> None:
    """Intervalo opcional dd/mm/yyyy é passado como query params."""
    url = sgs_url(11, start="01/06/2024", end="30/06/2024")
    assert "dataInicial=01/06/2024" in url
    assert "dataFinal=30/06/2024" in url


def test_resolve_window_defaults_to_90_days() -> None:
    """Requisições sem datas recebem os últimos 90 dias (limite do BCB p/ séries diárias)."""
    start, end = resolve_window(None, None)
    assert start != end
    fmt = "%d/%m/%Y"
    delta = datetime.strptime(end, fmt) - datetime.strptime(start, fmt)
    assert delta.days == DEFAULT_WINDOW_DAYS


def test_resolve_window_fills_missing_start_from_end() -> None:
    """Pedido só com fim começa DEFAULT_WINDOW_DAYS antes."""
    start, end = resolve_window(None, "30/06/2024")
    assert end == "30/06/2024"
    expected = (
        datetime.strptime("30/06/2024", "%d/%m/%Y").date()
        - timedelta(days=DEFAULT_WINDOW_DAYS)
    ).strftime("%d/%m/%Y")
    assert start == expected


def test_resolve_window_rejects_bad_dates() -> None:
    """Datas inválidas ou janela invertida falham de forma explícita."""
    with pytest.raises(FetchError, match="dd/mm/yyyy"):
        resolve_window("2024-06-01", None)
    with pytest.raises(FetchError, match="after end"):
        resolve_window("01/07/2024", "30/06/2024")
