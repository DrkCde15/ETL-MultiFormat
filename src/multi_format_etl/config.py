"""Configuração centralizada (sobrescrevível por ambiente; caminhos relativos à raiz do projeto)."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path


def get_project_root() -> Path:
    """Retorna a raiz do projeto (a pasta que contém pyproject.toml)."""
    current = Path(__file__).resolve()
    for parent in [current.parent, *current.parents]:
        if (parent / "pyproject.toml").exists():
            return parent
    return current.parents[2]


def setup_logging(level: str | None = None) -> logging.Logger:
    """Configura o logging raiz uma única vez e retorna um logger com namespace."""
    resolved = (level or os.getenv("LOG_LEVEL", "INFO")).upper()
    logging.basicConfig(
        level=getattr(logging, resolved, logging.INFO),
        format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    )
    return logging.getLogger("multi_format_etl")


@dataclass(frozen=True)
class Settings:
    """Configurações de execução imutáveis."""

    project_root: Path
    raw_dir: Path
    processed_dir: Path
    curated_dir: Path
    gold_dir: Path
    quality_dir: Path
    log_level: str

    def ensure_dirs(self) -> None:
        """Cria os diretórios de saída (processed/curated/gold/quality)."""
        self.processed_dir.mkdir(parents=True, exist_ok=True)
        self.curated_dir.mkdir(parents=True, exist_ok=True)
        self.gold_dir.mkdir(parents=True, exist_ok=True)
        self.quality_dir.mkdir(parents=True, exist_ok=True)


def load_settings() -> Settings:
    """Carrega as configurações do ambiente com padrões locais."""
    try:
        from dotenv import load_dotenv  # type: ignore
    except ImportError:
        if (get_project_root() / ".env").exists():
            logging.getLogger(__name__).warning(
                ".env found but python-dotenv is not installed — .env ignored"
            )
    else:
        root = get_project_root()
        env_file = root / ".env"
        if env_file.exists():
            load_dotenv(env_file)

    root = get_project_root()

    def _resolve(var: str, default: str) -> Path:
        """Resolve um caminho de variável de ambiente contra a raiz (absoluto passa direto)."""
        p = Path(os.getenv(var, default))
        return p if p.is_absolute() else root / p

    return Settings(
        project_root=root,
        raw_dir=_resolve("RAW_DATA_DIR", "data/raw"),
        processed_dir=_resolve("PROCESSED_DATA_DIR", "data/processed"),
        curated_dir=_resolve("CURATED_DATA_DIR", "data/curated"),
        gold_dir=_resolve("GOLD_DATA_DIR", "data/gold"),
        quality_dir=_resolve("QUALITY_DATA_DIR", "data/quality"),
        log_level=os.getenv("LOG_LEVEL", "INFO"),
    )
