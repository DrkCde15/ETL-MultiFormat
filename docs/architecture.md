# Arquitetura — Multi-format ETL

## Etapa 1 (implementada)

- Um loader por formato (`loaders/`), cada um com erro explícito `LoadError`.
- `standardize()`: normaliza nomes de colunas + proveniência. Nenhuma regra
  de negócio aqui de propósito.
- `validation/EXPECTED_COLUMNS`: checagem de presença (base para Pandera/GE).
- Amostras pequenas e intencionais: JSON com 1 `amount` nulo, logs com 1
  `failed` — fixtures para a etapa de limpeza.

## Decisões

- pandas na etapa 1 (volume pequeno); PySpark entra quando `curated/` exigir.
- Parquet em `processed/` prepara migração para Delta.
- XML via stdlib para evitar dependência extra.

## Futuro (não implementado)

`transformation/clean.py`, `aggregate.py`, `validation/checks.py`,
`curated/` agregado, Spark/Delta, Data Quality com GE/Pandera.
