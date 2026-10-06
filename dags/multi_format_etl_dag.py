"""Orquestração: pipeline multi-format-etl no Airflow (Etapa 3).

Tarefas são os scripts já existentes (sem retrabalho): `extract` baixa a
PTAX (BCB) de forma incremental — busca do dia seguinte à última cotação
e mescla deduplicando, então a série nunca encolhe; `transform`
reprocessa as quatro
camadas via run_load e `load` faz o full refresh das tabelas gold via
load_postgres (sai com 0 se o DATABASE_URL não estiver setado — o
arquivo nunca depende do banco).

UI local: localhost:8080 (admin/admin). Agendamento: 06:00 UTC/diário.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.bash import BashOperator

PROJECT = "/opt/airflow/project"

try:
    # dags/ está no sys.path do scheduler; sem monitoring, vira no-op.
    from monitoring_callbacks import on_task_failure, on_task_success

    _MONITORING_CALLBACKS = {
        "on_success_callback": on_task_success,
        "on_failure_callback": on_task_failure,
    }
except ImportError:
    _MONITORING_CALLBACKS = {}

default_args = {
    "owner": "etl",
    "retries": 1,
    "retry_delay": timedelta(minutes=10),
    **_MONITORING_CALLBACKS,
}

with DAG(
    dag_id="multi_format_etl",
    description="Extract PTAX (BCB) -> transform (processed/curated/gold) -> load Postgres",
    schedule="0 6 * * *",
    start_date=datetime(2025, 1, 1),
    catchup=False,
    max_active_runs=1,
    default_args=default_args,
    tags=["etl", "multi-format"],
) as dag:
    extract = BashOperator(
        task_id="extract",
        bash_command=f"python {PROJECT}/scripts/fetch_json.py",
    )
    transform = BashOperator(
        task_id="transform",
        bash_command=f"python {PROJECT}/scripts/run_load.py",
    )
    load = BashOperator(
        task_id="load",
        bash_command=f"python {PROJECT}/scripts/load_postgres.py",
    )

    extract >> transform >> load
