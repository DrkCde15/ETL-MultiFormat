"""Testes: helpers de fetch do PTAX (montagem de URL, janela) — sem rede."""

from __future__ import annotations

import json
from datetime import datetime, timedelta

import pytest

from multi_format_etl.fetch import (
    DEFAULT_WINDOW_DAYS,
    FetchError,
    fetch_bcb_ptax,
    ptax_url,
    resolve_window,
)


def test_ptax_url_formats_odata_window() -> None:
    """Datas dd/mm/yyyy viram MM-DD-YYYY no padrão OData do endpoint."""
    url = ptax_url("01/07/2026", "03/10/2026")
    assert url == (
        "https://olinda.bcb.gov.br/olinda/servico/PTAX/versao/v1/odata/"
        "CotacaoDolarPeriodo(dataInicial=@dataInicial,dataFinalCotacao=@dataFinalCotacao)"
        "?@dataInicial='07-01-2026'&@dataFinalCotacao='10-03-2026'&$format=json"
    )


def test_ptax_url_rejects_bad_dates() -> None:
    """Data fora do formato dd/mm/yyyy falha com mensagem explícita."""
    with pytest.raises(FetchError, match="dd/mm/yyyy"):
        ptax_url("2026-07-01", "03/10/2026")


def test_resolve_window_defaults_to_90_days() -> None:
    """Requisições sem datas recebem os últimos 90 dias (padrão da janela)."""
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
        datetime.strptime("30/06/2024", "%d/%m/%Y").date() - timedelta(days=DEFAULT_WINDOW_DAYS)
    ).strftime("%d/%m/%Y")
    assert start == expected


def test_resolve_window_rejects_bad_dates() -> None:
    """Datas inválidas ou janela invertida falham de forma explícita."""
    with pytest.raises(FetchError, match="dd/mm/yyyy"):
        resolve_window("2024-06-01", None)
    with pytest.raises(FetchError, match="after end"):
        resolve_window("01/07/2024", "30/06/2024")


def test_fetch_bcb_ptax_validates_envelope_and_writes_raw(tmp_path, monkeypatch) -> None:
    """Envelope {"value": [...]} válido é gravado cru; payload vazio falha."""
    records = {"value": [{"datahora": "2024-06-03 13:07:12", "cotacao_venda": 5.14}]}
    raw = json.dumps(records).encode()
    monkeypatch.setattr("multi_format_etl.fetch.http_get", lambda url, timeout=60.0: raw)
    out = fetch_bcb_ptax(tmp_path, start="01/06/2024", end="30/06/2024")
    assert out == tmp_path / "bcb_ptax_usd.json"
    assert out.read_bytes() == raw

    monkeypatch.setattr(
        "multi_format_etl.fetch.http_get", lambda url, timeout=60.0: b'{"value": []}'
    )
    with pytest.raises(FetchError, match="no records"):
        fetch_bcb_ptax(tmp_path, start="01/06/2024", end="30/06/2024")

    monkeypatch.setattr(
        "multi_format_etl.fetch.http_get", lambda url, timeout=60.0: b"<html>oops</html>"
    )
    with pytest.raises(FetchError, match="invalid JSON"):
        fetch_bcb_ptax(tmp_path, start="01/06/2024", end="30/06/2024")
