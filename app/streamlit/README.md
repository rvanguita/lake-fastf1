# Lake FastF1 · Paddock (Streamlit)

Dashboard em tema escuro que apresenta os dados produzidos pelo pipeline: os marts do
Silver, a ABT, o catálogo Delta e o modelo publicado na API.

| Página | Conteúdo |
|---|---|
| **Temporada** (`/`) | KPIs, disputa pelo título (pontos ou posição por rodada), classificação de pilotos com forma recente, construtores e resultado de cada GP |
| **Pilotos** (`/pilotos`) | Temporada do piloto, corrida a corrida (grid → chegada), duelo com o companheiro, forma nas janelas 5–50 do Silver e carreira no lake |
| **Previsão e modelo** (`/previsao`) | Chances de título com faixa p10–p90, evolução na temporada, explicação SHAP, importância global e model card |
| **Dados do lake** (`/dados`) | Linhagem, catálogo das tabelas Delta, regras de qualidade dos marts e cobertura por temporada |

Links reproduzem a visão: `?ano=2021` escolhe a temporada e `/pilotos?piloto=Lewis+Hamilton`
abre um piloto (o parâmetro usa o nome exibido).

## Executar

```bash
cd app/streamlit
uv sync --locked
uv run streamlit run main.py        # http://localhost:8501
```

| Variável | Padrão local | Uso |
|---|---|---|
| `LAKE_ROOT` | `<repo>/data` | Raiz com `raw/`, `bronze/` e `silver/` |
| `API_URL` | `http://localhost:5002` | API de previsão (só a página Previsão usa) |

No Compose (`docker compose up --build -d streamlit`), `data/` é montada somente leitura em
`/data` e a API é `http://api-driver-champion:5002`. `/_stcore/health` responde ao healthcheck.
A imagem instala exatamente o `uv.lock`.

## Estrutura

```
main.py          navegação (st.navigation), seletor de temporada ligado a ?ano=
views/           temporada.py · pilotos.py · previsao.py · dados.py
lake.py          leitura Delta projetada/filtrada, cache por versão (TTL 60 s), catálogo
model_api.py     cliente da API; só respostas válidas entram em cache
metrics.py       pandas puro: classificação, duelos, carreira, candidatos, qualidade
charts.py        template Plotly escuro e figuras
ui.py, fmt.py    blocos de interface e formatação pt-BR
.streamlit/      tema e configuração do servidor
```

## Definições

- **Pontos** somam Race e Sprint (`mart_standings`); vitórias, pódios, poles e abandonos
  vêm da corrida principal (`mart_driver_round`). A classificação é reconstruída dos
  resultados no lake e não substitui o resultado oficial.
- **Forma** na tabela: pontos por rodada nas últimas 5 rodadas.
- **Duelo com o companheiro**: corridas em que dividiram a equipe; "à frente na corrida" usa
  a ordem de resultado, "no grid" só conta corridas em que ambos tiveram posição de largada.
- **Carreira**: temporadas do piloto nos marts (1980 em diante). Temporadas parciais no lake
  (menos de 75% da mediana de corridas) aparecem marcadas. `driver_statistic_life` não é
  usada: é uma janela legada, fora do DAG.
- **Janelas do Silver**: métricas `*_5 … *_50` da ABT na data de referência mais recente
  (sessões Race + Sprint).
- **Previsão**: candidatos são os pilotos que já estrearam na temporada até cada data da ABT;
  temporadas passadas são simulações com o modelo atual. Se a API falhar, a página mostra o
  motivo e as outras páginas seguem funcionando.
- **Cores**: cor da equipe clareada até 3:1 de contraste; companheiro com traço pontilhado;
  sem cor na fonte (anos antigos), cada piloto recebe um slot fixo da paleta validada.

## Testes

```bash
uv run --locked pytest -q
```

Um mini-lake Delta coerente é escrito em `tmp_path` e apontado por `LAKE_ROOT`. Os testes
cobrem `metrics`, `lake`, `model_api`, os gráficos e cada página via
`streamlit.testing.v1.AppTest`, com a API simulada (online e fora do ar).
