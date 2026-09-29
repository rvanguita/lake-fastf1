"""Corridas: como cada vitória foi construída e o detalhe de uma etapa."""

from __future__ import annotations

import dash
import pandas as pd
from dash import Input, Output, Patch, State, dcc, html
from dash.exceptions import PreventUpdate

import analytics
import components as ui
import figures
import formatting as fmt
from repository import DataUnavailable, get_repository

dash.register_page(
    __name__,
    path="/corridas",
    name="Corridas",
    title="Corridas · Race Control",
    order=1,
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
    calendar = analytics.race_calendar(frame)
    header = ui.page_header(
        f"Corridas de {season}",
        "Como as vitórias aconteceram?",
        controls=ui.season_picker(seasons, season),
        meta=f"{fmt.plural(len(calendar), 'corrida principal', 'corridas principais')}"
        if len(calendar)
        else None,
    )
    if calendar.empty:
        return html.Div(
            [header, ui.notice("Sem corridas principais registradas nesta temporada.")],
            className="page",
        )
    selected = int(calendar["round"].iloc[-1])
    timed = int(calendar["margin"].notna().sum())
    gridded = calendar.dropna(subset=["winner_grid"])
    return html.Div(
        [
            header,
            ui.notice(warning, kind="warning") if warning else None,
            ui.quality(frame),
            html.Div(
                [
                    ui.findings(analytics.race_findings(calendar)),
                    ui.kpis(
                        [
                            (
                                "Margem mediana",
                                fmt.seconds(calendar["margin"].median()),
                                f"em {timed} de {len(calendar)} corridas com tempo",
                            ),
                            (
                                "Vitórias da pole",
                                f"{int(gridded['winner_grid'].eq(1).sum())}/{len(gridded)}",
                                "vencedor largou em P1",
                            ),
                            (
                                "Vencedores",
                                str(calendar["winner"].nunique()),
                                "pilotos diferentes",
                            ),
                            (
                                "Abandonos por corrida",
                                fmt.number(calendar["retirements"].mean(), 1),
                                "média de carros fora antes do fim",
                            ),
                        ]
                    ),
                ],
                className="lead",
            ),
            ui.panel(
                "Margem de vitória por etapa",
                "Segundos entre o vencedor e o 2º colocado · cor da equipe vencedora · "
                "clique numa barra para abrir a etapa",
                ui.graph(
                    figures.victory_margins(calendar, selected),
                    "Margem de vitória em segundos em cada etapa",
                    height=320,
                    graph_id="corridas-margens",
                ),
                footnote=None
                if timed == len(calendar)
                else f"{len(calendar) - timed} etapas sem tempo do 2º na mesma volta "
                "aparecem sem barra.",
                wide=True,
            ),
            html.Section(
                [
                    html.Div(
                        [
                            html.Label("Etapa", htmlFor="corridas-etapa"),
                            dcc.Dropdown(
                                id="corridas-etapa",
                                options=[
                                    {
                                        "label": f"R{row.round:02d} · {row.event}",
                                        "value": row.round,
                                    }
                                    for row in calendar.itertuples()
                                ],
                                value=selected,
                                clearable=False,
                                className="picker wide",
                            ),
                        ],
                        className="control",
                    ),
                    html.Div(
                        detail(frame, calendar, selected),
                        id="corridas-detalhe",
                        **{"aria-live": "polite"},
                    ),
                ],
                className="panel wide",
            ),
            dcc.Store(id="corridas-ano", data=season),
            dcc.Store(id="corridas-etapas", data=calendar["round"].tolist()),
            ui.details(
                "Calendário completo",
                ui.table(
                    calendar,
                    [
                        ("round", "Etapa", None),
                        ("event", "Grande Prêmio", None),
                        ("winner", "Vencedor", None),
                        ("team", "Equipe", None),
                        ("winner_grid", "Largou", lambda v: fmt.number(v)),
                        ("margin", "Margem", fmt.seconds),
                        ("retirements", "Abandonos", fmt.number),
                    ],
                    caption=f"Vencedores e margens das corridas de {season}",
                ),
            ),
        ],
        className="page",
    )


def detail(frame, calendar, round_number: int):
    event = calendar[calendar["round"].eq(round_number)]
    if event.empty:
        return ui.notice("Etapa não encontrada nesta temporada.")
    event = event.iloc[0]
    result = analytics.race_detail(frame, round_number)
    pole = result[result["grid"].eq(1)]
    sprint = analytics.sprint_winner(frame, round_number)
    place = ", ".join(part for part in [event["location"], event["country"]] if part)
    return html.Div(
        [
            html.Div(
                [
                    html.H2(f"R{round_number:02d} · {event['event']}"),
                    html.P(
                        " · ".join(
                            part
                            for part in [
                                place,
                                fmt.day(event["date"]),
                                f"sprint vencida por {sprint}" if sprint else None,
                            ]
                            if part
                        ),
                        className="meta",
                    ),
                ],
                className="detail-head",
            ),
            ui.kpis(
                [
                    (
                        "Vencedor",
                        event["winner"] or "—",
                        f"largou em P{int(event['winner_grid'])}"
                        if pd.notna(event["winner_grid"])
                        else None,
                    ),
                    (
                        "Pole",
                        pole.iloc[0]["driver"] if len(pole) else "—",
                        _pole_note(pole.iloc[0]) if len(pole) else None,
                    ),
                    (
                        "Margem",
                        fmt.seconds(event["margin"]),
                        "para o 2º colocado",
                    ),
                    (
                        "Abandonos",
                        str(event["retirements"]),
                        "carros que não completaram",
                    ),
                ]
            ),
            ui.table(
                result.assign(
                    delta=result["gain"].map(
                        lambda v: "—" if pd.isna(v) else f"{int(v):+d}" if v else "0"
                    )
                ),
                [
                    ("position", "Pos", None),
                    ("driver", "Piloto", None),
                    ("team", "Equipe", None),
                    ("grid", "Grid", fmt.number),
                    ("delta", "±", str),
                    ("points", "Pts", fmt.points),
                    ("gap_s", "Diferença para o vencedor", fmt.seconds),
                ],
                caption=f"Resultado da corrida {event['event']}",
                bar="gap_s",
                bar_label="outcome",
            ),
        ]
    )


def _pole_note(row) -> str:
    if row["position"] == "1":
        return "venceu a corrida"
    if row["retired"]:
        return "abandonou"
    return (
        f"terminou em P{row['position']}"
        if row["position"].isdigit()
        else row["outcome"]
    )


@dash.callback(
    Output("corridas-etapa", "value"),
    Input("corridas-margens", "clickData"),
    prevent_initial_call=True,
)
def select_from_chart(click):
    try:
        return int(click["points"][0]["customdata"][0])
    except (TypeError, KeyError, IndexError, ValueError) as exc:
        raise PreventUpdate from exc


@dash.callback(
    Output("corridas-detalhe", "children"),
    Output("corridas-margens", "figure"),
    Input("corridas-etapa", "value"),
    State("corridas-ano", "data"),
    State("corridas-etapas", "data"),
    prevent_initial_call=True,
)
def show_race(round_number, season, rounds):
    if round_number is None or season is None:
        raise PreventUpdate
    try:
        frame = get_repository().results([int(season)])
    except DataUnavailable as exc:
        return ui.notice(str(exc), kind="warning"), dash.no_update
    # Patch altera só o contorno das barras em vez de reenviar a figura inteira.
    highlight = Patch()
    highlight["data"][0]["marker"]["line"]["width"] = figures.selection_outline(
        rounds or [], round_number
    )
    return detail(frame, analytics.race_calendar(frame), int(round_number)), highlight
