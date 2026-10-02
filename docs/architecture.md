# Arquitetura — Multi-format ETL

## Etapa 1 (implementada)

- Um loader por formato num único módulo (`load.py`), com registro
  suffix → reader (`FORMAT_BY_SUFFIX`) e erro explícito `LoadError`.
- `standardize()`: normaliza nomes de colunas + proveniência. Nenhuma regra
  de negócio aqui de propósito.
- `valid.py`: contrato único por formato (`SPEC`) com presença
  (`check_columns`, aplicada na ingestão) e qualidade pós-limpeza
  (`check_quality`: nulos, chaves duplicadas, tipos — todos os problemas
  reportados de uma vez via `CheckError`).
- `transform.clean()`: strip, coerção de tipos, remoção de linhas sem campos
  obrigatórios e dedup por chave — dirigido por `SPEC`.
- Duas camadas de saída: `processed/` (padronizado, porta `check_columns`)
  e `curated/` (limpo, porta `check_quality` — só grava se passar).
- Amostras pequenas e intencionais: JSON com 1 `amount` nulo (removido por
  `clean`), logs com 1 `failed` (status de negócio legítimo, mantido).

## Decisões

- pandas na etapa 1 (volume pequeno); PySpark entra quando `curated/` exigir.
- Parquet em `processed/` prepara migração para Delta.
- XML via stdlib para evitar dependência extra.
- `SPEC` é a fonte única da verdade: `EXPECTED_COLUMNS` é derivado dele,
  então transformação e checks nunca divergem do contrato.

## Fontes de dados reais (planejado — não implementado)

Uma fonte por formato, escolhida conforme a natureza do dado, em vez de
forçar tudo pelo Kaggle:

| Formato | Fonte escolhida | Justificativa |
|---|---|---|
| CSV | Kaggle `pradeepkumar2424/usa-banking-transactions-dataset-2023-2024` (CC0, 5k linhas) | schema legível aderente ao `SPEC` (id, data, amount, status); licença sem atrito |
| JSON | API pública **BCB SGS** (`api.bcb.gov.br`, sem credencial) | bate com o README ("payloads JSON de API"); exercita fetch + rate limit |
| LOG | fixture sintética (ou format-bridge CSV → linhas `k=v`) | o formato de log é da própria aplicação — não existe fonte pública equivalente |

Regras quando implementar:

- credenciais (ex.: `KAGGLE_USERNAME`/`KAGGLE_KEY`) só em `.env`; apenas
  placeholders no `.env.example`;
- dataset completo gitignorado; `scripts/fetch_*.py` com slug + versão
  fixados; fixtures sintéticas seguem versionadas;
- testes nunca dependem de rede;
- Loghub como opção futura só para o capítulo "parser de log de sistema"
  (licença restrita a uso de pesquisa — não é CC0).

## Futuro (não implementado)

Agregação em `curated/`, PySpark/Delta quando o volume exigir,
validação avançada com Great Expectations/Pandera.
