# Lake FastF1

[![tests](https://github.com/rvanguita/lake-fastf1/actions/workflows/tests.yml/badge.svg)](https://github.com/rvanguita/lake-fastf1/actions/workflows/tests.yml)

Uma plataforma de dados e machine learning para transformar resultados históricos da Fórmula 1 em um lakehouse confiável, análises interativas e probabilidades transparentes para o campeonato de pilotos.

O Lake FastF1 foi construído como um projeto de engenharia de dados ponta a ponta. Ele coleta dados da [FastF1](https://docs.fastf1.dev/), persiste os arquivos brutos, organiza tabelas Delta em camadas, materializa datasets analíticos, treina um modelo temporalmente seguro e publica os resultados por uma API e um dashboard.

## O que o projeto entrega

- **Pipeline de dados:** ingestão por temporada e sessão, consolidação em Parquet/Delta e transformações Spark SQL.
- **Lakehouse local:** camadas Raw, Bronze e Silver com tabelas de resultados, estatísticas, features de treino e marts analíticos.
- **Modelo preditivo:** estimativa calibrada da probabilidade de cada piloto vencer o campeonato.
- **Transparência:** backtests rolling-origin, baseline de pontos recentes, model card, explicações SHAP e intervalos de dispersão do ensemble.
- **Produtos analíticos:** Streamlit Paddock com temporada, pilotos, previsão e dados do lake; Dash / Race Control com leitura rápida de temporada, corridas, previsão e eras.
- **Integrações:** Airflow para orquestração, MLflow para tracking/registry, FastAPI para serving, MySQL para espelho analítico e S3 para arquivamento opcional.

## Arquitetura e fluxo do projeto

O fluxo principal é semanal e é orquestrado pelo DAG `data-pipeline`, agendado para segunda-feira à 00:00 UTC, sem catch-up e com no máximo uma execução ativa.

![Arquitetura do Lake FastF1: fluxo medalhão FastF1 → Raw → Bronze → Silver orquestrado pelo DAG data-pipeline no Airflow, o treino temporal registrado no MLflow, o serving em FastAPI e Streamlit, e o espelho MySQL com o arquivo Raw em Amazon S3](docs/arquitetura.svg)

```mermaid
flowchart LR
    source[(FastF1)] --> extract[ExtractData\npor temporada/sessão]
    extract --> raw[(Raw\nParquet)]

    subgraph orchestration[Airflow · data-pipeline]
        bronze_task[Consolidação Spark]
        silver_task[Transformações Silver]
        mysql_task[Espelho MySQL]
    end

    raw --> bronze_task
    bronze_task --> bronze[(Bronze\nDelta: results)]
    bronze --> silver_task

    subgraph silver[Silver · Delta Lake]
        champions[(champions)]
        windows[(driver_statistic_5/10/20/40/50)]
        consolidated[(driver_all_statistic)]
        abt[(tb_abt\nfeatures do modelo)]
        marts[(mart_driver_round\nmart_standings)]
    end

    silver_task --> champions
    silver_task --> windows
    windows --> consolidated
    champions --> abt
    consolidated --> abt
    silver_task --> marts

    bronze --> mysql_task
    champions --> mysql_task
    consolidated --> mysql_task
    abt --> mysql_task
    marts --> mysql_task
    mysql_task --> mysql[(MySQL\nespelho para BI)]

    raw -. envio manual opcional .-> s3[(Amazon S3)]

    abt --> train[Treino temporal\nsrc/train_driver_champion.py]
    train --> mlflow[(MLflow\ntracking + registry)]
    mlflow --> api[FastAPI\n/v1/predict\n/v1/explain\n/v1/model-card]

    bronze --> dashboard[Streamlit\ndashboard analítico]
    marts --> dashboard
    abt --> dashboard
    api --> dashboard
    bronze --> dash[Dash · Race Control]
    abt --> dash
    api --> dash
```

### Fluxo em seis etapas

1. **Extração:** `src/extract_data.py` consulta sessões Race e Sprint da FastF1 e grava cada resultado como Parquet em `PATH_RAW`.
2. **Bronze:** `src/spark_session.py` consolida os Parquets em uma tabela Delta de resultados históricos.
3. **Silver:** `src/silver_data.py` executa as consultas em `src/queries/` e produz campeões, janelas móveis de estatísticas, a tabela consolidada de features, `tb_abt` e os marts analíticos.
4. **Consumo externo:** a tarefa `sender_mysql` replica Bronze e Silver para MySQL. O envio dos arquivos Raw para S3 é independente, manual e opcional.
5. **Treinamento:** `src/train_driver_champion.py` lê `tb_abt`, exclui a temporada corrente, executa backtests cronológicos, calibra o modelo e registra o artefato e o model card no MLflow.
6. **Serving e análise:** a FastAPI carrega o modelo registrado; o Streamlit lê os marts e a ABT do Silver e combina esses dados com previsões, explicações e metadados do modelo.

## Camadas de dados

| Camada | Formato | Responsabilidade | Principais saídas |
|---|---|---|---|
| Raw | Parquet | Preservar os resultados retornados pela FastF1 por sessão | `data/raw/results` |
| Bronze | Delta Lake | Consolidar o histórico e oferecer uma fonte física única para transformações | `data/bronze/results` |
| Silver | Delta Lake | Aplicar regras analíticas, features e contratos de qualidade | `champions`, `driver_*`, `tb_abt`, `mart_*` |
| Espelho | MySQL | Disponibilizar Bronze/Silver para consumidores externos e BI | tabelas do schema configurado |

Os grãos, chaves, domínios e expectativas de qualidade dos marts estão documentados no [contrato de dados analíticos](docs/analytics-data-contract.md).

## Produto analítico

O Streamlit **Paddock** (tema escuro) apresenta os dados que o pipeline produz, em quatro
páginas. A temporada escolhida na barra lateral vale para todas e fica na URL (`?ano=2024`).

| Página | Pergunta respondida | Conteúdo |
|---|---|---|
| **Temporada** | Como está o campeonato? | KPIs, disputa pelo título (pontos ou posição por rodada), classificação de pilotos com forma recente, construtores e resultado de cada GP |
| **Pilotos** | Como foi a temporada e a carreira de um piloto? | Corrida a corrida (grid → chegada), duelo com o companheiro, forma nas janelas do Silver e carreira no lake desde 1980 (`?piloto=`) |
| **Previsão e modelo** | O que o modelo espera e por quê? | Chances de título com faixa p10–p90, evolução na temporada, explicação SHAP por piloto, importância global e model card |
| **Dados do lake** | O que existe no lake e está íntegro? | Linhagem, catálogo Delta (versão, linhas, última escrita), regras de qualidade dos marts e cobertura por temporada |

As leituras Delta usam projeção de colunas e filtros, com cache pela versão da tabela. Só a
página de previsão chama a API; se ela estiver fora, as demais continuam funcionando.

### Regras analíticas importantes

- Pontos incluem Race e Sprint; vitórias e pódios consideram a corrida principal.
- DNF, DNS, DNQ, DSQ e NC permanecem categorias explícitas.
- Grid zero representa pit lane e não entra no cálculo de médias de posição.
- Trocas de equipe não duplicam um piloto na classificação da temporada.
- Rodadas sem participação preservam os pontos acumulados anteriores.
- Probabilidades de um mesmo snapshot são normalizadas entre os candidatos e somam 100% dentro da tolerância definida pela API.

### Segunda interface: Dash / Race Control

O [Race Control em Dash](app/dash/README.md) é uma leitura rápida e independente do
Streamlit, com quatro páginas que começam pelos **achados** calculados dos dados:
**Temporada** (distância para o líder e de onde vêm os pontos), **Corridas** (margem
de vitória e detalhe de cada etapa), **Previsão** (chance do modelo × pontos na mesma
data) e **Eras** (tendências desde 1980 e motivos de abandono por década). O estado
fica na URL (`/corridas?ano=2024`), então qualquer visão pode ser compartilhada. Lê
Bronze e ABT diretamente; apenas a página de previsão consulta a API.

```bash
uv run --project app/dash python app/dash/main.py
# http://localhost:8050
```

A classificação é reconstruída dos pontos das sessões e é apresentada como “líder
em pontos”, não como título oficial. Previsões de datas passadas aparecem como
simulações com o modelo publicado hoje.

## Modelo preditivo

O alvo do modelo é identificar o campeão de pilotos a partir das informações disponíveis em cada data de referência.

- A temporada em andamento nunca entra nos rótulos de treinamento.
- O universo de candidatos contém apenas pilotos que já participaram da temporada analisada.
- O backtest usa validação **rolling-origin**: cada temporada é avaliada somente com dados de temporadas anteriores.
- O estimador combina imputação constante, Random Forest e calibração sigmoide aprendida no último ano concluído.
- O model card registra acerto do campeão, ROC-AUC, Brier score, log loss, baseline e curva de calibração.
- O modelo permanece `experimental` quando não supera o baseline configurado.
- A explicação individual usa SHAP; importância global e contribuições locais são apresentadas separadamente.

Os limites retornados pela API representam a dispersão entre membros do ensemble. Eles não são garantia estatística nem intervalo causal de confiança.

## Tecnologias

| Responsabilidade | Tecnologias |
|---|---|
| Fonte e processamento | FastF1, Pandas, NumPy, PySpark |
| Armazenamento | Parquet, Delta Lake |
| Orquestração e lineage | Apache Airflow |
| Modelagem e explicabilidade | scikit-learn, SHAP |
| Tracking e registry | MLflow |
| API | FastAPI, Uvicorn |
| Produto analítico | Streamlit, Dash, Plotly |
| Consumo externo | MySQL, Amazon S3 |
| Ambiente | uv, Docker, Docker Compose |

## Execução local

### Pré-requisitos

- Docker com Docker Compose;
- Python 3.13+ e `uv` para executar os comandos locais;
- Java 17 para Spark/Delta;
- um arquivo `.env` criado a partir de `.env.example`;
- dados Delta materializados para executar o dashboard;
- um servidor MLflow acessível para habilitar previsões.

### Subir os serviços

```bash
cp .env.example .env
docker compose up --build -d
```

O Compose sobe Airflow, FastAPI, Streamlit e Dash. MLflow, MySQL e S3 são integrações externas e precisam ser configurados pelas variáveis de ambiente.

| Serviço | Endereço |
|---|---|
| Airflow | <http://localhost:8080> |
| FastAPI | <http://localhost:5002> |
| OpenAPI | <http://localhost:5002/docs> |
| Streamlit | <http://localhost:8501> |
| Dash / Race Control | <http://localhost:8050> |

Em containers, `MLFLOW_URI` deve apontar para um endereço acessível pela rede Docker. `localhost` dentro da API aponta para o próprio container da API.

### Executar as etapas manualmente

```bash
uv run python -m src.extract_data
uv run python -m src.spark_session
uv run python -m src.silver_data
uv run python -m src.train_driver_champion
```

O DAG do Airflow executa o caminho de ingestão, Bronze, Silver e MySQL. O comando de treinamento continua separado para permitir reprocessamento e experimentação sem acoplar o treino ao ciclo de ingestão.

### Configuração

| Grupo | Variáveis principais |
|---|---|
| Lake | `PATH_RAW`, `PATH_BRONZE`, `PATH_SILVER`, `PATH_QUERIES` |
| MLflow | `MLFLOW_URI`, `MLFLOW_MODEL_REGISTERED`, `MLFLOW_EXPERIMENT_NAME` |
| Serviços | `AIRFLOW_PORT`, `AIRFLOW_UID`, `API_PORT`, `API_URL`, `STREAMLIT_PORT`, `DASH_PORT` |
| MySQL | `MYSQL_HOST`, `MYSQL_PORT`, `MYSQL_ID_TABLE`, `MYSQL_USER`, `MYSQL_PASSWORD` |
| S3 opcional | `AWS_KEY`, `AWS_SECRET_KEY`, `REGION_NAME` |

Consulte o [.env.example](.env.example) para os valores esperados. No Compose, o Streamlit lê o lake em `LAKE_ROOT=/data` (a pasta `data/` montada somente leitura); o Dash usa os caminhos `TABLE_PATH_*` definidos no `docker-compose.yml`.

## API de previsões

| Método | Endpoint | Finalidade |
|---|---|---|
| `GET` | `/health_check` | Verificar disponibilidade do processo |
| `GET` | `/model_info` | Consultar features, classes e importâncias globais |
| `POST` | `/predict` | Contrato legado de probabilidades por classe |
| `POST` | `/v1/predict` | Retornar score, probabilidade e intervalos opcionais |
| `POST` | `/v1/explain` | Retornar contribuições SHAP por observação |
| `GET` | `/v1/model-card` | Expor backtests, calibração, corte de treino e limitações |

Exemplos básicos:

```bash
curl http://localhost:5002/health_check
curl http://localhost:5002/v1/model-card
```

`/v1/predict` recebe uma lista `values` contendo todas as features esperadas pelo modelo e um identificador `id`. O campo `include_intervals` é opcional e, por padrão, vale `true`:

```json
{
  "values": [
    {
      "id": "2026_10_driver_1",
      "prediction_group": "2026_10"
    }
  ],
  "include_intervals": false
}
```

O exemplo acima é apenas estrutural: as demais features devem ser obtidas a partir do schema do modelo publicado em `/model_info` ou `/docs`. Com `include_intervals=false`, a API não calcula os membros do ensemble e omite `lower` e `upper` da resposta.

## Qualidade, testes e performance

O projeto possui quatro ambientes `uv` independentes: raiz, API, Streamlit e Dash.

```bash
uv run pytest
(cd app/api && uv run pytest)
(cd app/streamlit && uv run --locked pytest)
(cd app/dash && uv run --locked pytest)
uv run ruff check .
uv run ruff format --check .
```

A suíte cobre ingestão, helpers Spark, envio MySQL/S3, contratos SQL, preparação temporal do modelo, endpoints da API, semântica analítica e contratos dos gráficos.

Para medir o benefício dos filtros sazonais nas leituras Delta:

```bash
uv run python scripts/benchmark_delta_reads.py
```

O benchmark compara leituras completas e filtradas por temporada, informando linhas, bytes materializados, tempo e proporção de I/O. Por padrão, ele sinaliza quando uma temporada ultrapassa 10% do volume da tabela completa.

## Estrutura do repositório

```text
lake-fastf1/
├── app/
│   ├── api/                  # previsão, explicações e model card
│   ├── dash/                 # Race Control: temporada, corridas, previsão e eras
│   └── streamlit/            # Paddock: views/ + lake, métricas, gráficos e cliente da API
├── dags/                     # DAG de ingestão e transformação
├── docs/                     # contratos e documentação complementar
├── scripts/                  # benchmarks e ferramentas de desenvolvimento
├── src/
│   ├── queries/              # SQL da camada Silver
│   ├── extract_data.py       # FastF1 → Raw
│   ├── spark_session.py      # Raw → Bronze
│   ├── silver_data.py        # Bronze → Silver
│   └── train_driver_champion.py
├── tests/                    # testes do pipeline e do treino
├── docker-compose.yml
└── pyproject.toml
```

## Limitações e próximos passos

- O dataset atual é orientado a resultados; telemetria, clima, pneus e tempos de volta ainda não fazem parte dos marts.
- Bronze e Silver são materializados por overwrite; processamento incremental completo ainda não está implementado.
- MLflow e MySQL não são provisionados pelo Compose atual.
- Comparações entre eras precisam considerar mudanças de regulamento, formato e pontuação.
- Próximas evoluções naturais incluem ingestão incremental, observabilidade operacional, novos sinais de corrida e uma demonstração online.

As probabilidades publicadas são estimativas experimentais e não constituem recomendação de aposta.
