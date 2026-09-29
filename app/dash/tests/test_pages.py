import pytest
from conftest import FakeRepository, rendered
from dash import Patch, no_update
from dash.exceptions import PreventUpdate

import figures
import main
import repository
from analytics import driver_table, race_calendar, standings_progression
from pages import corridas, eras, previsao, temporada
from repository import DataUnavailable


@pytest.mark.parametrize(
    "page,kwargs,expected",
    [
        (temporada, {}, ["Temporada 2024", "Beta terminou com 51 pontos"]),
        (
            temporada,
            {"ano": "2024"},
            ["De onde vêm os pontos", "Classificação completa"],
        ),
        (
            corridas,
            {"ano": "2024"},
            ["R03 · GP 3", "+1 volta", "Vitória mais apertada"],
        ),
        (previsao, {"ano": "2024"}, ["Previsão 2024", "Classificação na data"]),
        (eras, {}, ["Era · 2024", "Por que os carros abandonam"]),
        (eras, {"de": "2030", "ate": "1900"}, ["Era · 2024"]),
    ],
)
def test_pages_render_serializable_content(fake, page, kwargs, expected):
    content = rendered(page.layout(**kwargs))
    for text in expected:
        assert text in content
    # Só o callback da previsão consulta a API; nenhum layout faz isso.
    assert fake.forecast_calls == []


def test_unknown_season_falls_back_with_warning(fake):
    content = rendered(temporada.layout(ano="1900"))
    assert "A temporada 1900 não está no lake; exibindo 2024." in content
    assert "Temporada 2024" in content


@pytest.mark.parametrize("page", [temporada, corridas, previsao, eras])
def test_empty_and_unreachable_lake_render_explicit_state(results, page):
    repository.set_repository(FakeRepository(results.iloc[0:0]))
    assert "Dados indisponíveis" in rendered(page.layout())

    class Offline(FakeRepository):
        def seasons(self):
            raise DataUnavailable("Tabela Delta indisponível.")

    repository.set_repository(Offline(results))
    assert "Tabela Delta indisponível." in rendered(page.layout())
    repository.set_repository(None)


def test_forecast_success_explains_model_and_simulation(fake):
    content = rendered(previsao.forecast(2024, "2024-03-10"))
    assert "Gamma é o favorito do modelo, com 50,0% de chance." in content
    assert "Simulação histórica" in content
    assert "Acertou o campeão em 75% dos backtests" in content
    assert fake.forecast_calls == [(2024, "2024-03-10")]


def test_forecast_failure_keeps_standings(fake):
    fake.forecast_error = "A API respondeu 500 (Model not found)."
    content = rendered(previsao.forecast(2024, "2024-03-10"))
    assert "Model not found" in content
    page = rendered(previsao.layout(ano="2024"))
    assert "Classificação na data" in page and "Alpha" in page


def test_forecast_without_snapshots_says_why(results):
    repository.set_repository(FakeRepository(results, snapshots=()))
    content = rendered(previsao.layout(ano="2024"))
    assert "A ABT não tem snapshots para 2024" in content
    assert "Classificação da temporada" in content
    repository.set_repository(None)


def test_season_selection_only_changes_url_on_real_change():
    select = main.select_season
    assert select(2023, 2024) == "?ano=2023"
    assert select(2024, 2024) is no_update  # Dropdown reemitindo o valor ao montar
    period = eras.select_period
    assert period([1990, 2000], [1980, 2026]) == "?de=1990&ate=2000"
    assert period([1980, 2026], [1980, 2026]) is no_update


def test_navigation_keeps_season_only_on_season_pages():
    links = {link.children: link.href for link in main.nav_links("/eras", "?ano=2021")}
    assert links == {
        "Temporada": "/?ano=2021",
        "Corridas": "/corridas?ano=2021",
        "Previsão": "/previsao?ano=2021",
        "Eras": "/eras",
    }
    active = [
        link.children
        for link in main.nav_links("/eras", "")
        if "active" in link.className
    ]
    assert active == ["Eras"]


def test_race_selection_from_chart_and_dropdown(fake):
    click = {"points": [{"customdata": [2, "GP 2"]}]}
    assert corridas.select_from_chart(click) == 2
    with pytest.raises(PreventUpdate):
        corridas.select_from_chart({"points": []})
    detail, highlight = corridas.show_race(2, 2024, [1, 2, 3])
    assert "R02 · GP 2" in rendered(detail)
    assert "Abandono · Engine" in rendered(detail)
    assert isinstance(highlight, Patch)


def test_http_routes_assets_and_forecast_callback(fake):
    client = main.app.server.test_client()
    for path in [
        "/",
        "/corridas?ano=2024",
        "/previsao",
        "/eras",
        "/healthz",
        "/assets/style.css",
    ]:
        assert client.get(path).status_code == 200, path
    key = next(k for k in main.app.callback_map if "previsao-modelo.children" in k)
    response = client.post(
        "/_dash-update-component",
        json={
            "output": key,
            "outputs": {"id": "previsao-modelo", "property": "children"},
            "inputs": [
                {"id": "previsao-data", "property": "value", "value": "2024-03-10"}
            ],
            "state": [{"id": "previsao-ano", "property": "data", "value": 2024}],
            "changedPropIds": ["previsao-data.value"],
        },
    )
    assert response.status_code == 200, response.data
    assert "Gamma" in response.get_data(as_text=True)


def test_figures_encode_the_intended_reading(results):
    table = driver_table(results)
    progression = standings_progression(results)
    gap = figures.championship(progression, table, metric="gap")
    assert gap.layout.yaxis.autorange == "reversed"
    assert len(gap.data) == 4
    points = figures.championship(progression, table, metric="points")
    assert points.layout.yaxis.rangemode == "tozero"
    sources = figures.points_sources(table)
    assert [trace.name for trace in sources.data] == [
        "Pódios",
        "Demais corridas",
        "Sprints",
    ]
    assert sources.layout.legend.traceorder == "normal"
    margins = figures.victory_margins(race_calendar(results), selected=3)
    assert list(margins.data[0].marker.line.width) == [0, 0, 2]
    assert figures.selection_outline([1, 2], None) == [0, 0]
    assert figures.empty_figure("x").layout.annotations[0].text == "x"


def test_teammates_share_color_but_not_line_style(results):
    styles = figures.driver_styles(driver_table(results))
    assert styles["a"]["color"] == styles["b"]["color"]
    assert {styles["a"]["dash"], styles["b"]["dash"]} == {"solid", "dot"}
