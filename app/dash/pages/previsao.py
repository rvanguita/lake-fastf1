"""Previsão: o modelo publicado comparado com a classificação na mesma data."""

from __future__ import annotations

import dash
import pandas as pd
from dash import Input, Output, State, dcc, html
from dash.exceptions import PreventUpdate

import analytics
import components as ui
import figures
import formatting as fmt
from repository import DataUnavailable, get_repository

dash.register_page(
    __name__,
    path="/previsao",
    name="Previsão",
    title="Previsão · Race Control",
    order=2,
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
    try:
        snapshots = repo.snapshots(season)
        abt_error = None
    except DataUnavailable as exc:
        snapshots, abt_error = [], str(exc)
    return render(frame, season, seasons, snapshots, warning, abt_error)


def render(
    frame,
    season: int,
    seasons: list[int],
    snapshots: list[str],
    warning: str | None = None,
    abt_error: str | None = None,
):
    snapshot = snapshots[0] if snapshots else None
    picker = html.Div(
        [
            html.Label("Data de referência", htmlFor="previsao-data"),
            dcc.Dropdown(
                id="previsao-data",
                options=[
                    {"label": fmt.day(value), "value": value} for value in snapshots
                ],
                value=snapshot,
                clearable=False,
                placeholder="Sem datas na ABT",
                className="picker",
            ),
        ],
        className="control",
    )
    missing = None
    if not snapshots:
        missing = ui.notice(
            abt_error
            or f"A ABT não tem snapshots para {season}; a classificação abaixo usa a "
            "temporada inteira.",
            title="Previsão indisponível",
            kind="warning",
        )
    return html.Div(
        [
            ui.page_header(
                f"Previsão {season}",
                "O modelo concorda com a tabela?",
                controls=[ui.season_picker(seasons, season), picker],
                meta="Chances de título do modelo publicado, lado a lado com os pontos "
                "somados até a mesma data.",
            ),
            ui.notice(warning, kind="warning") if warning else None,
            missing,
            dcc.Store(id="previsao-ano", data=season),
            dcc.Loading(
                html.Div(id="previsao-modelo", className="stack"),
                type="dot",
                color=figures.SERIES[0],
                delay_show=250,
            ),
            html.Div(
                standings_panel(frame, snapshot),
                id="previsao-tabela",
            ),
        ],
        className="page",
    )


def standings_panel(frame, snapshot: str | None):
    table = (
        analytics.standings_at(frame, snapshot)
        if snapshot
        else analytics.driver_table(frame)
    )
    return ui.details(
        "Classificação na data" if snapshot else "Classificação da temporada",
        ui.table(
            table,
            [
                ("rank", "Pos", None),
                ("driver", "Piloto", None),
                ("team", "Equipe", None),
                ("points", "Pontos", fmt.points),
                ("wins", "Vitórias", fmt.number),
            ],
            caption="Classificação por pontos até a data de referência",
            bar="points",
        ),
        open_=True,
    )


def forecast(season: int, snapshot: str):
    repo = get_repository()
    try:
        predictions, context = repo.forecast(season, snapshot)
        frame = repo.results([season])
    except DataUnavailable as exc:
        return ui.notice(
            f"{exc} A classificação na data segue abaixo.",
            title="Previsão indisponível",
            kind="warning",
        )
    view = analytics.forecast_view(predictions, analytics.standings_at(frame, snapshot))
    top = view.head(8)
    rest = view.iloc[8:]
    return html.Div(
        [
            html.Div(
                [
                    ui.findings(analytics.forecast_findings(view)),
                    model_card(season, context),
                ],
                className="lead",
            ),
            html.Div(
                [
                    ui.panel(
                        "Chance × pontos na data",
                        "Cada ponto é um piloto · quem aparece alto para os pontos "
                        "que tem é onde o modelo discorda da tabela",
                        ui.graph(
                            figures.probability_vs_points(view),
                            "Chance de título em função dos pontos somados",
                            height=380,
                        ),
                    ),
                    ui.panel(
                        "Chances de título",
                        "Estimativa pontual normalizada entre os candidatos",
                        ui.table(
                            top,
                            [
                                ("model_rank", "#", None),
                                ("driver", "Piloto", None),
                                ("team", "Equipe", None),
                                (
                                    "probability",
                                    "Chance",
                                    lambda value: fmt.percent(value, 1),
                                ),
                            ],
                            caption="Oito maiores chances de título",
                            bar="probability",
                        ),
                        footnote=f"Demais {len(rest)} candidatos somam "
                        f"{fmt.percent(rest['probability'].sum(), 1)}."
                        if len(rest)
                        else None,
                    ),
                ],
                className="grid-2",
            ),
        ],
        className="stack",
    )


def model_card(season: int, context: dict):
    card = context.get("card") or {}
    metadata = context.get("metadata") or {}
    status = card.get("status") or metadata.get("status")
    trained = card.get("trained_through")
    try:
        in_training = trained is not None and season <= int(trained)
    except (TypeError, ValueError):
        in_training = False
    simulated = in_training or season < analytics.current_year()
    evaluations = pd.DataFrame(card.get("evaluations") or [])
    lines = []
    if {"top1_accuracy", "baseline_accuracy"}.issubset(evaluations.columns):
        lines.append(
            f"Acertou o campeão em {fmt.percent(evaluations['top1_accuracy'].mean())} "
            f"dos backtests (referência ingênua: "
            f"{fmt.percent(evaluations['baseline_accuracy'].mean())})."
        )
    if simulated:
        lines.append(
            "Simulação: o modelo publicado hoje aplicado a uma data passada; não é uma "
            "previsão arquivada."
            + (" A temporada está dentro do período de treino." if in_training else "")
        )
    lines.append("Sem intervalo de confiança; não use como garantia de resultado.")
    return html.Div(
        [
            html.H2("Modelo", className="section-label"),
            html.Div(
                [
                    ui.badge(
                        {"experimental": "Experimental", "validated": "Validado"}.get(
                            status, str(status or "Status não informado")
                        ),
                        "neutral",
                    ),
                    ui.badge(
                        f"Treinado até {trained}" if trained else "Corte de treino n/d",
                        "neutral",
                    ),
                    ui.badge("Simulação histórica", "warning") if simulated else None,
                ],
                className="badges",
            ),
            html.Ul([html.Li(line) for line in lines], className="model-notes"),
        ],
        className="model-card",
    )


@dash.callback(
    Output("previsao-modelo", "children"),
    Input("previsao-data", "value"),
    State("previsao-ano", "data"),
)
def show_forecast(snapshot, season):
    # Único ponto do app que chama a API; roda depois do layout já estar na tela.
    if not snapshot or season is None:
        raise PreventUpdate
    return forecast(int(season), snapshot)


@dash.callback(
    Output("previsao-tabela", "children"),
    Input("previsao-data", "value"),
    State("previsao-ano", "data"),
    prevent_initial_call=True,
)
def show_standings(snapshot, season):
    if not snapshot or season is None:
        raise PreventUpdate
    try:
        frame = get_repository().results([int(season)])
    except DataUnavailable as exc:
        return ui.notice(str(exc), kind="warning")
    return standings_panel(frame, snapshot)
