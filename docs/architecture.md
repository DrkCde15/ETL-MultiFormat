# Arquitetura — Multi-format ETL

## Etapa 1 — pipeline (implementada)

- Um loader por formato num único módulo (`load.py`), com registro
  suffix → reader (`FORMAT_BY_SUFFIX`) e erro explícito `LoadError`.
- `standardize()`: normaliza nomes de colunas + proveniência. Nenhuma regra
  de negócio aqui de propósito.
- `valid.py`: contrato único por formato (`SPEC`) com presença
  (`check_columns`, aplicada na ingestão) e qualidade pós-limpeza
  (`check_quality`: nulos, chaves duplicadas, tipos, **faixas** (`ranges`),
  **valores permitidos** (`enums`) e **frescor** — todos os problemas
  reportados de uma vez via `CheckError`; retorna os checks executados).
- `transform.clean()`: strip, coerção de tipos, remoção de linhas sem campos
  obrigatórios e dedup por chave — dirigido por `SPEC`; `clean_with_stats()`
  devolve também **o que foi descartado** (nulos por coluna, duplicatas).
- Relatório de qualidade: `run_load` grava `data/quality/quality_report.json`
  a cada execução (status, checks executados por formato, descartes do
  clean, totais) — evidência em vez de "passou silenciosamente".
- Três camadas de saída: `processed/` (padronizado, porta `check_columns`),
  `curated/` (limpo, porta `check_quality` — só grava se passar) e
  `gold/` (`aggregate.py`, dispatch `AGGREGATORS` por formato):
  csv → `by_status` + `by_month` (com taxa de fraude), json → série BCB
  por mês (mín/máx/média), xml → clientes por agência, logs → eventos
  por status/tipo; formato sem regra cai num resumo genérico.
- Pipeline com fontes reais: `csv` ← Kaggle (5.389 linhas) e `json` ←
  BCB (série diária) via fetch; `xml`/`logs` ← fixtures. Arquivo real
  ausente → erro com o comando de fetch correspondente.
- Amostras pequenas e intencionais: JSON com 1 `valor` nulo (removido por
  `clean`), logs com 1 `failed` (status de negócio legítimo, mantido).

## Decisões

- pandas na etapa 1 (volume pequeno); PySpark entra quando a gold exigir.
- Parquet em `processed/` prepara migração para Delta.
- XML via stdlib para evitar dependência extra.
- `SPEC` é a fonte única da verdade: `EXPECTED_COLUMNS` é derivado dele,
  então transformação e checks nunca divergem do contrato.
- Gold em pandas com um agregador por formato (registro `AGGREGATORS`);
  a chave `data` do BCB é parseada **só aqui**, com formato explícito
  `%d/%m/%Y` — sem ambiguidade de dayfirst.
- Regras de negócio (faixa/enum/frescor) vivem no **mesmo `SPEC`** dos
  contratos — uma fonte só; Pandera/Great Expectations ficam para o
  item 5 do roadmap (o núcleo não depende deles).

## Fontes de dados reais (fetch + ingestão concluídos)

Uma fonte por formato, escolhida conforme a natureza do dado, em vez de
forçar tudo pelo Kaggle:

| Formato | Fonte escolhida | Justificativa |
|---|---|---|
| CSV | Kaggle `pradeepkumar2424/usa-banking-transactions-dataset-2023-2024` (CC0, 5k linhas) | schema legível (id, data, amount, status); licença sem atrito |
| JSON | API pública **BCB SGS** (`api.bcb.gov.br`, sem credencial) | bate com o README ("payloads JSON de API"); exercita fetch de API real |
| LOG | fixture sintética (ou format-bridge CSV → linhas `k=v`) | o formato de log é da própria aplicação — não existe fonte pública equivalente |

Fetch (implementado):

- `scripts/fetch_json.py [--code N --start dd/mm/aaaa --end dd/mm/aaaa]`
  → `data/raw/json/bcb_sgs_{code}.json` via **stdlib** (urllib), validado
  como array não vazio. Sem datas, janela padrão de 90 dias (o BCB rejeita
  série diária sem janela — HTTP 406). Testado ao vivo.
- `scripts/fetch_kaggle.py [--slug owner/nome]` → **kaggle-api oficial**
  (>=2.2): credenciais checadas antes do import (`.env` carregado),
  `dataset_download_files(..., unzip=True)` em `data/raw/csv/`. Auth:
  `KAGGLE_USERNAME`+`KAGGLE_KEY` (legacy) ou `KAGGLE_API_TOKEN`, só em
  `.env`. Limite da 2.x: não expõe download por versão — o slug fixado
  no script é a âncora de reprodutibilidade.
- downloads ficam em `data/raw/{csv,json}/` e são gitignorados por
  padrão (`data/raw/csv/*` + exceção para a fixture); credenciais só
  em `.env`, nunca em logs; testes nunca dependem de rede.

Ingestão (concluída): `run_load` lê os arquivos reais — `SOURCES` nomeia
`Banking_Transactions_USA_2023_2024.csv` e `bcb_sgs_1.json` (ausentes →
erro apontando o fetch); o `SPEC` de `csv` (id/data/valor/status) e de
`json` (data/valor) foi reescrito para os schemas reais, e as fixtures
foram adaptadas aos mesmos schemas para manter os testes offline em
clone novo.

Decisão: `data` (BCB) fica como string `dd/mm/yyyy` — parsing sem formato
explícito é ambíguo (dayfirst); tratar junto com o achado A7
(timestamps/fuso). Loghub segue como opção futura só para o capítulo
"parser de log de sistema" (licença restrita a pesquisa — não é CC0).

## Disponibilização (opcional, implementada)

`scripts/load_postgres.py` replica `data/gold/` no **PostgreSQL local**
(`podman compose up -d`, imagem `postgres:16-alpine`) **só quando
`DATABASE_URL` existe** — sem o DSN ele avisa e sai com 0, e o pipeline
de arquivos (bem como os testes) nunca depende do banco.

- Carga em **full refresh** (TRUNCATE + INSERT) nas tabelas
  `gold.<fmt>_<tabela>`; DDL derivado dos dtypes pandas (`db.py`).
- Identificadores validados por regex (snake_case) antes de interpolar —
  sem SQL injetável vindo dos nomes de coluna.
- Testes: unitários de SQL/tipos/identificadores **sem banco** +
  roundtrip de integração com `skip` automático quando não há
  `DATABASE_URL`.

## Etapa 2 — DataOps (implementada)

- **CI** (`.github/workflows/ci.yml`): em push/PR para `main`, roda
  `uv sync --extra dev --frozen` (lockfile), `ruff check`,
  `ruff format --check` e `pytest --cov` com **serviço Postgres 16**
  efêmero — o roundtrip `gold → Postgres → SELECT` roda completo no CI
  sem segredo algum (credenciais de teste no workflow).
- **Lockfile**: `uv.lock` (85 pacotes) com `requires-python >=3.11`
  (piso exigido pelo `kaggle>=2.2`); `.python-version` fixa 3.12.
- **Lint**: `ruff` (regras E/F/I/UP/B, linha 100) sobre `src/`,
  `scripts/`, `tests/`; `notebooks/` fica de fora (células
  exploratórias).
- **A5**: `load_settings` avisa quando `.env` existe mas `python-dotenv`
  não está instalado; `SYNTHETIC_SEED` removido do `.env.example`
  (nunca teve uso no código).
- **Badge**: status do CI no topo do README.

## Futuro (não implementado)

PySpark/Delta sobre a gold quando o volume exigir, validação avançada
com Great Expectations/Pandera.
