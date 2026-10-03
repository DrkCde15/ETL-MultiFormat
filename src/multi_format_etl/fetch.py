"""Busca de fontes brutas externas (BCB PTAX JSON — somente stdlib).

O download do Kaggle vive em scripts/fetch_kaggle.py, sobre o pacote oficial
kaggle-api. Credenciais vêm do ambiente (.env) e nunca são logadas nem
gravadas em disco. Arquivos baixados são crus (como recebidos) e
gitignorados; as fixtures sintéticas continuam versionadas.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path

# PTAX de fechamento (compra/venda do USD/BRL) — mesmo BCB do SGS, endpoint
# público em olinda.bcb.gov.br (api.bcb.gov.br saiu do DNS em 03/10/2026).
PTAX_ENDPOINT = (
    "https://olinda.bcb.gov.br/olinda/servico/PTAX/versao/v1/odata/"
    "CotacaoDolarPeriodo(dataInicial=@dataInicial,dataFinalCotacao=@dataFinalCotacao)"
)

# Janela padrão quando o chamador omite as datas (séries com ~5,8 anos já
# foram validadas de ponta a ponta neste endpoint).
DEFAULT_WINDOW_DAYS = 90


class FetchError(RuntimeError):
    """Lançado quando uma fonte externa não pode ser baixada/descompactada."""


def resolve_window(start: str | None, end: str | None) -> tuple[str, str]:
    """Resolve uma janela de consulta dd/mm/yyyy, com padrão dos últimos 90 dias.

    Fim ausente significa hoje; início ausente significa 90 dias antes do fim
    resolvido. Lança FetchError em datas inválidas ou janela invertida.
    """
    try:
        end_date = datetime.strptime(end, "%d/%m/%Y").date() if end else date.today()
        start_date = (
            datetime.strptime(start, "%d/%m/%Y").date()
            if start
            else end_date - timedelta(days=DEFAULT_WINDOW_DAYS)
        )
    except ValueError as exc:
        raise FetchError(f"Invalid date {start or end!r}: use dd/mm/yyyy") from exc
    if start_date > end_date:
        raise FetchError(f"Window start {start_date:%d/%m/%Y} is after end {end_date:%d/%m/%Y}")
    return start_date.strftime("%d/%m/%Y"), end_date.strftime("%d/%m/%Y")


def ptax_url(start: str, end: str) -> str:
    """Monta a URL do CotacaoDolarPeriodo (OData).

    A API pública usa dd/mm/yyyy; o endpoint espera MM-DD-YYYY entre aspas.
    """
    try:
        start_md = datetime.strptime(start, "%d/%m/%Y").strftime("%m-%d-%Y")
        end_md = datetime.strptime(end, "%d/%m/%Y").strftime("%m-%d-%Y")
    except ValueError as exc:
        raise FetchError(f"Invalid date {start!r}/{end!r}: use dd/mm/yyyy") from exc
    return f"{PTAX_ENDPOINT}?@dataInicial='{start_md}'&@dataFinalCotacao='{end_md}'&$format=json"


def http_get(url: str, *, timeout: float = 60.0) -> bytes:
    """Faz GET na url e retorna o corpo. Lança FetchError em erros HTTP/de rede."""
    request = urllib.request.Request(url, headers={"User-Agent": "multi-format-etl/0.1"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read(200).decode("utf-8", errors="replace").strip()
        exc.close()
        raise FetchError(f"HTTP {exc.code} fetching {url}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise FetchError(f"Network error fetching {url}: {exc.reason}") from exc
    except OSError as exc:
        raise FetchError(f"Connection failed for {url}: {exc}") from exc


def fetch_bcb_ptax(
    dest_dir: Path,
    *,
    start: str | None = None,
    end: str | None = None,
) -> Path:
    """Baixa a série PTAX USD/BRL (compra/venda) como JSON bruto em dest_dir.

    Datas são dd/mm/yyyy; datas omitidas caem no padrão dos últimos 90 dias
    (ver resolve_window). Grava bcb_ptax_usd.json exatamente como recebido,
    após validar o envelope {"value": [...]} com registros. Caso contrário,
    lança FetchError.
    """
    start, end = resolve_window(start, end)
    payload = http_get(ptax_url(start, end))
    try:
        envelope = json.loads(payload)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise FetchError("PTAX endpoint returned invalid JSON") from exc
    records = envelope.get("value") if isinstance(envelope, dict) else None
    if not isinstance(records, list) or not records:
        raise FetchError("PTAX endpoint returned no records")
    dest_dir.mkdir(parents=True, exist_ok=True)
    out = dest_dir / "bcb_ptax_usd.json"
    out.write_bytes(payload)
    return out


__all__ = [
    "DEFAULT_WINDOW_DAYS",
    "FetchError",
    "fetch_bcb_ptax",
    "http_get",
    "ptax_url",
    "resolve_window",
]
