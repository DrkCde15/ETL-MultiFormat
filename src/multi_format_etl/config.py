"""Centralized configuration (env-overridable, paths relative to project root)."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path


def get_project_root() -> Path:
    """Return project root (folder containing pyproject.toml)."""
    current = Path(__file__).resolve()
    for parent in [current.parent, *current.parents]:
        if (parent / "pyproject.toml").exists():
            return parent
    return current.parents[2]


def setup_logging(level: str | None = None) -> logging.Logger:
    """Configure root logging once and return a namespaced logger."""
    resolved = (level or os.getenv("LOG_LEVEL", "INFO")).upper()
    logging.basicConfig(
        level=getattr(logging, resolved, logging.INFO),
        format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    )
    return logging.getLogger("multi_format_etl")


@dataclass(frozen=True)
class Settings:
    """Immutable runtime settings."""

    project_root: Path
    raw_dir: Path
    processed_dir: Path
    curated_dir: Path
    log_level: str

    def ensure_dirs(self) -> None:
        """Create output dirs (processed/curated). Raw must already exist."""
        self.processed_dir.mkdir(parents=True, exist_ok=True)
        self.curated_dir.mkdir(parents=True, exist_ok=True)


def load_settings() -> Settings:
    """Load settings from environment with local defaults."""
    try:
        from dotenv import load_dotenv  # type: ignore
    except ImportError:
        pass
    else:
        root = get_project_root()
        env_file = root / ".env"
        if env_file.exists():
            load_dotenv(env_file)

    root = get_project_root()

    def _resolve(var: str, default: str) -> Path:
        p = Path(os.getenv(var, default))
        return p if p.is_absolute() else root / p

    return Settings(
        project_root=root,
        raw_dir=_resolve("RAW_DATA_DIR", "data/raw"),
        processed_dir=_resolve("PROCESSED_DATA_DIR", "data/processed"),
        curated_dir=_resolve("CURATED_DATA_DIR", "data/curated"),
        log_level=os.getenv("LOG_LEVEL", "INFO"),
    )
