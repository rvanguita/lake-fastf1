# Race Control · Dash

Leitura rápida dos resultados de F1 do Lake FastF1, independente do Streamlit.
Cada página começa pelos **achados** (frases calculadas a partir dos dados), depois
KPIs, um ou dois gráficos e, recolhida, a tabela completa.

| Página | Pergunta | Conteúdo |
|---|---|---|
| **Temporada** `/` | Como está a disputa? | Distância para o líder rodada a rodada (alterna para pontos acumulados), composição dos pontos (pódios, demais corridas, sprints) e classificação |
| **Corridas** `/corridas` | Como as vitórias aconteceram? | Margem de vitória por etapa; clique numa barra para ver o resultado com diferença para o vencedor, grid, ± posições e motivo de abandono |
| **Previsão** `/previsao` | O modelo concorda com a tabela? | Chance de título × pontos na mesma data, lista de chances, contexto do modelo e classificação na data |
| **Eras** `/eras` | O que mudou na F1? | Vencedores diferentes, vitórias da pole e abandonos por temporada; motivos de abandono por década |

## Executar

```bash
uv sync --project app/dash
uv run --project app/dash python app/dash/main.py   # http://localhost:8050
```

A aplicação lê o `.env` da raiz sem sobrescrever variáveis exportadas. Com Docker:
`docker compose up --build -d dash` (Gunicorn, dados montados só para leitura, sem
Spark/Java). `/healthz` confirma o processo, não a prontidão das fontes.

| Variável | Padrão local | Uso |
|---|---|---|
| `DASH_PORT` | `8050` | Porta local ou publicada pelo Compose |
| `DASH_HOST` | `127.0.0.1` | Bind do servidor de desenvolvimento |
| `TABLE_PATH_BRONZE` | `<raiz>/data/bronze/results` | Delta de resultados |
| `TABLE_PATH_SILVER` | `<raiz>/data/silver/tb_abt` | Delta de features (ABT) |
| `API_URL` | `http://localhost:5002` | API de previsão |

## Arquitetura

```
main.py          Dash Pages, shell (topo + navegação), callback de ano → URL, /healthz
pages/           temporada, corridas, previsao, eras: layout(**query) + callbacks da página
analytics.py     pandas puro: limpeza do Bronze, classificação, achados, eras
figures.py       template Plotly "race_control" e as figuras
components.py    achados, KPIs, painéis, tabelas com barras, avisos
repository.py    leituras Delta projetadas e cliente da API
formatting.py    números, tempos e datas em pt-BR
```

- **A URL é o estado.** `?ano=2024` e `?de=1990&ate=2010` renderizam a página no
  servidor; trocar o seletor escreve a URL, o que dá links compartilháveis e
  voltar/avançar do navegador.
- **Callbacks pequenos.** A alternância distância/acumulado é `clientside` (sem
  servidor); a seleção de etapa usa `Patch` para mudar só o contorno da barra; só a
  página Previsão chama a API, num callback isolado com carregamento próprio.
- **Cache por versão Delta.** Leituras e resultados preparados ficam em cache por
  processo, chaveados pela versão da tabela, verificada no máximo a cada 60 s.
  Funções de `analytics` não mutam a entrada; o repositório entrega cópias.
- **Leve.** Respostas com gzip (`dash[compress]`), poucas séries por gráfico e
  tabelas HTML quando o dado é tabular.
- A altura de cada gráfico vem do `style` do `dcc.Graph` (`responsive=True` ignora a
  altura da figura).

## Definições

- **Pontos** somam Race e Sprint; vitórias, pódios e largadas contam só a corrida
  principal. A classificação é reconstruída dos pontos das sessões, com empates na
  mesma posição, e aparece como **líder em pontos**, não como título oficial
  (não aplica descartes históricos nem punições de campeonato).
- **Distância para o líder**: pontos atrás de quem liderava *naquela* rodada.
  Ausência numa etapa mantém os pontos; o piloto aparece a partir da estreia.
- **Margem de vitória**: `Time` do 2º colocado quando ele terminou na mesma volta
  (no FastF1, `Time` do vencedor é o total e dos demais é a diferença). Sem isso, a
  etapa fica sem barra e é contada no subtítulo.
- **Abandono**: largou e o `Status` não indica conclusão (`Finished`, `Lapped`,
  `+N Lap(s)`); desclassificações ficam de fora. Um piloto pode ter posição
  classificada e ainda assim ter abandonado.
- **Motivo**: `analytics.classify_retirement` agrupa o texto de `Status` em *falha
  técnica*, *incidente de pista* (acidente, colisão, rodada, dano, pneu) e *sem motivo
  detalhado* (`Retired`, `Withdrew` e desconhecidos). A fonte recente usa muito
  `Retired`; o achado de Eras informa essa parcela quando passa de 25%.
- **Cobertura parcial**: temporadas com menos de 75% da mediana de corridas do
  recorte e a temporada em andamento aparecem com círculo vazado em Eras.
- **Previsão**: usa apenas features de `/model_info` e pilotos que já correram até a
  data escolhida; respostas parciais ou probabilidades que não somam 100% viram
  estado indisponível. Datas passadas são *simulações* com o modelo publicado hoje.
  Falhas mostram o motivo (API fora, modelo não registrado, contrato da ABT) e a
  classificação na data continua na tela.
- Cores de equipe vêm do Bronze e são clareadas até 3:1 de contraste com o fundo;
  companheiros de equipe diferem pelo traço. Sem cor na fonte, cada piloto recebe um
  slot fixo da paleta categórica validada.

## Testes

```bash
cd app/dash
uv run --locked pytest -q
```

Sem API, MLflow, Spark ou dados locais: `analytics` com uma fixture pequena (sprint,
transferência, ausência, pit lane, DNS, retardatário), Delta real em `tmp_path` para o
repositório (projeção, predicado, TTL de versão, contratos da API) e as páginas com um
repositório falso (renderização, estados vazios/erro, callbacks e rotas HTTP).
