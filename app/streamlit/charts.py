"""Figuras Plotly sobre um template escuro único (aplicado com `theme=None`)."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio

import fmt
import metrics

SURFACE = "#1a1a19"
INK = "#f2f1ec"
INK_2 = "#c3c2b7"
MUTED = "#8a8a84"
GRID = "#2c2c2a"
AXIS = "#3a3a37"
ACCENT = "#3987e5"
NEGATIVE = "#d95926"
WARNING = "#fab219"
FONT = 'system-ui, -apple-system, "Segoe UI", Roboto, sans-serif'
# Paleta categórica escura validada (CVD e contraste 3:1) contra SURFACE; ordem fixa.
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

pio.templates["paddock"] = go.layout.Template(
    layout={
        "font": {"family": FONT, "size": 12, "color": INK_2},
        "paper_bgcolor": "rgba(0,0,0,0)",
        "plot_bgcolor": "rgba(0,0,0,0)",
        "colorway": SERIES,
        "separators": ",.",
        "margin": {"l": 8, "r": 16, "t": 36, "b": 8},
        "hoverlabel": {
            "bgcolor": "#262624",
            "bordercolor": AXIS,
            "font": {"family": FONT, "color": INK},
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
            "color": MUTED,
            "automargin": True,
            "title": {"font": {"size": 11, "color": MUTED}},
        },
        "yaxis": {
            "gridcolor": GRID,
            "zeroline": False,
            "color": MUTED,
            "automargin": True,
            "title": {"font": {"size": 11, "color": MUTED}},
        },
    }
)
CONFIG = {"displayModeBar": False, "responsive": True}


def _figure(height: int) -> go.Figure:
    return go.Figure(layout={"template": "paddock", "height": height})


def identity_styles(frame: pd.DataFrame) -> dict[str, tuple[str, str]]:
    """Cor e traço por piloto: cor da equipe (companheiro pontilhado) ou, sem cores
    na fonte (temporadas antigas), um slot fixo da paleta por piloto e traço cheio."""
    drivers = frame.drop_duplicates("driver_id")
    if drivers["color"].eq(metrics.FALLBACK_COLOR).all():
        return {
            driver: (SERIES[index % len(SERIES)], "solid")
            for index, driver in enumerate(drivers["driver_id"])
        }
    team = "team_name" if "team_name" in drivers else "team"
    dashes = metrics.line_dashes(
        list(drivers[["driver_id", team]].itertuples(index=False))
    )
    return {
        driver: (color, dashes[driver])
        for driver, color in zip(drivers["driver_id"], drivers["color"], strict=True)
    }


def title_fight(frame: pd.DataFrame, metric: str) -> go.Figure:
    """`metric` = "points" (acumulado) ou "rank" (posição no campeonato)."""
    fig = _figure(420)
    column = "cumulative_points" if metric == "points" else "championship_rank"
    styles = identity_styles(frame)
    for driver_id, data in frame.groupby("driver_id", sort=False):
        first = data.iloc[0]
        color, dash = styles[driver_id]
        fig.add_trace(
            go.Scatter(
                x=data["round_number"],
                y=data[column],
                name=first["driver_name"],
                mode="lines+markers",
                line={"color": color, "width": 2, "dash": dash},
                marker={"size": 6},
                customdata=data[["event_name"]],
                hovertemplate="%{customdata[0]}<br>%{y}<extra>%{fullData.name}</extra>",
            )
        )
        last = data.iloc[-1]
        fig.add_annotation(
            x=last["round_number"],
            y=last[column],
            text=last["abbreviation"],
            xanchor="left",
            xshift=8,
            showarrow=False,
            font={"color": INK_2, "size": 11},
        )
    fig.update_xaxes(title="Rodada", tickformat="d")
    if metric == "points":
        fig.update_yaxes(title="Pontos acumulados", rangemode="tozero")
    else:
        fig.update_yaxes(title="Posição no campeonato", autorange="reversed", dtick=1)
    return fig


def constructors(table: pd.DataFrame) -> go.Figure:
    data = table.iloc[::-1]
    fig = _figure(max(260, 30 * len(data) + 60))
    fig.add_trace(
        go.Bar(
            x=data["points"],
            y=data["team"],
            orientation="h",
            # Temporadas antigas não têm cor de equipe: barra única no acento.
            marker={
                "color": data["color"].replace(metrics.FALLBACK_COLOR, ACCENT),
                "cornerradius": 3,
            },
            text=[fmt.points(value) for value in data["points"]],
            textposition="outside",
            textfont={"color": INK_2},
            cliponaxis=False,
            hovertemplate="%{y}: %{x:,.0f} pts<extra></extra>",
        )
    )
    fig.update_layout(bargap=0.35, margin={"t": 8})
    fig.update_xaxes(visible=False)
    fig.update_yaxes(showgrid=False, ticklabelstandoff=8)
    return fig


def race_by_race(frame: pd.DataFrame, color: str) -> go.Figure:
    """Haltere grid → chegada; abandonos aparecem no grid com ×."""
    fig = _figure(360)
    labels = [f"R{number:02d}" for number in frame["round_number"]]
    for label, grid, finish in zip(
        labels, frame["official_grid"], frame["official_finish"], strict=True
    ):
        if pd.notna(grid) and pd.notna(finish):
            fig.add_trace(
                go.Scatter(
                    x=[label, label],
                    y=[grid, finish],
                    mode="lines",
                    line={"color": AXIS, "width": 3},
                    hoverinfo="skip",
                    showlegend=False,
                )
            )
    fig.add_trace(
        go.Scatter(
            x=labels,
            y=frame["official_grid"],
            mode="markers",
            name="Largada",
            marker={"size": 9, "color": SURFACE, "line": {"color": MUTED, "width": 2}},
            customdata=frame[["event_name"]],
            hovertemplate="%{customdata[0]}<br>Largou P%{y}<extra></extra>",
        )
    )
    finished = frame["official_finish"].notna()
    fig.add_trace(
        go.Scatter(
            x=[label for label, ok in zip(labels, finished, strict=True) if ok],
            y=frame.loc[finished, "official_finish"],
            mode="markers",
            name="Chegada",
            marker={"size": 11, "color": color, "line": {"color": SURFACE, "width": 2}},
            customdata=frame.loc[finished, ["event_name", "points"]],
            hovertemplate="%{customdata[0]}<br>Chegou P%{y} · %{customdata[1]} pts"
            "<extra></extra>",
        )
    )
    out = frame[~finished]
    if len(out):
        fig.add_trace(
            go.Scatter(
                x=[f"R{number:02d}" for number in out["round_number"]],
                y=out["official_grid"].fillna(1),
                mode="markers",
                name="Não completou",
                marker={
                    "size": 12,
                    "symbol": "x-thin",
                    "line": {"color": NEGATIVE, "width": 2},
                },
                customdata=out[["event_name", "result_status"]],
                hovertemplate="%{customdata[0]}<br>%{customdata[1]}<extra></extra>",
            )
        )
    worst = int(frame[["official_grid", "official_finish"]].max().max(skipna=True) or 1)
    ticks = list(range(1, worst + 1)) if worst <= 10 else [1, *range(5, worst + 1, 5)]
    fig.update_yaxes(title="Posição", autorange="reversed", tickvals=ticks)
    # Ordem das etapas fixa: o primeiro traço pode não conter todas as categorias.
    fig.update_xaxes(type="category", categoryorder="array", categoryarray=labels)
    return fig


def career(frame: pd.DataFrame) -> go.Figure:
    fig = _figure(300)
    fig.add_trace(
        go.Scatter(
            x=frame["season"],
            y=frame["rank"],
            # Rótulos só em carreiras curtas; nas longas, o hover dá a posição.
            mode="lines+markers+text" if len(frame) <= 8 else "lines+markers",
            text=[f"P{rank}" for rank in frame["rank"]],
            textposition="top center",
            textfont={"color": INK_2, "size": 11},
            line={"color": ACCENT, "width": 2},
            marker={"size": 8},
            customdata=frame[["team", "points"]],
            hovertemplate="%{x} · %{customdata[0]}<br>P%{y} · %{customdata[1]} pts"
            "<extra></extra>",
        )
    )
    fig.update_xaxes(
        title="Temporada", tickformat="d", dtick=1 if len(frame) < 12 else None
    )
    fig.update_yaxes(title="Posição final", autorange="reversed", tick0=1)
    return fig


def odds(latest: pd.DataFrame) -> go.Figure:
    """Chance de título com intervalo p10–p90 quando a API o fornece."""
    data = latest.iloc[::-1]
    fig = _figure(max(280, 34 * len(data) + 60))
    error = None
    if {"lower", "upper"}.issubset(data.columns):
        error = {
            "type": "data",
            "symmetric": False,
            "array": (data["upper"] - data["probability"]).clip(lower=0),
            "arrayminus": (data["probability"] - data["lower"]).clip(lower=0),
            "color": INK_2,
            "thickness": 1.5,
            "width": 4,
        }
    fig.add_trace(
        go.Bar(
            x=data["probability"],
            y=data["driver"],
            orientation="h",
            marker={
                "color": data["color"].replace(metrics.FALLBACK_COLOR, ACCENT),
                "cornerradius": 3,
            },
            error_x=error,
            hovertemplate="%{y}: %{x:.1%}<extra></extra>",
        )
    )
    fig.update_layout(bargap=0.35, margin={"t": 8})
    fig.update_xaxes(
        tickformat=".0%", showgrid=True, gridcolor=GRID, rangemode="tozero"
    )
    fig.update_yaxes(showgrid=False, ticklabelstandoff=8)
    return fig


def odds_evolution(frame: pd.DataFrame) -> go.Figure:
    fig = _figure(380)
    styles = identity_styles(frame)
    for driver_id, data in frame.groupby("driver_id", sort=False):
        first = data.iloc[0]
        color, dash = styles[driver_id]
        fig.add_trace(
            go.Scatter(
                x=data["dt_ref"],
                y=data["probability"],
                name=first["driver"],
                mode="lines+markers",
                line={"color": color, "width": 2, "dash": dash},
                marker={"size": 5},
                hovertemplate="%{x|%d/%m}: %{y:.1%}<extra>%{fullData.name}</extra>",
            )
        )
    fig.update_layout(hovermode="x unified")
    fig.update_yaxes(title="Chance de título", tickformat=".0%", rangemode="tozero")
    fig.update_xaxes(title="Data de referência")
    return fig


def importances(frame: pd.DataFrame) -> go.Figure:
    data = frame.iloc[::-1]
    fig = _figure(max(300, 26 * len(data) + 60))
    fig.add_trace(
        go.Bar(
            x=data["importance"],
            y=data["label"],
            orientation="h",
            marker={"color": ACCENT, "cornerradius": 3},
            hovertemplate="%{y}<br>%{x:.1%} da importância<extra></extra>",
        )
    )
    fig.update_layout(bargap=0.3, margin={"t": 8})
    fig.update_xaxes(tickformat=".0%", showgrid=True, gridcolor=GRID)
    fig.update_yaxes(showgrid=False, ticklabelstandoff=8)
    return fig


def contributions(frame: pd.DataFrame) -> go.Figure:
    """SHAP: barras para a direita aumentam a chance; para a esquerda, reduzem."""
    data = frame.iloc[::-1]
    fig = _figure(max(300, 30 * len(data) + 60))
    fig.add_trace(
        go.Bar(
            x=data["contribution"],
            y=data["label"],
            orientation="h",
            marker={
                "color": [
                    ACCENT if value >= 0 else NEGATIVE for value in data["contribution"]
                ],
                "cornerradius": 3,
            },
            customdata=data[["value"]],
            hovertemplate="%{y}<br>valor %{customdata[0]:,.2f} · efeito %{x:+.3f}"
            "<extra></extra>",
        )
    )
    fig.update_layout(bargap=0.3, margin={"t": 8})
    fig.update_xaxes(zeroline=True, zerolinecolor=AXIS, showgrid=True, gridcolor=GRID)
    fig.update_yaxes(showgrid=False, ticklabelstandoff=8)
    return fig


def calibration(points: pd.DataFrame) -> go.Figure:
    fig = _figure(320)
    fig.add_trace(
        go.Scatter(
            x=[0, 1],
            y=[0, 1],
            mode="lines",
            line={"color": AXIS, "width": 1},
            hoverinfo="skip",
            showlegend=False,
        )
    )
    fig.add_trace(
        go.Scatter(
            x=points["predicted"],
            y=points["observed"],
            mode="lines+markers",
            line={"color": ACCENT, "width": 2},
            marker={"size": 7},
            hovertemplate="previsto %{x:.0%} · observado %{y:.0%}<extra></extra>",
            showlegend=False,
        )
    )
    fig.update_xaxes(title="Probabilidade prevista", tickformat=".0%", range=[0, 1])
    fig.update_yaxes(title="Frequência observada", tickformat=".0%", range=[0, 1])
    return fig


def coverage(frame: pd.DataFrame) -> go.Figure:
    colors = {"completa": ACCENT, "parcial": WARNING, "em andamento": "#199e70"}
    fig = _figure(300)
    for status, data in frame.groupby("status", sort=False):
        fig.add_trace(
            go.Bar(
                x=data["season"],
                y=data["races"],
                name=status.capitalize(),
                marker={"color": colors.get(status, MUTED), "cornerradius": 2},
                hovertemplate="%{x}: %{y} corridas<extra>" + status + "</extra>",
            )
        )
    fig.update_layout(barmode="overlay", bargap=0.25)
    fig.update_xaxes(tickformat="d")
    fig.update_yaxes(title="Corridas no lake")
    return fig
