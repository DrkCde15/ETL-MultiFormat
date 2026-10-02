# Revisão de Engenharia de Dados — multi-format-etl

**Data:** 2026-10-02  
**Escopo:** código em `src/`, `scripts/`, `tests/`, `data/`, configuração (`pyproject.toml`, `.gitignore`, `.env.example`), documentação (`README.md`, `docs/architecture.md`) e histórico git (2 commits). Rodei apenas `pytest` (local, não destrutivo); **não** executei `scripts/run_load.py`.  
**Maturidade assumida:** Estágio 1 — README declara "v0.1.0 — Etapa 1", propósito de portfólio/estudo ("Demonstrar capacidade", README.md:3-6), sem consumidor real declarado.

**Premissas:** (1) propósito = portfólio/estudo, não produção; (2) consumidor atual = ninguém (saída `processed/` é "base para" algo futuro, README.md:24); (3) dado 100% sintético. Se você discordar de alguma, refaça o scorecard com a nova premissa.

## Veredito

O projeto entrega exatamente o que promete — loaders por formato, `standardize()` e testes — com código modular, erros explícitos e reprocessamento idempotente. Porém **falha em um inegociável de qualquer estágio**: os dados de exemplo não estão no repositório (`.gitignore:19` ignora `data/` inteiro), então um clone fresco não roda nem o script nem os testes, contradizendo o README. As outras duas coisas que importam agora: a validação de schema declarada nunca é aplicada (schema drift passaria silencioso) e o `pytest` quebra no caminho de instalação alternativo que o próprio README oferece. Tudo isso são horas de trabalho, não semanas.

## Mapa do ciclo de vida

| Etapa do ciclo | Onde está no repo | Tecnologia | Observação |
|---|---|---|---|
| Geração (fontes) | `data/raw/{csv,json,xml,logs}/` — **não versionados** | amostras sintéticas fixas | sem contrato de schema ativo |
| Armazenamento | `data/raw` → `data/processed` → `data/curated` (local) | Parquet (pyarrow) | camadas decididas e documentadas (`docs/architecture.md`); saída gitignorada |
| Ingestão | `scripts/run_load.py` + `src/.../loaders/` | pandas batch | manual (sem scheduler); loga volume por formato |
| Transformação | `src/.../transformation/__init__.py` | `standardize()` | só padronização + proveniência (escopo proposital da etapa 1) |
| Disponibilização | `data/processed/*/data.parquet` | Parquet | nenhum consumidor, métrica ou frescor declarado |

## Scorecard

| Dimensão | Nota (0–3) | Esperado no estágio | Resumo em uma linha |
|---|---|---|---|
| Geração | 1 | 1–2 | fixtures locais sem dono, contrato ou recuperação pelo repo |
| Armazenamento | 2 | 1–2 | raw → processed → curated, Parquet colunar, saída não versionada |
| Ingestão | 2 | 1–2 | batch idempotente com `LoadError` e log de volume; sem validação de entrada |
| Transformação | 2 | 1–2 | função pura testada; escopo mínimo declarado e respeitado |
| Disponibilização | 1 | 1 | parquet local sem consumidor/frescor (aceitável neste estágio) |
| Segurança e privacidade | 2 | 1–2 | zero segredos no repo/histórico, `.env` ignorado, dado fictício declarado |
| Gerenciamento de dados | 1 | 1–2 | README/docs bons, mas metadados contradizem o gitignore e o contrato é órfão |
| DataOps | 1 | 1 | testes existem; sem CI, lint, monitoramento ou alerta |
| Arquitetura | 2 | 1–2 | decisões documentadas (`docs/architecture.md:12-16`), sem over-engineering, sem ADR formal |
| Orquestração | 1 | 1 | CLI manual; correto para o estágio, mas sem DAG/retry/backfill |
| Engenharia de software | 2 | 1–2 | modular, configurável, testada; sem lockfile, linter e `pythonpath` no pytest |

## Pontos fortes verificados

- **Idempotência real:** `df.to_parquet(out, index=False)` sobrescreve (`scripts/run_load.py:42`) — reexecutar não duplica. Nenhum `append`/`insert` no código.
- **Falha barulhenta:** `LoadError` com causa encadeada (`src/multi_format_etl/loaders/csv_loader.py:10-21`); o CLI loga erro, retorna exit 1 e reporta linhas ingeridas por formato (`scripts/run_load.py:38-43`).
- **Transformação como função pura** com proveniência (`_source_format`, `_source_file`) em `src/multi_format_etl/transformation/__init__.py:12-18`.
- **Escala de tecnologia certa:** pandas + Parquet para volume minúsculo, Spark adiado como decisão explícita (`docs/architecture.md:14-15`) — exatamente o "não construa para a escala que não existe".
- **6 testes passando** (verificado com `PYTHONPATH=src pytest`), cobrindo os 4 loaders, falha por arquivo ausente e o contrato de proveniência.

## Achados

### A1 — Dados brutos não versionados; README e `.gitignore` se contradizem — Alta · Esforço P
- **Local:** `.gitignore:18-19`, `README.md:41`
- **Status:** verificado
- **Evidência:** `.gitignore:19` ignora `data/` inteiro; `git ls-files data/` retorna 0 arquivos; o comentário da linha 18 ("raw de exemplo é versionado") e o README ("amostras versionadas") dizem o contrário. `tests/test_loaders.py:15-16` e `scripts/run_load.py:34` dependem desses arquivos.
- **Por que importa:** quebra o inegociável 5 (outra pessoa roda pelo README) e o 3 (o bruto só existe na máquina do autor — se a máquina sumir, as amostras se perdem). Reprodutibilidade é o mínimo para portfólio.
- **Como corrigir:** em `.gitignore`, trocar `data/` por `data/processed/` + `data/curated/`, e commitar as 4 amostras (~36 KB).

### A2 — Contrato de schema declarado mas nunca aplicado — Média · Esforço P
- **Local:** `src/multi_format_etl/validation/__init__.py:3`; aplicação em `scripts/run_load.py:36` (ausente)
- **Status:** verificado (grep: `EXPECTED_COLUMNS` tem zero referências fora da definição)
- **Evidência:** `run_load.py:36` chama `standardize(loader(...))` sem checar colunas; `README.md:47` descreve o módulo como se fizesse parte do fluxo.
- **Por que importa:** é o erro silencioso clássico da etapa de ingestão (cap. 7): a fonte renomeia/ remove uma coluna e o Parquet sai "válido" com dado errado, sem alarme.
- **Como corrigir:** aplicar a checagem de presença antes de gravar (falta → `LoadError` com colunas faltantes) — ou apagar o módulo até houver aplicação, para código não mentir.

### A3 — `pytest` quebra no caminho de instalação alternativo do README — Média · Esforço P
- **Local:** `pyproject.toml:25-27` (só `testpaths`/`addopts`, sem `pythonpath`)
- **Status:** verificado — reproduzi: venv montado só com `requirements.txt` → `ModuleNotFoundError: No module named 'multi_format_etl'`; com `PYTHONPATH=src` → `6 passed`.
- **Por que importa:** `README.md:58` oferece `uv pip install -r requirements.txt` como alternativa, e esse caminho não instala o pacote → coleta de testes falha. Falha visível, não silenciosa, mas frustra o primeiro contato.
- **Como corrigir:** adicionar `pythonpath = ["src"]` em `[tool.pytest.ini_options]` (pytest ≥ 7 nativo).

### A4 — Nenhum CI nem linter — Baixa · Esforço P
- **Local:** pasta `.github/` ausente; nenhum `ruff`/`mypy`/`pre-commit` em `pyproject.toml`/`requirements.txt`
- **Status:** inferido (ausência verificada)
- **Evidência:** `ls -a` sem `.github`, sem `.pre-commit-config.yaml`; grep de ferramentas de lint sem hit.
- **Por que importa:** DataOps (cap. 2); no estágio 1 nota 1 é aceitável, mas sem CI os testes só rodam se alguém lembrar.
- **Como corrigir:** GitHub Actions com `uv sync` + `pytest` + `ruff check` (~10 linhas).

### A5 — dotenv ausente é engolido em silêncio; `SYNTHETIC_SEED` é configuração fantasma — Baixa · Esforço P
- **Local:** `src/multi_format_etl/config.py:50-51`; `.env.example:5`
- **Status:** verificado — `SYNTHETIC_SEED` tem zero usos no código.
- **Evidência:** `except ImportError: pass` faz o projeto rodar sem `python-dotenv` e sem avisar; quem tiver `.env` com diretórios customizados e instalar sem o pacote ganha silenciosamente os defaults.
- **Por que importa:** o inegociável 1 está garantido (`.env` no `.gitignore`), mas configuração que "parece valer e não vale" é erro de manutenção; `SYNTHETIC_SEED` promete reprodutibilidade que ninguém implementou.
- **Como corrigir:** logar um warning quando `.env` existir e o dotenv não carregar; remover `SYNTHETIC_SEED` do `.env.example` ou usá-lo num script de geração de amostras.

### A6 — Dependências sem lockfile — Baixa · Esforço P
- **Local:** `requirements.txt` (só lower bounds `>=`)
- **Status:** verificado
- **Evidência:** sem `uv.lock`/`requirements.lock`; o venv atual já diverge do declarado (python-dotenv 1.2.4 vs `>=1.0`).
- **Por que importa:** engenharia de software (cap. 2): "no meu venv passa" deixa de ser reprodutível com o tempo.
- **Como corrigir:** `uv pip compile requirements.txt -o requirements.lock` (ou `uv lock` se migrar para `uv sync`).

### A7 — Timestamps de origem sem fuso horário — Info · Esforço P
- **Local:** `data/raw/csv/transactions.csv:2` (`2024-06-01T10:00:00` sem offset), `src/multi_format_etl/loaders/log_loader.py:21`
- **Status:** verificado
- **Evidência:** formatos ISO sem `Z`/offset; o log loader mantém o timestamp como string crua.
- **Por que importa:** semântica de tempo (cap. 5) — evento × ingestão × processamento indistinguíveis. Hoje é inofensivo (dado sintético, sem janelas), mas vira problema na primeira agregação temporal.
- **Como corrigir:** documentar no README que timestamps são "hora local sem fuso" e tratar na etapa de limpeza.

## Roadmap

1. **Agora** — A1 versionar `data/raw/` (P) · A3 `pythonpath = ["src"]` (P) · A2 aplicar ou remover `EXPECTED_COLUMNS` (P). Todos cabeçalho de um PR só.
2. **Em seguida** — A4 GitHub Actions com pytest + ruff; A6 lockfile; A5 limpeza do `.env.example`; testes de `run_load` end-to-end e do parser de log malformado — é o que leva o projeto ao estágio 2 (DataOps formalizado).
3. **Deliberadamente adiado** — Airflow/Dagster (não há produção nem frequência a orquestrar), Spark além do extra (volume cabe em memória por 4 ordens de grandeza), Pandera/Great Expectations (a checagem de colunas do A2 cobre o risco atual), particionamento e catálogo (over-engineering neste estágio — cap. 4, custo de manutenção vs. valor).

## O que esta análise não cobriu

Produção e volumes reais (não existe em produção), custos, permissões na nuvem (não há nuvem), qualidade real dos dados (só vi amostras sintéticas), e o que vive fora do repositório (ex.: histórico do GitHub além dos commits locais, se houver mais no remoto). A análise é estática: não executei o pipeline nem validei saída do Parquet. Nenhum segredo ou dado pessoal real foi encontrado no repo ou histórico (scan dos commits limpo; `full_name` no XML é fictício, declarado no próprio arquivo `data/raw/xml/customers.xml:2`).

## Perguntas em aberto

1. **As amostras sintéticas são permanentes ou haverá extração de uma fonte real?** Se houver fonte real, A1 e A2 sobem de prioridade e o contrato de schema vira obrigatório.
2. **Existe (ou vai existir) consumidor para `processed/`?** Sem consumidor, Disponibilização fica 1 por definição — e está correto assim.
3. **O alvo continua sendo estágio 1, ou você quer levar a portfólio para estágio 2?** Se estágio 2, DataOps esperado sobe de 1 para 2 e A4 deixa de ser "Baixa" para prioridade real.
