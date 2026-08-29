"""Route tests for ``app/api/main.py``.

MLflow is never contacted: ``main.model_find`` is monkeypatched to return a
minimal fake estimator (or ``None``).
"""

import numpy as np
import pytest
from fastapi.testclient import TestClient

import main


class FakeModel:
    """Just enough of a fitted sklearn estimator for ``predict``."""

    feature_names_in_ = np.array(["f1", "f2"])
    classes_ = np.array([0, 1])

    def predict_proba(self, X):
        return np.tile([0.3, 0.7], (len(X), 1))


@pytest.fixture
def client():
    return TestClient(main.app)


@pytest.fixture
def fake_model(monkeypatch):
    monkeypatch.setattr(main, "model_find", lambda *a, **k: FakeModel())
    return FakeModel()


def test_health_check(client):
    resp = client.get("/health_check")
    assert resp.status_code == 200
    assert resp.json() == {"status": "OK"}


def test_predict_happy_path(client, fake_model):
    payload = {
        "values": [
            {"id": "2024-03-10_max", "f1": 1.0, "f2": 2.0},
            {"id": "2024-03-10_lando", "f1": 3.0, "f2": 4.0},
        ]
    }
    resp = client.post("/predict", json=payload)

    assert resp.status_code == 200
    preds = resp.json()["predictions"]
    assert set(preds) == {"2024-03-10_max", "2024-03-10_lando"}
    # inner keys are model.classes_ (0, 1) serialised as JSON string keys
    assert preds["2024-03-10_max"]["1"] == pytest.approx(0.7)
    assert preds["2024-03-10_max"]["0"] == pytest.approx(0.3)


def test_predict_empty_values_returns_400(client, fake_model):
    resp = client.post("/predict", json={"values": []})
    assert resp.status_code == 400
    assert resp.json()["detail"] == "No features provided"


def test_predict_model_not_found_returns_500(client, monkeypatch):
    monkeypatch.setattr(main, "model_find", lambda *a, **k: None)
    resp = client.post("/predict", json={"values": [{"id": "x", "f1": 1, "f2": 2}]})
    assert resp.status_code == 500
    assert resp.json()["detail"] == "Model not found"


def test_predict_missing_feature_column_returns_422(client, fake_model):
    resp = client.post("/predict", json={"values": [{"id": "x", "f1": 1.0}]})
    assert resp.status_code == 422
    assert "f2" in resp.json()["detail"]


def test_predict_values_not_a_list_returns_422(client, fake_model):
    resp = client.post("/predict", json={"values": "not-a-list"})
    assert resp.status_code == 422
