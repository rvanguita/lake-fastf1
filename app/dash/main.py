"""Race Control: app Dash multipágina sobre o lake de resultados de F1."""

from __future__ import annotations

import logging
import os
from urllib.parse import parse_qs, urlencode

import dash
from dash import Dash, Input, Output, State, dcc, html

# Páginas que compartilham `?ano=`; Eras usa seu próprio intervalo.
SEASON_PAGES = {"/", "/corridas", "/previsao"}

app = Dash(
    __name__,
    use_pages=True,
    compress=True,
    suppress_callback_exceptions=True,
    title="Race Control",
    update_title=None,
)
server = app.server


def query(search: str | None) -> dict[str, str]:
    return {
        key: values[0] for key, values in parse_qs((search or "").lstrip("?")).items()
    }


def nav_links(pathname: str | None, search: str | None) -> list:
    season = query(search).get("ano")
    links = []
    for page in dash.page_registry.values():
        path = page["relative_path"]
        suffix = (
            f"?{urlencode({'ano': season})}" if season and path in SEASON_PAGES else ""
        )
        current = path == (pathname or "/")
        links.append(
            dcc.Link(
                page["name"],
                href=path + suffix,
                className="nav-link active" if current else "nav-link",
            )
        )
    return links


app.layout = html.Div(
    [
        dcc.Location(id="url", refresh="callback-nav"),
        html.A("Pular para o conteúdo", href="#conteudo", className="skip-link"),
        html.Header(
            html.Div(
                [
                    dcc.Link(
                        [
                            html.Span("RC", className="brand-mark"),
                            html.Span(
                                [
                                    html.Strong("Race Control"),
                                    html.Small("Lake FastF1"),
                                ],
                                className="brand-text",
                            ),
                        ],
                        href="/",
                        className="brand",
                    ),
                    html.Nav(
                        nav_links("/", ""),
                        id="nav",
                        className="nav",
                        **{"aria-label": "Páginas"},
                    ),
                ],
                className="topbar-inner",
            ),
            className="topbar",
        ),
        html.Main(dash.page_container, id="conteudo", className="shell"),
        html.Footer(
            html.P(
                "Resultados FastF1 do lake (Bronze) e features da ABT. Pontos somam "
                "Race + Sprint; vitórias e pódios contam só a corrida principal. "
                "A classificação é reconstruída dos pontos das sessões e não substitui "
                "o resultado oficial do campeonato."
            ),
            className="footer",
        ),
    ],
    className="app",
)


@dash.callback(
    Output("nav", "children"),
    Input("url", "pathname"),
    Input("url", "search"),
)
def update_nav(pathname, search):
    return nav_links(pathname, search)


@dash.callback(
    Output("url", "search", allow_duplicate=True),
    Input("ano", "value"),
    State("ano-renderizado", "data"),
    prevent_initial_call=True,
)
def select_season(season, rendered):
    # A URL é a fonte da verdade: mudar o ano renderiza a página de novo a partir dela.
    if not season or season == rendered:
        return dash.no_update
    return f"?{urlencode({'ano': season})}"


@server.get("/healthz")
def health():
    return {"status": "ok", "service": "race-control"}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    app.run(
        host=os.getenv("DASH_HOST", "127.0.0.1"),
        port=int(os.getenv("DASH_PORT", "8050")),
        debug=False,
    )
