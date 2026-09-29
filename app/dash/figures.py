"""Figuras Plotly do Race Control sobre um template único e discreto."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
from plotly.subplots import make_subplots

import formatting as fmt
from analytics import CAUSES, FALLBACK_COLOR

SURFACE = "#1a1a19"
INK = "#ffffff"
INK_2 = "#c3c2b7"
MUTED = "#898781"
GRID = "#2c2c2a"
AXIS = "#383835"
FONT = 'system-ui, -apple-system, "Segoe UI", sans-serif'
# Paleta categórica escura validada (CVD e contraste) contra SURFACE; ordem fixa.
SERIES = [
    "#3987e5",
    "#d95926",
    "#199e70",
    "#c98500",
    "#d55181",
    "#008300",
    "#9085e9",
    "#e66767",
]

pio.templates["race_control"] = go.layout.Template(
    layout={
        "font": {"family": FONT, "size": 12, "color": INK_2},
        "paper_bgcolor": "rgba(0,0,0,0)",
        "plot_bgcolor": "rgba(0,0,0,0)",
        "colorway": SERIES,
        "separators": ",.",
        "margin": {"l": 8, "r": 16, "t": 8, "b": 8},
        "hovermode": "closest",
        "hoverlabel": {
            "bgcolor": "#262624",
            "bordercolor": AXIS,
            "font": {"family": FONT, "size": 12, "color": INK},
        },
        "legend": {
            "orientation": "h",
            "x": 0,
            "y": 1.02,
            "yanchor": "bottom",
            "bgcolor": "rgba(0,0,0,0)",
            "font": {"color": INK_2},
        },
        "xaxis": {
            "showgrid": False,
            "zeroline": False,
            "linecolor": AXIS,
            "tickcolor": AXIS,
            "ticks": "outside",
            "ticklen": 4,
            "color": MUTED,
            "automargin": True,
            "title": {"font": {"size": 11, "color": MUTED}},
        },
        "yaxis": {
            "gridcolor": GRID,
            "zeroline": False,
            "showline": False,
            "color": MUTED,
            "automargin": True,
            "title": {"font": {"size": 11, "color": MUTED}},
        },
    }
)


def _figure(*traces) -> go.Figure:
    return go.Figure(data=list(traces), layout={"template": "race_control"})


def empty_figure(message: str) -> go.Figure:
    fig = _figure()
    fig.add_annotation(
        text=message,
        x=0.5,
        y=0.5,
        xref="paper",
        yref="paper",
        showarrow=False,
        font={"color": MUTED, "size": 13},
    )
    fig.update_xaxes(visible=False)
    fig.update_yaxes(visible=False)
    return fig


def driver_styles(table: pd.DataFrame) -> dict[str, dict]:
    """Cor segue o piloto dentro da temporada: equipe quando houver, senão slot fixo.

    O segundo piloto de uma mesma equipe recebe traço pontilhado para não depender
    apenas da cor.
    """
    styles = {}
    teams_seen: set[str] = set()
    use_team = table["color"].ne(FALLBACK_COLOR).all()
    for index, row in enumerate(table.itertuples()):
        color = row.color if use_team else SERIES[index % len(SERIES)]
        dash = "dot" if use_team and row.team in teams_seen else "solid"
        teams_seen.add(row.team)
        styles[row.driver_id] = {"color": color, "dash": dash}
    return styles


def championship(
    progression: pd.DataFrame,
    table: pd.DataFrame,
    *,
    metric: str = "gap",
    limit: int = 5,
) -> go.Figure:
    """Distância para o líder (`gap`) ou pontos acumulados (`points`) por rodada."""
    if progression.empty:
        return empty_figure("Sem pontos registrados nesta temporada")
    top = table.head(limit)
    styles = driver_styles(top)
    column = "gap_to_leader" if metric == "gap" else "cumulative"
    fig = _figure()
    for row in top.itertuples():
        data = progression[progression["driver_id"].eq(row.driver_id)]
        style = styles[row.driver_id]
        fig.add_trace(
            go.Scatter(
                x=data["round"].tolist(),
                y=data[column].tolist(),
                name=row.driver,
                mode="lines+markers",
                line={"color": style["color"], "width": 2, "dash": style["dash"]},
                marker={"size": 6, "color": style["color"]},
                hovertemplate="%{y:,.0f} pts<extra>%{fullData.name}</extra>",
            )
        )
        if len(data):
            fig.add_annotation(
                x=data["round"].iloc[-1],
                y=data[column].iloc[-1],
                text=row.code,
                xanchor="left",
                xshift=8,
                showarrow=False,
                font={"color": INK_2, "size": 11},
            )
    fig.update_layout(hovermode="x unified", showlegend=True)
    # Sem dtick fixo: o Plotly espaça os rótulos pela largura disponível (celular).
    fig.update_xaxes(title="Rodada", tickformat="d")
    if metric == "gap":
        fig.update_yaxes(title="Pontos atrás do líder", autorange="reversed")
    else:
        fig.update_yaxes(title="Pontos acumulados", rangemode="tozero")
    return fig


def points_sources(table: pd.DataFrame, *, limit: int = 10) -> go.Figure:
    data = table.head(limit).iloc[::-1]
    if data.empty:
        return empty_figure("Sem pontos registrados nesta temporada")
    parts = [
        ("podium_points", "Pódios"),
        ("other_race_points", "Demais corridas"),
        ("sprint_points", "Sprints"),
    ]
    if not data["sprint_points"].any():
        parts = parts[:2]
    fig = _figure()
    for index, (column, label) in enumerate(parts):
        fig.add_trace(
            go.Bar(
                x=data[column].tolist(),
                y=data["driver"].tolist(),
                name=label,
                orientation="h",
                marker={
                    "color": SERIES[index],
                    "line": {"color": SURFACE, "width": 2},
                },
                hovertemplate="%{y}<br>" + label + ": %{x:,.0f} pts<extra></extra>",
            )
        )
    for row in data.itertuples():
        fig.add_annotation(
            x=row.points,
            y=row.driver,
            text=fmt.points(row.points),
            xanchor="left",
            xshift=6,
            showarrow=False,
            font={"color": INK_2, "size": 11},
        )
    fig.update_layout(barmode="stack", bargap=0.35, legend_traceorder="normal")
    fig.update_xaxes(title="Pontos", showgrid=True, gridcolor=GRID)
    fig.update_yaxes(showgrid=False)
    return fig


def victory_margins(calendar: pd.DataFrame, selected: int | None = None) -> go.Figure:
    if calendar.empty:
        return empty_figure("Sem corridas principais nesta temporada")
    labels = [f"R{number:02d}" for number in calendar["round"]]
    colors = [
        color if color != FALLBACK_COLOR else SERIES[0] for color in calendar["color"]
    ]
    outline = selection_outline(calendar["round"].tolist(), selected)
    customdata = [
        [
            row.round,
            row.event,
            row.winner or "—",
            row.team or "—",
            f"P{int(row.winner_grid)}" if pd.notna(row.winner_grid) else "—",
            fmt.seconds(row.margin),
        ]
        for row in calendar.itertuples()
    ]
    fig = _figure(
        go.Bar(
            x=labels,
            y=calendar["margin"].tolist(),
            marker={
                "color": colors,
                "cornerradius": 3,
                "line": {"color": INK, "width": outline},
            },
            text=[code or "" for code in calendar["winner_code"]],
            textposition="outside",
            textfont={"color": INK_2, "size": 10},
            cliponaxis=False,
            customdata=customdata,
            hovertemplate=(
                "<b>%{customdata[1]}</b><br>%{customdata[2]} · %{customdata[3]}"
                "<br>Largou em %{customdata[4]} · margem %{customdata[5]}"
                "<extra></extra>"
            ),
        )
    )
    fig.update_layout(bargap=0.45, showlegend=False)
    fig.update_xaxes(type="category", title="Etapa")
    fig.update_yaxes(title="Segundos à frente do 2º", rangemode="tozero")
    return fig


def selection_outline(rounds: list[int], selected: int | None) -> list[int]:
    """Contorno na barra selecionada; as demais mantêm a cor original da equipe."""
    return [2 if number == selected else 0 for number in rounds]


def probability_vs_points(view: pd.DataFrame, *, labelled: int = 5) -> go.Figure:
    if view.empty:
        return empty_figure("Sem candidatos nesta data")
    colors = [
        color if color != FALLBACK_COLOR else SERIES[0] for color in view["color"]
    ]
    text = [
        row.code if index < labelled else ""
        for index, row in enumerate(view.itertuples())
    ]
    fig = _figure(
        go.Scatter(
            x=view["points"].tolist(),
            y=view["probability"].tolist(),
            mode="markers+text",
            text=text,
            textposition="top center",
            textfont={"color": INK_2, "size": 11},
            marker={
                "size": 12,
                "color": colors,
                "line": {"color": SURFACE, "width": 2},
            },
            customdata=view[["driver", "team", "rank", "model_rank"]].values.tolist(),
            hovertemplate=(
                "<b>%{customdata[0]}</b> · %{customdata[1]}"
                "<br>%{x:,.0f} pts (%{customdata[2]}º na tabela)"
                "<br>%{y:.1%} de chance (%{customdata[3]}º no modelo)<extra></extra>"
            ),
        )
    )
    fig.update_layout(showlegend=False)
    fig.update_xaxes(
        title="Pontos na data", rangemode="tozero", showgrid=True, gridcolor=GRID
    )
    fig.update_yaxes(title="Chance de título", tickformat=".0%", rangemode="tozero")
    return fig


def era_trends(summary: pd.DataFrame) -> go.Figure:
    if summary.empty:
        return empty_figure("Sem temporadas no recorte")
    rows = [
        ("winners", "Vencedores diferentes", ",.0f", None),
        ("pole_rate", "Vitórias saindo da pole", ".0%", ".0%"),
        ("retirement_rate", "Largadas que terminaram em abandono", ".0%", ".0%"),
    ]
    fig = make_subplots(
        rows=len(rows),
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.09,
        subplot_titles=[title for _, title, _, _ in rows],
    )
    fig.update_layout(
        template="race_control",
        showlegend=False,
        hovermode="x",
        margin={"l": 8, "r": 16, "t": 28, "b": 8},
    )
    uncertain = summary["partial"] | summary["in_progress"]
    symbols = ["circle-open" if flag else "circle" for flag in uncertain]
    for index, (column, title, hover, tick) in enumerate(rows, start=1):
        fig.add_trace(
            go.Scatter(
                x=summary["season"].tolist(),
                y=summary[column].tolist(),
                mode="lines+markers",
                name=title,
                line={"color": SERIES[0], "width": 2},
                marker={"size": 7, "symbol": symbols, "color": SERIES[0]},
                hovertemplate="%{x}: %{y:" + hover + "}<extra></extra>",
            ),
            row=index,
            col=1,
        )
        fig.update_yaxes(
            tickformat=tick, rangemode="tozero", nticks=5, row=index, col=1
        )
    for annotation in fig.layout.annotations:
        annotation.update(x=0, xanchor="left", font={"color": INK_2, "size": 12})
    fig.update_xaxes(dtick=5)
    return fig


def retirement_causes(decades: pd.DataFrame) -> go.Figure:
    if decades.empty:
        return empty_figure("Sem largadas no recorte")
    fig = _figure()
    for index, cause in enumerate(CAUSES):
        data = decades[decades["cause"].eq(cause)]
        fig.add_trace(
            go.Bar(
                x=[f"Anos {decade}" for decade in data["decade"]],
                y=data["rate"].tolist(),
                name=cause,
                marker={
                    "color": SERIES[index],
                    "line": {"color": SURFACE, "width": 2},
                },
                customdata=data[["count", "starts"]].values.tolist(),
                hovertemplate=(
                    cause
                    + ": %{y:.1%}<br>%{customdata[0]:,.0f} de %{customdata[1]:,.0f} "
                    "largadas<extra></extra>"
                ),
            )
        )
    totals = decades.groupby("decade")["rate"].sum()
    for decade, total in totals.items():
        fig.add_annotation(
            x=f"Anos {decade}",
            y=total,
            text=fmt.percent(total),
            yanchor="bottom",
            yshift=4,
            showarrow=False,
            font={"color": INK_2, "size": 11},
        )
    fig.update_layout(barmode="stack", bargap=0.4, legend_traceorder="normal")
    fig.update_yaxes(title="Parcela das largadas", tickformat=".0%")
    return fig
