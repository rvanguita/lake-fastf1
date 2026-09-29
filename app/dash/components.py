"""Componentes de interface compartilhados pelas páginas."""

from __future__ import annotations

from collections.abc import Callable, Sequence

import pandas as pd
from dash import dcc, html

GRAPH_CONFIG = {"displayModeBar": False, "responsive": True}
Column = tuple[str, str, Callable | None]


def resolve_season(value, seasons: Sequence[int]) -> tuple[int | None, str | None]:
    """Traduz `?ano=` para uma temporada existente; inválido cai na mais recente."""
    if not seasons:
        return None, None
    try:
        season = int(value)
    except (TypeError, ValueError):
        season = None
    if value is not None and season not in seasons:
        return seasons[
            0
        ], f"A temporada {value} não está no lake; exibindo {seasons[0]}."
    return season or seasons[0], None


def page_header(title: str, question: str, *, controls=None, meta=None):
    return html.Header(
        [
            html.Div(
                [
                    html.P(question, className="eyebrow"),
                    html.H1(title),
                    html.P(meta, className="meta") if meta else None,
                ],
                className="page-title",
            ),
            html.Div(controls, className="controls") if controls else None,
        ],
        className="page-header",
    )


def season_picker(seasons: Sequence[int], value: int):
    return html.Div(
        [
            html.Label("Temporada", htmlFor="ano"),
            dcc.Dropdown(
                id="ano",
                options=[{"label": str(year), "value": year} for year in seasons],
                value=value,
                clearable=False,
                className="picker",
            ),
            # Ano com que a página foi renderizada: o Dropdown reemite o valor ao montar.
            dcc.Store(id="ano-renderizado", data=value),
        ],
        className="control",
    )


def findings(items: Sequence[str]):
    if not items:
        return None
    return html.Section(
        [
            html.H2("Achados", className="section-label"),
            html.Ol([html.Li(item) for item in items], className="findings"),
        ],
        className="findings-block",
    )


def kpis(items: Sequence[tuple[str, str, str | None]]):
    return html.Div(
        [
            html.Div(
                [
                    html.Span(label, className="kpi-label"),
                    html.Strong(value, className="kpi-value"),
                    html.Span(note, className="kpi-note") if note else None,
                ],
                className="kpi",
            )
            for label, value, note in items
        ],
        className="kpis",
    )


def panel(title: str, subtitle: str | None, *children, footnote=None, wide=False):
    return html.Section(
        [
            html.Div(
                [html.H2(title), html.P(subtitle) if subtitle else None],
                className="panel-head",
            ),
            *children,
            html.P(footnote, className="footnote") if footnote else None,
        ],
        className="panel wide" if wide else "panel",
    )


def graph(figure, label: str, *, height: int, graph_id: str | None = None):
    # `responsive=True` descarta a altura do layout: a altura vem sempre do estilo.
    extra = {"id": graph_id} if graph_id else {}
    return html.Div(
        dcc.Graph(
            figure=figure,
            config=GRAPH_CONFIG,
            responsive=True,
            style={"height": f"{height}px"},
            **extra,
        ),
        className="graph",
        role="img",
        **{"aria-label": label},
    )


def team_cell(row: dict):
    return [
        html.Span(className="dot", style={"background": row.get("color")}),
        row.get("team") or "—",
    ]


def table(
    frame: pd.DataFrame,
    columns: Sequence[Column],
    *,
    caption: str,
    bar: str | None = None,
    bar_label: str | None = None,
):
    """Tabela HTML; `bar` desenha uma barra proporcional ao campo na coluna de mesmo nome."""
    maximum = float(frame[bar].max()) if bar and len(frame) else 0.0
    head = html.Thead(
        html.Tr(
            [
                html.Th(label, scope="col", className="num" if formatter else None)
                for _, label, formatter in columns
            ]
        )
    )
    rows = []
    for row in frame.to_dict("records"):
        cells = []
        for key, _, formatter in columns:
            value = row.get(key)
            if key == "team":
                cells.append(html.Td(team_cell(row), className="team"))
                continue
            text = formatter(value) if formatter else value
            if text is None or (not isinstance(text, str) and pd.isna(text)):
                text = "—"
            if key == bar:
                width = 0 if maximum <= 0 or pd.isna(value) else value / maximum * 100
                label = row.get(bar_label) if bar_label else text
                cells.append(
                    html.Td(
                        html.Div(
                            [
                                html.Div(
                                    html.Span(
                                        className="bar",
                                        style={"width": f"{width:.1f}%"},
                                    ),
                                    className="bar-track",
                                ),
                                html.Span(label, className="bar-label"),
                            ],
                            className="bar-cell",
                        ),
                        className="num",
                    )
                )
            else:
                cells.append(html.Td(str(text), className="num" if formatter else None))
        rows.append(html.Tr(cells))
    return html.Div(
        html.Table(
            [html.Caption(caption, className="sr-only"), head, html.Tbody(rows)]
        ),
        className="table-wrap",
        tabIndex=0,
    )


def details(summary: str, *children, open_=False):
    return html.Details(
        [html.Summary(summary), *children], className="details", open=open_
    )


def notice(text: str, *, title: str | None = None, kind: str = "info"):
    return html.Div(
        [html.Strong(title) if title else None, html.Span(text)],
        className=f"notice {kind}",
        role="status",
    )


def badge(text: str, kind: str = "neutral"):
    return html.Span(text, className=f"badge {kind}")


def unavailable(message: str):
    return html.Div(
        [
            html.H1("Dados indisponíveis"),
            html.P(message),
            html.P(
                "Execute o pipeline (Raw → Bronze → Silver) ou confira "
                "TABLE_PATH_BRONZE / TABLE_PATH_SILVER e recarregue a página.",
                className="meta",
            ),
        ],
        className="empty",
        role="status",
    )


def quality(frame: pd.DataFrame):
    duplicates = frame.attrs.get("duplicates", 0)
    invalid = frame.attrs.get("invalid", 0)
    if not duplicates and not invalid:
        return None
    return notice(
        f"{duplicates} registros duplicados e {invalid} inválidos foram excluídos "
        "deste recorte.",
        title="Qualidade dos dados",
        kind="warning",
    )
