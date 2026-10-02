"""CLI: replica data/gold/ no Postgres local (opcional — requer DATABASE_URL).

Uso:
    podman compose up -d
    export DATABASE_URL=postgresql://etl:etl@localhost:5432/multi_format_etl
    python scripts/load_postgres.py

Sem DATABASE_URL o script apenas avisa e sai com 0 — o pipeline de
arquivos nunca depende do banco.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from multi_format_etl.config import load_settings, setup_logging
from multi_format_etl.db import DbError, load_gold

logger = setup_logging()


def main() -> int:
    """Sincroniza as tabelas gold no Postgres; sem DSN sai com aviso (exit 0)."""
    settings = load_settings()
    dsn = os.getenv("DATABASE_URL")
    if not dsn:
        logger.info(
            "DATABASE_URL não definido — camada Postgres ignorada (opcional). "
            "Suba o banco com `podman compose up -d` e exporte DATABASE_URL."
        )
        return 0
    try:
        loaded = load_gold(settings, dsn)
    except DbError as exc:
        logger.error("Load FAILED: %s", exc)
        return 1
    for name, rows in sorted(loaded.items()):
        logger.info("Loaded %s rows=%d", name, rows)
    logger.info("Postgres DONE: %d table(s)", len(loaded))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
