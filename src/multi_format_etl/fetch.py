"""Busca de fontes brutas externas (BCB SGS JSON — somente stdlib).

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

SGS_ENDPOINT = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{code}/dados"

# O BCB rejeita séries diárias com janela maior que 10 anos (HTTP 406),
# então requisições sem datas caem no padrão dos últimos 90 dias.
DEFAULT_WINDOW_DAYS = 90


class FetchError(RuntimeError):
    """Lançado quando uma fonte externa não pode ser baixada/descompactada."""


def sgs_url(code: int, start: str | None = None, end: str | None = None) -> str:
    """Monta a URL do endpoint JSON do BCB SGS (datas como dd/mm/yyyy)."""
    params = ["formato=json"]
    if start:
        params.append(f"dataInicial={start}")
    if end:
        params.append(f"dataFinal={end}")
    return f"{SGS_ENDPOINT.format(code=code)}?{'&'.join(params)}"


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


def fetch_bcb_sgs(
    code: int,
    dest_dir: Path,
    *,
    start: str | None = None,
    end: str | None = None,
) -> Path:
    """Baixa uma série BCB SGS como JSON bruto em dest_dir.

    Datas são dd/mm/yyyy; datas omitidas caem no padrão dos últimos 90 dias
    (ver resolve_window). Grava bcb_sgs_{code}.json exatamente como recebido,
    após validar que o payload é um array JSON não vazio. Caso contrário,
    lança FetchError.
    """
    start, end = resolve_window(start, end)
    payload = http_get(sgs_url(code, start, end))
    try:
        records = json.loads(payload)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise FetchError(f"BCB SGS series {code} returned invalid JSON") from exc
    if not isinstance(records, list) or not records:
        raise FetchError(f"BCB SGS series {code} returned no records")
    dest_dir.mkdir(parents=True, exist_ok=True)
    out = dest_dir / f"bcb_sgs_{code}.json"
    out.write_bytes(payload)
    return out


__all__ = [
    "DEFAULT_WINDOW_DAYS",
    "FetchError",
    "fetch_bcb_sgs",
    "http_get",
    "resolve_window",
    "sgs_url",
]
