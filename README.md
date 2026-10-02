# ETL/ELT com Dados Estruturados e Não Estruturados

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

## Objetivo

Demonstrar capacidade de ingerir e padronizar **diferentes formatos**:
CSV, JSON, XML e logs semiestruturados de transações.

**Escopo desta versão (v0.1.0 — Etapa 1):** um loader por formato em `load.py` +
padronização (`standardize`) + limpeza de estágio 1 (`clean`) + checks de
nulos/duplicados/tipos. Sem agregações e sem Spark ainda.

## Problema

Na prática, dados chegam em formatos heterogêneos (extratos CSV, payloads
JSON de API, legados em XML, logs de aplicação). Este projeto cria um ponto
de entrada único e testado para esses formatos, com contrato mínimo por
formato e proveniência (`_source_format`, `_source_file`).

## Arquitetura

```text
data/raw/{csv,json,xml,logs}/  →  load.py  →  standardize()  →  data/processed/<fmt>/data.parquet
                                                                          ↓
                                                  clean()  +  check_quality()  (nulos/duplicados/tipos)
                                                                          ↓
                                                    data/curated/<fmt>/data.parquet
                                                                          ↓ (futuro)
                                                               agregado (Spark/Delta)
```

Futuro: Pandera/Great Expectations, agregações em `curated/`, PySpark/Databricks.

## Tecnologias

Python 3.10+, pandas + pyarrow, python-dotenv, pytest. XML via stdlib
(`xml.etree`). Nenhum recurso cloud.

## Estrutura do projeto

```text
multi-format-etl/
├── data/raw/{csv,json,xml,logs}/  # amostras versionadas
├── data/{processed,curated}/      # saída local (gitignored)
├── src/multi_format_etl/
│   ├── config.py
│   ├── load.py          # registry suffix → reader (csv/json/xml/log)
│   ├── transform.py     # standardize() + clean()
│   └── valid.py         # SPEC + check_columns + check_quality
├── scripts/run_load.py
├── tests/test_loaders.py
└── docs/architecture.md
```

## Como executar

```bash
cd multi-format-etl
uv venv --python 3.12                # cria .venv com Python 3.12
source .venv/bin/activate
uv pip install -e ".[dev]"            # instala o pacote + extras dev
# ou só as dependências: uv pip install -r requirements.txt
cp .env.example .env   # opcional
python scripts/run_load.py
pytest
```

## Próximas etapas

1. ~~Validação de schema + checks (nulos, duplicados, tipos)~~ (concluído: `valid.py`).
2. ~~Limpeza e normalização por formato em `transform.py`~~ (concluído: `transform.clean()`).
3. Curated agregado + Spark/Delta.
4. Contrato por fonte (ex.: JSON aninhado real, XML com namespace).
5. Validação avançada com Pandera/Great Expectations.
6. Fontes reais por formato — CSV←Kaggle (CC0), JSON←API BCB, logs←
   fixture/format-bridge. Desenho em `docs/architecture.md`.

## Licença

Distribuído sob a licença MIT — veja [`LICENSE`](LICENSE).
