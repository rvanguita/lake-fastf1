import json
from pathlib import Path

import pytest
import requests
from streamlit.testing.v1 import AppTest

import model_api

MAIN = str(Path(__file__).resolve().parents[1] / "main.py")
FEATURES = ["qty_1place_r_20"]


def reply(body, status=200):
    response = requests.Response()
    response.status_code = status
    response._content = json.dumps(body).encode()
    return response


@pytest.fixture
def api_online(monkeypatch):
    def get(url, **_):
        if url.endswith("/model_info"):
            return reply({"features": FEATURES, "importances": {FEATURES[0]: 1.0}})
        return reply({"status": "experimental", "limitations": ["Somente teste."]})

    def post(url, data, **_):
        rows = json.loads(data)["values"]
        if url.endswith("/v1/explain"):
            row = rows[0]
            return reply(
                {
                    "explanations": {
                        row["id"]: {
                            "base_value": 0.1,
                            "contributions": [
                                {
                                    "feature": FEATURES[0],
                                    "value": 3.0,
                                    "contribution": 0.2,
                                }
                            ],
                        }
                    }
                }
            )
        groups: dict[str, list] = {}
        for row in rows:
            groups.setdefault(row["prediction_group"], []).append(row)
        predictions = {}
        for members in groups.values():
            total = sum(member[FEATURES[0]] + 1 for member in members)
            for member in members:
                share = (member[FEATURES[0]] + 1) / total
                predictions[member["id"]] = {
                    "probability": share,
                    "lower": share * 0.8,
                    "upper": min(share * 1.2, 1),
                }
        return reply({"predictions": predictions, "metadata": {}})

    monkeypatch.setattr(model_api.requests, "get", get)
    monkeypatch.setattr(model_api.requests, "post", post)


def run(page=None, **params):
    """Abre a página como um link direto `/<página>?param=valor`."""
    app = AppTest.from_file(MAIN, default_timeout=60)
    if page:
        app.run()
        app.switch_page(page)  # a troca de página limpa a URL; os params vêm depois
    for key, value in params.items():
        app.query_params[key] = value
    app.run()
    assert not app.exception, [error.message for error in app.exception]
    return app


def metric(app, label):
    return next(item.value for item in app.metric if item.label == label)


def test_season_page(lake_root):
    app = run()
    assert app.title[0].value == "Temporada 2024"
    assert metric(app, "Líder em pontos") == "A. Alpha"
    assert metric(app, "Vantagem") == "24 pts"
    assert metric(app, "Vencedor") == "A. Alpha"  # último GP selecionado


def test_season_comes_from_url(lake_root):
    app = run(ano="2023")
    assert app.title[0].value == "Temporada 2023"
    assert metric(app, "Líder em pontos") == "B. Beta"


def test_driver_page_follows_url(lake_root):
    app = run("views/pilotos.py", piloto="Bruno Beta")  # o bind usa o rótulo exibido
    assert app.title[0].value == "Bruno Beta"
    assert metric(app, "Vitórias") == "1"
    assert metric(app, "À frente na corrida") == "1/3"


def test_forecast_page_with_api(lake_root, api_online):
    app = run("views/previsao.py")
    assert app.title[0].value == "Previsão 2024"
    assert metric(app, "Candidatos") == "4"
    assert metric(app, "Data de referência") == "20/03/2024"
    assert any("simulação" in item.value for item in app.info)


def test_forecast_page_without_api(lake_root, monkeypatch):
    monkeypatch.setattr(
        model_api.requests,
        "get",
        lambda *a, **k: reply({"detail": "Model not found"}, 500),
    )
    app = run("views/previsao.py")
    assert "Previsão indisponível" in app.warning[0].value
    assert "Model not found" in app.warning[0].value


def test_data_page(lake_root):
    app = run("views/dados.py")
    assert app.title[0].value == "Dados do lake"
    assert metric(app, "Tabelas Delta") == "5"
    assert metric(app, "Arquivos Raw") == "1"


def test_missing_lake_stops_with_message(tmp_path, monkeypatch):
    monkeypatch.setenv("LAKE_ROOT", str(tmp_path / "vazio"))
    app = AppTest.from_file(MAIN, default_timeout=60).run()
    assert "Tabela Delta indisponível" in app.sidebar.error[0].value
