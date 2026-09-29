from unittest.mock import Mock

import pandas as pd
import pytest
import requests

import model_api


@pytest.fixture(autouse=True)
def _clear():
    model_api._get.clear()
    model_api._post.clear()
    yield
    model_api._get.clear()
    model_api._post.clear()


def response(body, status=200):
    reply = requests.Response()
    reply.status_code = status
    reply._content = __import__("json").dumps(body).encode()
    return reply


CANDIDATES = pd.DataFrame(
    {
        "id": ["2024-03-01:a", "2024-03-01:b"],
        "prediction_group": ["2024-03-01", "2024-03-01"],
        "feature": [1.0, None],
        "extra": [9, 9],
    }
)


def test_payload_keeps_model_features_and_fills_missing():
    rows = model_api.payload(CANDIDATES, ["feature"])
    assert rows[0] == {
        "id": "2024-03-01:a",
        "prediction_group": "2024-03-01",
        "feature": 1.0,
    }
    assert rows[1]["feature"] == model_api.FEATURE_FILL
    with pytest.raises(model_api.ModelUnavailable, match="1 features"):
        model_api.payload(CANDIDATES, ["feature", "missing"])


def test_predict_validates_contract(monkeypatch):
    post = Mock(
        return_value=response(
            {
                "predictions": {
                    "2024-03-01:a": {"probability": 0.7},
                    "2024-03-01:b": {"probability": 0.3},
                }
            }
        )
    )
    monkeypatch.setattr(model_api.requests, "post", post)
    predictions = model_api.predict(CANDIDATES, ["feature"], intervals=True)
    assert predictions["2024-03-01:a"]["probability"] == 0.7
    assert '"include_intervals": true' in post.call_args.kwargs["data"]

    model_api._post.clear()
    post.return_value = response(
        {"predictions": {"2024-03-01:a": {"probability": 1.0}}}
    )
    with pytest.raises(model_api.ModelUnavailable, match="todos os candidatos"):
        model_api.predict(CANDIDATES, ["feature"])


def test_failure_is_not_cached_and_reason_is_readable(monkeypatch):
    get = Mock(
        side_effect=[
            response({"detail": "Model not found"}, status=500),
            response({"features": ["feature"]}),
        ]
    )
    monkeypatch.setattr(model_api.requests, "get", get)
    with pytest.raises(model_api.ModelUnavailable, match=r"500 \(Model not found\)"):
        model_api.model_info()
    assert model_api.model_info() == {"features": ["feature"]}
    assert model_api.model_info() == {"features": ["feature"]}  # sucesso em cache
    assert get.call_count == 2


def test_offline_api_message(monkeypatch):
    monkeypatch.setattr(
        model_api.requests, "get", Mock(side_effect=requests.ConnectionError("down"))
    )
    with pytest.raises(model_api.ModelUnavailable, match="não respondeu em"):
        model_api.model_card()


def test_explain_returns_driver_entry(monkeypatch):
    body = {"explanations": {"2024-03-01:a": {"base_value": 0.1, "contributions": []}}}
    monkeypatch.setattr(model_api.requests, "post", Mock(return_value=response(body)))
    assert model_api.explain(CANDIDATES.head(1), ["feature"])["base_value"] == 0.1
