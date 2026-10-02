"""Baixa uma série BCB SGS (JSON bruto) em data/raw/json/.

Uso:
    python scripts/fetch_json.py
    python scripts/fetch_json.py --code 11 --start 01/06/2024 --end 30/06/2024
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from multi_format_etl.config import load_settings, setup_logging
from multi_format_etl.fetch import FetchError, fetch_bcb_sgs

logger = setup_logging()


def main() -> int:
    """Baixa uma série SGS em data/raw/json/bcb_sgs_{code}.json."""
    parser = argparse.ArgumentParser(
        description="Baixa uma série BCB SGS como JSON bruto "
        "(datas omitidas caem nos últimos 90 dias)"
    )
    parser.add_argument(
        "--code",
        type=int,
        default=1,
        help="código da série SGS (padrão: 1 = taxa de venda USD/BRL)",
    )
    parser.add_argument("--start", help="data inicial dd/mm/yyyy")
    parser.add_argument("--end", help="data final dd/mm/yyyy")
    args = parser.parse_args()

    settings = load_settings()
    try:
        out = fetch_bcb_sgs(
            args.code, settings.raw_dir / "json", start=args.start, end=args.end
        )
    except FetchError as exc:
        logger.error("Fetch FAILED: %s", exc)
        return 1
    logger.info("Fetched SGS series %s -> %s", args.code, out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
