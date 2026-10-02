# ETL/ELT com Dados Estruturados e Não Estruturados

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

## Objetivo

Demonstrar capacidade de ingerir e padronizar **diferentes formatos**:
CSV, JSON, XML e logs semiestruturados de transações.

**Escopo desta versão (v0.1.0 — Etapa 1):** um loader por formato em
`load.py` + padronização (`standardize`) + limpeza de estágio 1 (`clean`) +
checks de nulos/duplicados/tipos. **CSV e JSON vêm de fontes reais**
(dataset Kaggle e API do BCB, via `fetch_*.py`); XML e logs seguem
fixtures (não existem APIs públicas equivalentes). Sem agregações e sem
Spark ainda.

## Problema

Na prática, dados chegam em formatos heterogêneos (extratos CSV, payloads
JSON de API, legados em XML, logs de aplicação). Este projeto cria um ponto
de entrada único e testado para esses formatos, com contrato mínimo por
formato e proveniência (`_source_format`, `_source_file`).

## Arquitetura

```text
data/raw/csv/   ← Kaggle   (fetch_kaggle.py, gitignored)
data/raw/json/  ← API BCB  (fetch_json.py,    gitignored)
data/raw/xml/   ← fixture versionada
data/raw/logs/  ← fixture versionada
        ↓
     load.py  →  standardize()  →  data/processed/<fmt>/data.parquet
                                          ↓
                   clean()  +  check_quality()  (nulos/duplicados/tipos)
                                          ↓
                    data/curated/<fmt>/data.parquet
                                          ↓ (futuro)
                                 agregado (Spark/Delta)
```

Futuro: Pandera/Great Expectations, agregações em `curated/`, PySpark/Databricks.

## Fontes de dados

| Formato | Origem | Volume | Licença/acesso |
|---|---|---|---|
| CSV | Kaggle `pradeepkumar2424/usa-banking-transactions-dataset-2023-2024` | 5.389 × 20 | CC0 |
| JSON | API pública **BCB SGS** (série 1 — câmbio USD/BRL, janela de 90 dias) | ~64 × 2 | API aberta, sem credencial |
| XML | fixture sintética (legado fictício) | 3 clientes | versionada no repo |
| LOG | fixture sintética (formato `ts\|k=v` da própria aplicação) | 4 eventos | versionada no repo |

Os downloads (`data/raw/csv/`, `data/raw/json/`) ficam **fora do Git**;
as fixtures continuam versionadas para os testes rodarem offline em um
clone novo (os 2 testes dos arquivos reais pulam até o fetch rodar).

## Tecnologias

Python 3.10+, pandas + pyarrow, python-dotenv, pytest, kaggle-api (fetch
de datasets Kaggle). XML via stdlib (`xml.etree`). Nenhum recurso cloud.

## Estrutura do projeto

```text
multi-format-etl/
├── data/raw/{csv,json,xml,logs}/  # fixtures versionadas; downloads gitignored
├── data/{processed,curated}/      # saída local (gitignored)
├── src/multi_format_etl/
│   ├── config.py
│   ├── fetch.py         # BCB SGS (stdlib) + janela de datas
│   ├── load.py          # registry suffix → reader (csv/json/xml/log)
│   ├── transform.py     # standardize() + clean()
│   └── valid.py         # SPEC + check_columns + check_quality
├── scripts/
│   ├── fetch_json.py    # baixa série BCB → data/raw/json/ (gitignored)
│   ├── fetch_kaggle.py  # baixa dataset Kaggle (kaggle-api) → data/raw/csv/
│   └── run_load.py
├── tests/               # test_loaders + test_fetch (offline; reais pulam sem fetch)
└── docs/
    ├── architecture.md
    └── revisao-engenharia-dados.md
```

## Como executar

```bash
cd multi-format-etl
uv venv --python 3.12                # cria .venv com Python 3.12
source .venv/bin/activate
uv pip install -e ".[dev]"            # instala o pacote + extras dev
# ou só as dependências: uv pip install -r requirements.txt
cp .env.example .env   # obrigatório p/ Kaggle (KAGGLE_USERNAME/KAGGLE_KEY)
python scripts/fetch_json.py    # 1x: baixa série BCB → data/raw/json/
python scripts/fetch_kaggle.py  # 1x: baixa dataset Kaggle → data/raw/csv/
python scripts/run_load.py
pytest
```

## Resultado

`run_load.py` com os dados reais (exit 0):

```text
  - csv    processed=5389 curated=5389 -> data/curated/csv/data.parquet
  - json   processed=64   curated=64   -> data/curated/json/data.parquet
  - xml    processed=3    curated=3    -> data/curated/xml/data.parquet
  - logs   processed=4    curated=4    -> data/curated/logs/data.parquet
Load DONE: 5460 rows processed, 5460 rows curated
```

`pytest`: 23 testes (fixtures offline + contrato ponta a ponta dos
arquivos reais, que pulam em clone novo antes do fetch).

## Próximas etapas

1. ~~Validação de schema + checks (nulos, duplicados, tipos)~~ (concluído: `valid.py`).
2. ~~Limpeza e normalização por formato em `transform.py`~~ (concluído: `transform.clean()`).
3. Curated agregado + Spark/Delta.
4. Contrato por fonte (ex.: JSON aninhado real, XML com namespace).
5. Validação avançada com Pandera/Great Expectations.
6. ~~Fontes reais por formato~~ (concluído: CSV←Kaggle e JSON←API BCB já
   entram no pipeline via `fetch_*.py`; fixtures adaptadas aos schemas
   reais p/ testes offline; XML/logs sem fonte API equivalente).
   Desenho em `docs/architecture.md`.

## Licença

Distribuído sob a licença MIT — veja [`LICENSE`](LICENSE).
