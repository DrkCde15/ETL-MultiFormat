# Arquitetura — Multi-format ETL

## Etapa 1 (implementada)

- Um loader por formato num único módulo (`load.py`), com registro
  suffix → reader (`FORMAT_BY_SUFFIX`) e erro explícito `LoadError`.
- `standardize()`: normaliza nomes de colunas + proveniência. Nenhuma regra
  de negócio aqui de propósito.
- `valid.py` (`EXPECTED_COLUMNS` + `check_columns`): checagem de presença
  aplicada na ingestão (base para Pandera/GE).
- Amostras pequenas e intencionais: JSON com 1 `amount` nulo, logs com 1
  `failed` — fixtures para a etapa de limpeza.

## Decisões

- pandas na etapa 1 (volume pequeno); PySpark entra quando `curated/` exigir.
- Parquet em `processed/` prepara migração para Delta.
- XML via stdlib para evitar dependência extra.

## Futuro (não implementado)

Novos módulos `clean.py`/`aggregate.py` (transformação), `checks.py`
(qualidade), `curated/` agregado, Spark/Delta, Data Quality com GE/Pandera.
