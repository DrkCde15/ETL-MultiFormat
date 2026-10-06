"""Wiring da observabilidade: DAG + callbacks + compose (sem airflow instalado)."""

from __future__ import annotations

import ast
import importlib.util
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DAG_FILE = ROOT / "dags" / "multi_format_etl_dag.py"
HOOK_FILE = ROOT / "dags" / "monitoring_callbacks.py"


def test_dag_wires_monitoring_callbacks() -> None:
    """DAG registra runs via callbacks (default_args), com import seguro."""
    src = DAG_FILE.read_text(encoding="utf-8")
    assert ast.parse(src) is not None
    assert "from monitoring_callbacks import" in src
    assert "on_success_callback" in src and "on_failure_callback" in src
    hook = HOOK_FILE.read_text(encoding="utf-8")
    assert "record_finished_run" in hook
    assert "except ImportError" in hook, "hook precisa ser no-op sem monitoring"


def test_compose_and_gitignore_wire_monitoring() -> None:
    """Compose monta o src do monitoring; monitoring.db não vai ao git."""
    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    assert "pipeline-monitoring/src:/opt/monitoring/src" in compose
    assert "DATABASE_PATH" in compose
    assert "monitoring.db" in compose
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "monitoring.db" in gitignore


def _load_hook_with_stub(monkeypatch, tmp_path):
    """Carrega o hook com um pipeline_monitoring fake (sem airflow/dependências)."""
    recorded = {}

    fake_pkg = types.ModuleType("pipeline_monitoring")
    fake_alerts = types.ModuleType("pipeline_monitoring.alerts")
    fake_config = types.ModuleType("pipeline_monitoring.config")
    fake_store = types.ModuleType("pipeline_monitoring.store")

    class Settings:
        database_path = tmp_path / "mon.db"
        thresholds = object()

    fake_config.load_settings = lambda: Settings()
    fake_store.init_db = lambda db_path: None
    fake_store.register_pipeline = lambda db_path, name: name

    def fake_record(db_path, name, **kwargs):
        recorded.update({"db": db_path, "name": name, **kwargs})
        return {"run_id": "r1", "pipeline_name": name, **kwargs}

    fake_store.record_finished_run = fake_record
    fake_alerts.evaluate_run = lambda run, thresholds: []

    monkeypatch.setitem(sys.modules, "pipeline_monitoring", fake_pkg)
    monkeypatch.setitem(sys.modules, "pipeline_monitoring.alerts", fake_alerts)
    monkeypatch.setitem(sys.modules, "pipeline_monitoring.config", fake_config)
    monkeypatch.setitem(sys.modules, "pipeline_monitoring.store", fake_store)

    spec = importlib.util.spec_from_file_location(
        "monitoring_callbacks_under_test", HOOK_FILE
    )
    hook = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(hook)
    return hook, recorded


def _fake_context(task_id="extract", exc=None):
    ti = types.SimpleNamespace(
        dag_id="multi_format_etl",
        task_id=task_id,
        start_date=None,
        end_date=None,
    )
    return {"task_instance": ti, "exception": exc}


def test_hook_records_success_and_failure(monkeypatch, tmp_path) -> None:
    """Hook registra dag_id.task_id com status certo; falha nunca levanta."""
    hook, recorded = _load_hook_with_stub(monkeypatch, tmp_path)
    hook.on_task_success(_fake_context())
    assert recorded["name"] == "multi_format_etl.extract"
    assert recorded["status"] == "success"
    hook.on_task_failure(_fake_context(exc=RuntimeError("boom")))
    assert recorded["status"] == "failed"
    assert "boom" in recorded["error_message"]


def test_hook_noops_without_monitoring(monkeypatch, tmp_path) -> None:
    """Sem pipeline_monitoring instalado, callbacks são no-op silencioso."""
    for mod in [m for m in sys.modules if m.startswith("pipeline_monitoring")]:
        monkeypatch.delitem(sys.modules, mod, raising=False)
    monkeypatch.setitem(sys.modules, "pipeline_monitoring", None)
    spec = importlib.util.spec_from_file_location(
        "monitoring_callbacks_noop", HOOK_FILE
    )
    hook = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(hook)  # ImportError interno -> _HAS_MONITORING=False
    hook.on_task_success(_fake_context())  # não levanta
    hook.on_task_failure(_fake_context(exc=RuntimeError("x")))  # não levanta
