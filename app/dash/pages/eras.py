"""Eras: o que mudou na F1 ao longo das temporadas do lake."""

from __future__ import annotations

from urllib.parse import urlencode

import dash
from dash import Input, Output, State, dcc, html

import analytics
import components as ui
import figures
import formatting as fmt
from repository import DataUnavailable, get_repository

dash.register_page(
    __name__, path="/eras", name="Eras", title="Eras · Race Control", order=3
)


def resolve_range(start, end, seasons: list[int]) -> tuple[int, int]:
    low, high = min(seasons), max(seasons)

    def clamp(value, default):
        try:
            return min(max(int(value), low), high)
        except (TypeError, ValueError):
            return default

    first, last = clamp(start, low), clamp(end, high)
    return (first, last) if first <= last else (last, first)


def layout(de=None, ate=None, **_):
    repo = get_repository()
    try:
        seasons = repo.seasons()
        if not seasons:
            return ui.unavailable("Nenhuma temporada foi encontrada no Bronze.")
        first, last = resolve_range(de, ate, seasons)
        selected = [year for year in seasons if first <= year <= last]
        frame = repo.results(selected)
    except DataUnavailable as exc:
        return ui.unavailable(str(exc))
    return render(frame, seasons, first, last)


def render(frame, seasons: list[int], first: int, last: int):
    summary = analytics.era_summary(frame, current_year=analytics.current_year())
    decades = analytics.retirement_by_decade(frame)
    uncertain = summary[summary["partial"] | summary["in_progress"]]
    low, high = min(seasons), max(seasons)
    slider = html.Div(
        [
            html.Label("Período", htmlFor="eras-periodo"),
            dcc.RangeSlider(
                id="eras-periodo",
                min=low,
                max=high,
                step=1,
                value=[first, last],
                allowCross=False,
                updatemode="mouseup",
                marks={
                    year: str(year)
                    for year in range(low, high + 1)
                    if year % 10 == 0 or year in (low, high)
                },
                tooltip={"placement": "bottom"},
            ),
            dcc.Store(id="eras-renderizado", data=[first, last]),
        ],
        className="control range",
    )
    header = ui.page_header(
        f"Eras · {first}–{last}" if first != last else f"Era · {first}",
        "O que mudou na F1?",
        meta=f"{fmt.plural(len(summary), 'temporada')} · "
        f"{fmt.number(summary['races'].sum())} corridas · "
        f"{fmt.number(summary['starts'].sum())} largadas",
    )
    if summary.empty:
        return html.Div(
            [
                header,
                slider,
                ui.notice("Sem corridas principais no período escolhido."),
            ],
            className="page",
        )
    return html.Div(
        [
            header,
            slider,
            ui.quality(frame),
            ui.findings(analytics.era_findings(summary)),
            ui.panel(
                "Tendências por temporada",
                "Vencedores diferentes · vitórias de quem largou na pole · largadas "
                "que terminaram em abandono",
                ui.graph(
                    figures.era_trends(summary),
                    "Três tendências anuais em painéis com eixo de tempo comum",
                    height=540,
                ),
                footnote=(
                    "Círculos vazados: temporada em andamento ou com poucas corridas "
                    "no lake ("
                    + ", ".join(str(year) for year in uncertain["season"])
                    + ")."
                )
                if len(uncertain)
                else None,
                wide=True,
            ),
            ui.panel(
                "Por que os carros abandonam",
                "Parcela das largadas de cada década que terminou em abandono, por "
                "motivo registrado na fonte",
                ui.graph(
                    figures.retirement_causes(decades),
                    "Abandonos por década divididos por motivo",
                    height=340,
                ),
                footnote="Abandono: largou e o status não indica conclusão (Finished, "
                "Lapped, +N Laps); desclassificações ficam de fora. Motivos genéricos "
                "como Retired entram em “Sem motivo detalhado”.",
                wide=True,
            ),
            ui.details(
                "Temporada a temporada",
                ui.table(
                    summary.sort_values("season", ascending=False),
                    [
                        ("season", "Ano", None),
                        ("races", "Corridas", fmt.number),
                        ("leader", "Líder em pontos", None),
                        ("leader_team", "Equipe", None),
                        ("leader_wins", "Vitórias do líder", fmt.number),
                        ("winners", "Vencedores", fmt.number),
                        ("pole_rate", "Vitórias da pole", fmt.percent),
                        ("retirement_rate", "Abandonos", fmt.percent),
                    ],
                    caption="Resumo anual do período",
                ),
            ),
        ],
        className="page",
    )


@dash.callback(
    Output("url", "search", allow_duplicate=True),
    Input("eras-periodo", "value"),
    State("eras-renderizado", "data"),
    prevent_initial_call=True,
)
def select_period(value, rendered):
    if not value or list(value) == list(rendered or []):
        return dash.no_update
    return f"?{urlencode({'de': value[0], 'ate': value[1]})}"
