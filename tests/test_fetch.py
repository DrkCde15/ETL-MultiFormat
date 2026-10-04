"""Testes: helpers de fetch do PTAX (montagem de URL, janela, incremental) — sem rede."""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta

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


def _write_series(tmp_path, records: list[dict]):
    path = tmp_path / "bcb_ptax_usd.json"
    path.write_text(json.dumps({"value": records}), encoding="utf-8")
    return path


def test_fetch_bcb_ptax_validates_envelope_and_writes_raw(tmp_path, monkeypatch) -> None:
    """No modo --full, envelope válido é gravado cru; vazio/HTML falha rápido."""
    records = {"value": [{"datahora": "2024-06-03 13:07:12", "cotacao_venda": 5.14}]}
    raw = json.dumps(records).encode()
    monkeypatch.setattr("multi_format_etl.fetch.http_get", lambda url, timeout=60.0: raw)
    out = fetch_bcb_ptax(tmp_path, start="01/06/2024", end="30/06/2024", incremental=False)
    assert out == tmp_path / "bcb_ptax_usd.json"
    assert out.read_bytes() == raw

    monkeypatch.setattr(
        "multi_format_etl.fetch.http_get", lambda url, timeout=60.0: b'{"value": []}'
    )
    with pytest.raises(FetchError, match="no records"):
        fetch_bcb_ptax(tmp_path, start="01/06/2024", end="30/06/2024", incremental=False)

    monkeypatch.setattr(
        "multi_format_etl.fetch.http_get", lambda url, timeout=60.0: b"<html>oops</html>"
    )
    with pytest.raises(FetchError, match="invalid JSON"):
        fetch_bcb_ptax(tmp_path, start="01/06/2024", end="30/06/2024", incremental=False)


def test_fetch_incremental_starts_day_after_last_quote(tmp_path, monkeypatch) -> None:
    """Sem datas, a janela começa no dia seguinte à última cotação gravada."""
    _write_series(tmp_path, [{"dataHoraCotacao": "2026-06-01T00:00:00", "cotacaoVenda": 5.0}])
    seen: dict[str, str] = {}

    def fake_get(url: str, *, timeout: float = 60.0) -> bytes:
        seen["url"] = url
        body = {"value": [{"dataHoraCotacao": "2026-06-02T00:00:00", "cotacaoVenda": 5.1}]}
        return json.dumps(body).encode()

    monkeypatch.setattr("multi_format_etl.fetch.http_get", fake_get)
    out = fetch_bcb_ptax(tmp_path)
    assert "@dataInicial='06-02-2026'" in seen["url"]
    values = json.loads(out.read_text(encoding="utf-8"))["value"]
    assert [r["dataHoraCotacao"] for r in values] == [
        "2026-06-01T00:00:00",
        "2026-06-02T00:00:00",
    ]


def test_fetch_incremental_merges_and_dedups_new_wins(tmp_path, monkeypatch) -> None:
    """Mescla deduplicando por dataHoraCotacao: registro novo substitui o antigo."""
    _write_series(
        tmp_path,
        [
            {"dataHoraCotacao": "2026-06-01T00:00:00", "cotacaoVenda": 4.9},
            {"dataHoraCotacao": "2026-06-02T00:00:00", "cotacaoVenda": 5.0},
        ],
    )

    def fake_get(url: str, *, timeout: float = 60.0) -> bytes:
        body = {
            "value": [
                {"dataHoraCotacao": "2026-06-01T00:00:00", "cotacaoVenda": 4.95},
                {"dataHoraCotacao": "2026-06-03T00:00:00", "cotacaoVenda": 5.2},
            ]
        }
        return json.dumps(body).encode()

    monkeypatch.setattr("multi_format_etl.fetch.http_get", fake_get)
    out = fetch_bcb_ptax(tmp_path)
    values = json.loads(out.read_text(encoding="utf-8"))["value"]
    assert [(r["dataHoraCotacao"], r["cotacaoVenda"]) for r in values] == [
        ("2026-06-01T00:00:00", 4.95),
        ("2026-06-02T00:00:00", 5.0),
        ("2026-06-03T00:00:00", 5.2),
    ]


def test_fetch_incremental_keeps_file_when_no_new_records(tmp_path, monkeypatch) -> None:
    """Janela sem registros novos mantém o arquivo atual (fim de semana não é erro)."""
    before = [{"dataHoraCotacao": "2026-06-01T00:00:00", "cotacaoVenda": 5.0}]
    path = _write_series(tmp_path, before)
    monkeypatch.setattr(
        "multi_format_etl.fetch.http_get", lambda url, timeout=60.0: b'{"value": []}'
    )
    out = fetch_bcb_ptax(tmp_path)
    assert out == path
    assert json.loads(path.read_text(encoding="utf-8"))["value"] == before


def test_fetch_incremental_skips_http_when_series_has_today(tmp_path, monkeypatch) -> None:
    """Série já com cotação de hoje não faz requisição nenhuma."""
    today = date.today().isoformat()
    path = _write_series(tmp_path, [{"dataHoraCotacao": f"{today}T00:00:00", "cotacaoVenda": 5.0}])

    def fail_get(url: str, *, timeout: float = 60.0) -> bytes:
        raise AssertionError("HTTP should be skipped when series is current")

    monkeypatch.setattr("multi_format_etl.fetch.http_get", fail_get)
    assert fetch_bcb_ptax(tmp_path) == path


def test_fetch_incremental_without_file_uses_default_window(tmp_path, monkeypatch) -> None:
    """Arquivo ausente (clone novo) cai na janela padrão de 90 dias."""
    seen: dict[str, str] = {}

    def fake_get(url: str, *, timeout: float = 60.0) -> bytes:
        seen["url"] = url
        body = {"value": [{"dataHoraCotacao": "2026-07-06T00:00:00", "cotacaoVenda": 5.4}]}
        return json.dumps(body).encode()

    monkeypatch.setattr("multi_format_etl.fetch.http_get", fake_get)
    out = fetch_bcb_ptax(tmp_path)
    expected_start, expected_end = resolve_window(None, None)
    assert ptax_url(expected_start, expected_end) == seen["url"]
    assert len(json.loads(out.read_text(encoding="utf-8"))["value"]) == 1


def test_fetch_full_mode_replaces_whole_file(tmp_path, monkeypatch) -> None:
    """--full descarta a série existente e grava só a janela pedida."""
    _write_series(tmp_path, [{"dataHoraCotacao": "2026-06-01T00:00:00", "cotacaoVenda": 5.0}])
    raw = json.dumps({"value": [{"dataHoraCotacao": "2026-07-06T00:00:00"}]}).encode()
    monkeypatch.setattr("multi_format_etl.fetch.http_get", lambda url, timeout=60.0: raw)
    out = fetch_bcb_ptax(tmp_path, start="01/07/2026", end="31/07/2026", incremental=False)
    assert json.loads(out.read_text(encoding="utf-8"))["value"] == [
        {"dataHoraCotacao": "2026-07-06T00:00:00"}
    ]
