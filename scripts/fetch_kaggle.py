"""Baixa um dataset Kaggle em data/raw/csv/ via kaggle-api oficial.

Credenciais (verificadas antes de importar kaggle — ver .env.example):
    KAGGLE_USERNAME + KAGGLE_KEY (legado) ou KAGGLE_API_TOKEN (novo),
    ou ~/.kaggle/{kaggle.json,access_token}.
Arquivos baixados ficam gitignorados; a fixture sintética continua versionada.
Obs.: kaggle-api 2.x não expõe download por versão, então o slug abaixo é
a âncora de reprodutibilidade.

Uso:
    python scripts/fetch_kaggle.py
    python scripts/fetch_kaggle.py --slug owner/outro-dataset
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from multi_format_etl.config import load_settings, setup_logging

logger = setup_logging()

DEFAULT_SLUG = "pradeepkumar2424/usa-banking-transactions-dataset-2023-2024"


def _has_credentials() -> bool:
    """Retorna True se há credenciais Kaggle (variáveis de ambiente ou ~/.kaggle)."""
    if os.getenv("KAGGLE_USERNAME") and os.getenv("KAGGLE_KEY"):
        return True
    if os.getenv("KAGGLE_API_TOKEN"):
        return True
    kaggle_dir = Path.home() / ".kaggle"
    return (kaggle_dir / "kaggle.json").exists() or (kaggle_dir / "access_token").exists()


def main() -> int:
    """Autentica e baixa o dataset (descompactado) em raw/csv/."""
    parser = argparse.ArgumentParser(description="Baixa um dataset Kaggle em data/raw/csv/")
    parser.add_argument("--slug", default=DEFAULT_SLUG, help="owner/nome-do-dataset")
    args = parser.parse_args()

    settings = load_settings()  # carrega o .env antes do kaggle ver o ambiente
    if not _has_credentials():
        logger.error(
            "No Kaggle credentials. Copy .env.example to .env and set "
            "KAGGLE_USERNAME/KAGGLE_KEY (or KAGGLE_API_TOKEN), or run `kaggle auth login`."
        )
        return 1

    try:
        from kaggle.api.kaggle_api_extended import KaggleApi
    except ImportError:
        logger.error("kaggle-api not installed. Run: uv pip install -e '.[dev]'")
        return 1

    dest = settings.raw_dir / "csv"
    dest.mkdir(parents=True, exist_ok=True)
    api = KaggleApi()
    try:
        api.authenticate()
        api.dataset_download_files(args.slug, path=str(dest), unzip=True, quiet=False)
    except SystemExit:
        logger.error("Kaggle authentication failed (see message above).")
        return 1
    except Exception as exc:
        logger.error("Fetch FAILED: %s", exc)
        return 1

    files = sorted(p.name for p in dest.iterdir() if p.is_file())
    logger.info(
        "Downloaded %d file(s) into %s: %s",
        len(files),
        dest,
        ", ".join(files) or "(none)",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
