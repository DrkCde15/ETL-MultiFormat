# ETL/ELT com Dados Estruturados e Não Estruturados

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![CI](https://github.com/DrkCde15/ETL-MultiFormat/actions/workflows/ci.yml/badge.svg)](https://github.com/DrkCde15/ETL-MultiFormat/actions/workflows/ci.yml)

## Objetivo

Demonstrar capacidade de ingerir e padronizar **diferentes formatos**:
CSV, JSON, XML e logs semiestruturados de transações.

**v0.4.0 — Etapa 1 (pipeline) concluída:** um loader por formato em
`load.py` + padronização (`standardize`) + limpeza (`clean`, com
estatística de descarte) + **camada de data quality** (nulos, chaves,
tipos, faixas, enums e frescor, com relatório `quality_report.json`) +
**camada gold com agregados de negócio** (`aggregate.py`) +
**disponibilização opcional em Postgres**. **CSV e JSON vêm de fontes
reais** (dataset Kaggle e API do BCB, via `fetch_*.py`); XML e logs
seguem fixtures (não existem APIs públicas equivalentes). Spark continua
fora — a gold roda em pandas.

**Etapa 2 (DataOps) concluída:** CI no GitHub Actions (`uv sync` +
`ruff check` + `ruff format --check` + `pytest` com cobertura e serviço
Postgres, habilitando o roundtrip completo), **lockfile `uv.lock`**,
badge de build e avisos de configuração — achados A4/A5/A6 do
`docs/revisao-engenharia-dados.md`.

**Etapa 3 (orquestração) concluída:** DAG do **Airflow 2.6**
(`dags/multi_format_etl_dag.py`) encadeia `extract → transform →
load` (fetch PTAX **incremental** — busca só o dia seguinte à última
cotação e mescla, a série nunca encolhe → run_load → load_postgres)
diariamente às 06:00
(UTC), em container próprio
(`Dockerfile.airflow` + serviço `airflow` no compose) com UI local em
`localhost:8080` (admin/admin) — metadados no Postgres (banco `airflow`)
+ LocalExecutor. Falha da fonte BCB é **fail-fast por decisão
explícita**: run fica vermelha (retry único) em vez de seguir com
snapshot velho (janela sem registros novos, tipo fim de semana,
mantém o arquivo e não é erro).

## Problema

Na prática, dados chegam em formatos heterogêneos (extratos CSV, payloads
JSON de API, legados em XML, logs de aplicação). Este projeto cria um ponto
de entrada único e testado para esses formatos, com contrato mínimo por
formato e proveniência (`_source_format`, `_source_file`).

## Arquitetura

```text
data/raw/csv/   ← Kaggle   (fetch_kaggle.py, gitignored)
data/raw/json/  ← BCB PTAX (fetch_json.py,    gitignored)
data/raw/xml/   ← fixture versionada
data/raw/logs/  ← fixture versionada
        ↓
     load.py  →  standardize()  →  data/processed/<fmt>/data.parquet
                                          ↓
                   clean()  +  check_quality()  (nulos, chave, tipos,
                                          ↓        faixa, enum, frescor)
                    data/curated/<fmt>/data.parquet
                                   ↓
                  aggregate()  →  data/gold/<fmt>/<tabela>.parquet
                                   ↓ (futuro)
                          Spark/Delta sobre a gold

  + data/quality/quality_report.json  (status, checks executados,
    descartes do clean e totais — gravado a cada execução)

Orquestração (Etapa 3): DAG `multi_format_etl` no Airflow —
  extract → transform → load  (06:00 UTC/diário, catchup off)
```

Futuro: Pandera/Great Expectations, PySpark/Databricks sobre a gold.

## Fontes de dados

| Formato | Origem | Volume | Licença/acesso |
|---|---|---|---|
| CSV | Kaggle `pradeepkumar2424/usa-banking-transactions-dataset-2023-2024` | 5.389 × 20 | CC0 |
| JSON | API pública **BCB PTAX** (`olinda.bcb.gov.br` — USD/BRL compra/venda, bootstrap `--start 01/01/2021` + fetch incremental diário) | 1.446 × 3 | API aberta, sem credencial |
| XML | fixture sintética (legado fictício) | 3 clientes | versionada no repo |
| LOG | fixture sintética (formato `ts\|k=v` da própria aplicação) | 4 eventos | versionada no repo |

Os downloads (`data/raw/csv/`, `data/raw/json/`) ficam **fora do Git**;
as fixtures continuam versionadas para os testes rodarem offline em um
clone novo (os 2 testes dos arquivos reais pulam até o fetch rodar).

## Tecnologias

Python 3.11+, pandas + pyarrow, python-dotenv, pytest + pytest-cov, ruff
(lint/formatação), uv (lockfile `uv.lock` + GitHub Actions), kaggle-api
(fetch de datasets Kaggle), psycopg (disponibilização opcional em
PostgreSQL local via Docker), Apache Airflow 2.6 (orquestração local em
container — LocalExecutor + metadados no Postgres). XML via stdlib
(`xml.etree`). Nenhum recurso cloud.

## Estrutura do projeto

```text
multi-format-etl/
├── .github/workflows/ci.yml # CI: uv sync + ruff + compileall + pytest
├── Dockerfile.airflow   # imagem Airflow 2.6 com o projeto instalado
├── dags/multi_format_etl_dag.py  # DAG: extract → transform → load (ETL p/ Postgres)
├── data/raw/{csv,json,xml,logs}/  # fixtures versionadas; downloads gitignored
├── docker-compose.yml   # Postgres 16 + Airflow local (podman / docker compose)
├── docker-entrypoint-initdb.d/  # init do Postgres: cria o banco airflow
├── data/{processed,curated,gold,quality}/  # saída local (gitignored)
├── uv.lock              # lockfile (uv sync --extra dev --frozen)
├── src/multi_format_etl/
│   ├── aggregate.py     # camada gold: agregados por formato
│   ├── config.py
│   ├── db.py            # gold → Postgres (opcional, DATABASE_URL)
│   ├── fetch.py         # BCB PTAX (stdlib) + janela de datas
│   ├── load.py          # registry suffix → reader (csv/json/xml/log)
│   ├── transform.py     # standardize() + clean() (com estatísticas)
│   └── valid.py         # SPEC + checks + relatório de qualidade
├── scripts/
│   ├── fetch_json.py    # baixa série PTAX do BCB → data/raw/json/ (gitignored)
│   ├── fetch_kaggle.py  # baixa dataset Kaggle (kaggle-api) → data/raw/csv/
│   ├── load_postgres.py # gold → Postgres (só com DATABASE_URL)
│   └── run_load.py
├── notebooks/
│   └── 01_analise_exploratoria.ipynb  # EDA das 4 fontes + quality/gold
├── tests/               # loaders/fetch/gold/quality/db/config (offline)
└── docs/
    ├── architecture.md
    └── revisao-engenharia-dados.md
```

## Como executar

```bash
cd multi-format-etl
uv sync --extra dev                # instala do uv.lock (recomendado, reproduzível)
# ou manualmente: uv venv --python 3.12 && source .venv/bin/activate
#                 uv pip install -e ".[dev]"
cp .env.example .env   # obrigatório p/ Kaggle (KAGGLE_USERNAME/KAGGLE_KEY)
python scripts/fetch_json.py    # 1x: baixa série PTAX (BCB) → data/raw/json/
python scripts/fetch_kaggle.py  # 1x: baixa dataset Kaggle → data/raw/csv/
python scripts/run_load.py
pytest

# opcional: disponibilização das tabelas gold em Postgres local
podman compose up -d db   # (ou: docker compose up -d db)
export DATABASE_URL=postgresql://etl:etl@localhost:5432/multi_format_etl
python scripts/load_postgres.py   # sem DATABASE_URL: avisa e sai com 0

# opcional: orquestração (Airflow local; UI em http://localhost:8080 — admin/admin)
podman compose up -d --build airflow
# primeira vez: despausar/trigger (DAG nasce pausada)
podman compose exec airflow airflow dags unpause multi_format_etl
podman compose exec airflow airflow dags trigger multi_format_etl
podman compose down            # para tudo (db + airflow)
```

## Resultado

`run_load.py` com os dados reais (exit 0):

```text
  - csv    processed=5389 curated=5389 gold=2 -> data/curated/csv/data.parquet
  - json   processed=1446 curated=1446 gold=1 -> data/curated/json/data.parquet
  - xml    processed=3    curated=3    gold=1 -> data/curated/xml/data.parquet
  - logs   processed=4    curated=4    gold=2 -> data/curated/logs/data.parquet
Load DONE: 6842 rows processed, 6842 rows curated, 6 gold tables
```

`pytest`: 53 testes (fixtures offline + contrato ponta a ponta dos
arquivos reais, que pulam em clone novo antes do fetch; o roundtrip de
Postgres pula sem `DATABASE_URL` e roda no CI via serviço).

A cada execução o `run_load` grava `data/quality/quality_report.json`
com o **status da carga, os checks executados por formato**
(ex.: `range:transaction_amount`, `enum:transaction_status`,
`freshness:transaction_date`), **o que o `clean` descartou** (nulos por
coluna, chaves duplicadas) e os totais — evidência auditável da qualidade.

**Postgres opcional**: com `DATABASE_URL` apontando para o
`podman compose up -d`, `scripts/load_postgres.py` replica as 6 tabelas
gold no schema `gold` (`gold.csv_by_status`, `gold.json_by_month`, …)
em full refresh (DROP + CREATE + INSERT — o DDL vem dos dtypes, então
mudança de schema recria a tabela). Sem o
DSN, o script só avisa — o pipeline de arquivos nunca depende do banco.

Tabelas gold geradas:

| Formato | Tabelas | Conteúdo |
|---|---|---|
| csv | `by_status`, `by_month` | transações, total/média de valor, taxa de fraude mensal |
| json | `by_month` | pregões observados, mín/máx/média da PTAX (venda) por mês |
| xml | `by_branch` | clientes por agência |
| logs | `by_status`, `by_type` | eventos e volume transacionado |

## Próximas etapas

1. ~~Validação de schema + checks (nulos, duplicados, tipos)~~ (concluído: `valid.py`).
2. ~~Limpeza e normalização por formato em `transform.py`~~ (concluído: `transform.clean()`).
3. Spark/Delta sobre a gold (a camada gold local, em pandas, está
   concluída — `aggregate.py`).
4. Contrato por fonte (ex.: JSON aninhado real, XML com namespace).
5. Validação avançada com Pandera/Great Expectations (as regras de
   negócio e o relatório de qualidade já estão no núcleo, sem dependência).
6. ~~Fontes reais por formato~~ (concluído: CSV←Kaggle e JSON←API BCB já
   entram no pipeline via `fetch_*.py`; fixtures adaptadas aos schemas
   reais p/ testes offline; XML/logs sem fonte API equivalente).
   Desenho em `docs/architecture.md`.
7. ~~**Etapa 2 — DataOps**~~ (concluído: CI no GitHub Actions com
   `uv sync --frozen` + `ruff check` + `ruff format --check` + `pytest
   --cov` com serviço Postgres, lockfile `uv.lock`, badge de build e
   warning do A5 — achados A4/A5/A6).
8. ~~**Etapa 3 — Orquestração**~~ (concluído: DAG `multi_format_etl` no
   Airflow 2.6 em container — `dags/` + `Dockerfile.airflow` + serviço
   `airflow` no compose; agendamento diário 06:00, fail-fast na fonte,
   `compileall dags` no CI).

## Licença

Distribuído sob a licença MIT — veja [`LICENSE`](LICENSE).
