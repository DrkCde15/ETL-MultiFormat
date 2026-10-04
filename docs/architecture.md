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
  csv → `by_status` + `by_month` (com taxa de fraude), json → série PTAX
  por mês (pregões, mín/máx/média da venda), xml → clientes por agência, logs → eventos
  por status/tipo; formato sem regra cai num resumo genérico.
- Pipeline com fontes reais: `csv` ← Kaggle (5.389 linhas) e `json` ←
  BCB PTAX (série diária, 1.446 registros) via fetch; `xml`/`logs` ← fixtures. Arquivo real
  ausente → erro com o comando de fetch correspondente.
- Amostras pequenas e intencionais: JSON com 1 `cotacaoVenda` nula (removida
  por `clean`), logs com 1 `failed` (status de negócio legítimo, mantido).

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
| JSON | API pública **BCB PTAX** (`olinda.bcb.gov.br`, sem credencial) | bate com o README ("payloads JSON de API"); exercita fetch de API real; mesmo BCB da série SGS original |
| LOG | fixture sintética (ou format-bridge CSV → linhas `k=v`) | o formato de log é da própria aplicação — não existe fonte pública equivalente |

Fetch (implementado):

- `scripts/fetch_json.py [--start dd/mm/aaaa --end dd/mm/aaaa] [--full]`
  → `data/raw/json/bcb_ptax_usd.json` via **stdlib** (urllib): endpoint
  OData `CotacaoDolarPeriodo` (datas dd/mm/yyyy da API pública viram
  MM-DD-YYYY), envelope `{"value": [...]}` validado como lista não vazia
  antes de gravar. **Incremental por padrão**: sem datas, busca de
  (última cotação + 1 dia) até hoje e mescla deduplicando por
  `dataHoraCotacao` — a série nunca encolhe (bug de overwrite corrigido
  em 04/10/2026, quando uma run de 90 dias rebaixou 1.446 → 64
  registros); arquivo ausente (clone novo) cai na janela de 90 dias;
  janela sem registros novos mantém o arquivo como está (fim de semana
  não é erro). `--full` regrava a janela pedida sem mesclar. Resposta
  vazia sem histórico, HTTP ou JSON inválido continuam `FetchError`
  (fail-fast). Testado ao vivo (1.446 registros para 2021→2026).
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
`Banking_Transactions_USA_2023_2024.csv` e `bcb_ptax_usd.json` (ausentes →
erro apontando o fetch); o `SPEC` de `csv` (id/data/amount/status) e de
`json` (datahora/compra/venda) foi reescrito para os schemas reais — o
payload PTAX vem em camelCase e o `rename` do SPEC o mapeia para os
nomes canônicos no `standardize` —, e as fixtures foram adaptadas aos
mesmos schemas para manter os testes offline em clone novo.

Decisão (revisada): com a migração para a PTAX, `datahora` chega em ISO
não ambíguo (`YYYY-MM-DD HH:MM:SS.fff`) — temporal e frescor habilitados
no `SPEC` de `json`, encerrando o adiamento de parsing do antigo `data`
da série SGS. O timestamp segue naïve (fuso do achado A7 adiado).
Loghub segue como opção futura só para o capítulo
"parser de log de sistema" (licença restrita a pesquisa — não é CC0).

## Disponibilização (opcional, implementada)

`scripts/load_postgres.py` replica `data/gold/` no **PostgreSQL local**
(`podman compose up -d`, imagem `postgres:16-alpine`) **só quando
`DATABASE_URL` existe** — sem o DSN ele avisa e sai com 0, e o pipeline
de arquivos (bem como os testes) nunca depende do banco.

- Carga em **full refresh** (DROP + CREATE + INSERT — o DDL vem dos
  dtypes pandas, então mudança de schema recria a tabela) nas tabelas
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

## Etapa 3 — Orquestração (implementada)

- **DAG** `multi_format_etl` (`dags/multi_format_etl_dag.py`): encadeia
  `extract >> transform >> load` (fetch PTAX → run_load →
  load_postgres) — as tasks são **os scripts
  já existentes** (BashOperator), sem retrabalho nem lógica nova na
  orquestração. Agendamento `0 6 * * *` (06:00 UTC), `catchup=False`,
  `max_active_runs=1`, `retries=1` (10 min).
- **Container próprio**: `Dockerfile.airflow` parte de
  `apache/airflow:2.6.3-python3.11` e instala o projeto com
  `pip install .` **alinhado às constraints oficiais** do Airflow
  (constraints-2.6.3/3.11, com pandas/pyarrow elevados para os floors
  do projeto: 2.2.3/14.0.1). A imagem 2.6 instala o Airflow no
  site-packages do usuário `airflow` e traz `PIP_USER=true`: um `.pth`
  expõe esse diretório no sys.path do sistema e o build roda sem
  `PIP_USER`, senão o compose (uid 1000 + HOME em `.airflow/`) não
  importaria airflow e o projeto cairia em `/root/.local`.
  `.dockerignore` mantém `.venv`/`data`/`.git` fora do build context.
- **compose** (`serviço airflow`): monta o projeto inteiro
  (`./:/opt/airflow/project`), `AIRFLOW_HOME` em `.airflow/`
  (gitignorado — logs fora do Git), `dags_folder` apontando
  para `dags/`, `DATABASE_URL` apontando para o serviço `db`, porta
  8080 (usuário `admin`/`admin` criado no comando de start — sem ele,
  o standalone criaria o admin com senha aleatória). uid do host com
  **GID 0** — exigência do entrypoint oficial da imagem.
- **Executor + metadados**: `LocalExecutor` com metadados no **Postgres**
  (banco `airflow` criado por
  `docker-entrypoint-initdb.d/01-airflow-db.sql` na primeira subida do
  serviço `db`) — os avisos de "não use SQLite/SequentialExecutor em
  produção" sumiram da UI; para outro ambiente, a troca segue sendo só
  de DSN/executor.
- **Fail-fast na fonte** (decisão explícita): se a API do BCB estiver
  indisponível, `extract` falha e a run fica vermelha (retry único) —
  sem fallback silencioso para snapshot antigo. No modo incremental,
  só a resposta vazia *sem histórico* local é erro; janela sem registros
  novos (fim de semana/feriado) mantém o arquivo e segue para
  `transform`. Valeu na prática:
  em 03/10/2026 o BCB removeu `api.bcb.gov.br` do DNS (NXDOMAIN
  confirmado no servidor autoritativo) e a DAG sinalizou exatamente
  assim. A fonte foi migrada para a PTAX no `olinda.bcb.gov.br` (mesmo
  BCB, série equivalente de câmbio) — decisão de migrar, não de contornar
  o fail-fast.
- **Compatibilidade pandas 2/3**: `clean()` testa
  `is_object_dtype`/`is_string_dtype` por coluna (sem `select_dtypes`),
  cobrindo o pandas 3 do host e o 2.2.3 do container.
- **Validação ao vivo**: build + `up`, `/health` 200, login
  `admin`/`admin` (inclusive após restart do container), DAG listada e
  `tasks test` de `transform` (6.842 linhas, quality `passed`) e
  `load` (6 tabelas) verdes dentro do container; os avisos de
  SQLite/SequentialExecutor sumiram da UI com Postgres + LocalExecutor;
  com a PTAX como fonte, o fetch volta a responder e a DAG completa
  fecha em verde de ponta a ponta.

## Futuro (não implementado)

PySpark/Delta sobre a gold quando o volume exigir, validação avançada
com Great Expectations/Pandera.
