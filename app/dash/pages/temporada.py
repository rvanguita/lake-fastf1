"""Temporada: a disputa por pontos em uma leitura rápida."""

from __future__ import annotations

import dash
from dash import Input, Output, State, clientside_callback, dcc, html

import analytics
import components as ui
import figures
import formatting as fmt
from repository import DataUnavailable, get_repository

dash.register_page(
    __name__, path="/", name="Temporada", title="Temporada · Race Control", order=0
)


def layout(ano=None, **_):
    repo = get_repository()
    try:
        seasons = repo.seasons()
        season, warning = ui.resolve_season(ano, seasons)
        if season is None:
            return ui.unavailable("Nenhuma temporada foi encontrada no Bronze.")
        frame = repo.results([season])
    except DataUnavailable as exc:
        return ui.unavailable(str(exc))
    return render(frame, season, seasons, warning)


def render(frame, season: int, seasons: list[int], warning: str | None = None):
    in_progress = season == analytics.current_year()
    header = ui.page_header(
        f"Temporada {season}",
        "Como está a disputa?",
        controls=ui.season_picker(seasons, season),
        meta=_coverage(frame, in_progress),
    )
    if frame.empty:
        return html.Div(
            [header, ui.notice("Sem resultados de Race ou Sprint nesta temporada.")],
            className="page",
        )
    table = analytics.driver_table(frame)
    progression = analytics.standings_progression(frame)
    race = frame[frame["session"].eq("Race")]
    leader = table.iloc[0]
    second = table.iloc[1] if len(table) > 1 else None
    winners = race.loc[race["win"], "driver_id"].nunique()
    charts = {
        metric: figures.championship(progression, table, metric=metric).to_dict()
        for metric in ("gap", "points")
    }
    return html.Div(
        [
            header,
            ui.notice(warning, kind="warning") if warning else None,
            ui.quality(frame),
            html.Div(
                [
                    ui.findings(
                        analytics.season_findings(frame, in_progress=in_progress)
                    ),
                    ui.kpis(
                        [
                            (
                                "Líder em pontos",
                                leader["driver"],
                                f"{fmt.points(leader['points'])} pts · {leader['team']}",
                            ),
                            (
                                "Vantagem",
                                fmt.points(leader["points"] - second["points"])
                                if second is not None
                                else "—",
                                f"sobre {second['driver']}"
                                if second is not None
                                else None,
                            ),
                            (
                                "Vencedores",
                                str(winners),
                                f"em {fmt.plural(race['round'].nunique(), 'corrida')}",
                            ),
                            (
                                "Pilotos",
                                str(len(table)),
                                "com resultado registrado",
                            ),
                        ]
                    ),
                ],
                className="lead",
            ),
            ui.panel(
                "A disputa rodada a rodada",
                "Cinco primeiros da classificação · temporada completa · Race + Sprint",
                dcc.RadioItems(
                    id="temporada-metrica",
                    options=[
                        {"label": "Distância para o líder", "value": "gap"},
                        {"label": "Pontos acumulados", "value": "points"},
                    ],
                    value="gap",
                    inline=True,
                    className="segmented",
                ),
                ui.graph(
                    charts["gap"],
                    "Distância em pontos para o líder a cada rodada",
                    height=380,
                    graph_id="temporada-grafico",
                ),
                dcc.Store(id="temporada-figuras", data=charts),
                footnote="Companheiros de equipe usam a mesma cor; o segundo aparece "
                "pontilhado. Ausência numa etapa mantém os pontos.",
                wide=True,
            ),
            ui.panel(
                "De onde vêm os pontos",
                "Dez primeiros · pontos em pódios, nas demais posições e nas sprints",
                ui.graph(
                    figures.points_sources(table),
                    "Composição dos pontos dos dez primeiros",
                    height=max(260, 34 * min(len(table), 10) + 70),
                ),
                wide=True,
            ),
            ui.details(
                "Classificação completa",
                ui.table(
                    table,
                    [
                        ("rank", "Pos", None),
                        ("driver", "Piloto", None),
                        ("team", "Equipe", None),
                        ("points", "Pontos", fmt.points),
                        ("wins", "Vitórias", fmt.number),
                        ("podiums", "Pódios", fmt.number),
                        ("recent_points", "Últimas 3 rodadas", fmt.points),
                    ],
                    caption=f"Classificação por pontos em {season}",
                    bar="points",
                ),
            ),
        ],
        className="page",
    )


def _coverage(frame, in_progress: bool):
    if frame.empty:
        return None
    races = frame.loc[frame["session"].eq("Race"), "round"].nunique()
    sprints = frame.loc[frame["session"].eq("Sprint"), "round"].nunique()
    parts = [
        fmt.plural(races, "corrida"),
        fmt.plural(sprints, "sprint"),
        f"última sessão em {fmt.day(frame['date'].max())}",
    ]
    return [
        " · ".join(parts),
        ui.badge("em andamento", "live") if in_progress else None,
    ]


# Troca de métrica sem ida ao servidor: as duas figuras já vieram no layout.
clientside_callback(
    """
    function (metric, charts) {
        return charts && charts[metric] ? charts[metric] : window.dash_clientside.no_update;
    }
    """,
    Output("temporada-grafico", "figure"),
    Input("temporada-metrica", "value"),
    State("temporada-figuras", "data"),
    prevent_initial_call=True,
)
