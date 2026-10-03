"""Testes do carregamento de configuração (achado A5 do review)."""

import sys

from multi_format_etl.config import load_settings


def test_load_settings_resolves_project_root() -> None:
    """A raiz resolvida contém o pyproject.toml."""
    settings = load_settings()
    assert (settings.project_root / "pyproject.toml").exists()


def test_warns_when_env_exists_but_dotenv_missing(tmp_path, monkeypatch, caplog) -> None:
    """Com .env presente e python-dotenv indisponível, emite warning (não engole)."""
    (tmp_path / ".env").write_text("LOG_LEVEL=DEBUG\n", encoding="utf-8")
    monkeypatch.setattr("multi_format_etl.config.get_project_root", lambda: tmp_path)
    monkeypatch.setitem(sys.modules, "dotenv", None)

    with caplog.at_level("WARNING", logger="multi_format_etl.config"):
        load_settings()

    assert "python-dotenv" in caplog.text


def test_silent_when_env_file_absent(tmp_path, monkeypatch, caplog) -> None:
    """Sem .env, a ausência do python-dotenv não gera warning."""
    monkeypatch.setattr("multi_format_etl.config.get_project_root", lambda: tmp_path)
    monkeypatch.setitem(sys.modules, "dotenv", None)

    with caplog.at_level("WARNING", logger="multi_format_etl.config"):
        load_settings()

    assert "python-dotenv" not in caplog.text
