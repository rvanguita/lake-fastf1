"""Cliente da API de previsão. Só respostas válidas entram em cache: uma falha é
levantada como `ModelUnavailable` e a próxima renderização tenta de novo."""

from __future__ import annotations

import json
import math
import os

import pandas as pd
import requests
import streamlit as st

API_URL = (os.getenv("API_URL") or "http://localhost:5002").rstrip("/")
# Mesmo valor do SimpleImputer do treino para features ausentes.
FEATURE_FILL = -10000


class ModelUnavailable(RuntimeError):
    """A API não entregou uma resposta utilizável; a mensagem explica o motivo."""


def _reason(exc: Exception) -> str:
    if isinstance(exc, requests.HTTPError) and exc.response is not None:
        try:
            detail = exc.response.json().get("detail")
        except ValueError:
            detail = None
        suffix = f" ({detail})" if isinstance(detail, str) else ""
        return f"A API respondeu {exc.response.status_code}{suffix}."
    if isinstance(exc, requests.RequestException):
        return f"A API de previsão não respondeu em {API_URL}."
    return f"Resposta fora do contrato esperado: {exc}"


@st.cache_data(ttl=300, show_spinner=False)
def _get(api: str, endpoint: str) -> dict:
    response = requests.get(f"{api}/{endpoint}", timeout=(3, 30))
    response.raise_for_status()
    body = response.json()
    if not isinstance(body, dict):
        raise TypeError("a resposta deve ser um objeto JSON")
    return body


@st.cache_data(ttl=600, max_entries=16, show_spinner=False)
def _post(api: str, endpoint: str, body: str) -> dict:
    response = requests.post(
        f"{api}/{endpoint}",
        data=body,
        headers={"Content-Type": "application/json"},
        timeout=(3, 120),
    )
    response.raise_for_status()
    result = response.json()
    if not isinstance(result, dict):
        raise TypeError("a resposta deve ser um objeto JSON")
    return result


def _call(function, *args) -> dict:
    try:
        return function(API_URL, *args)
    except (requests.RequestException, ValueError, TypeError) as exc:
        raise ModelUnavailable(_reason(exc)) from exc


def model_info() -> dict:
    return _call(_get, "model_info")


def model_card() -> dict:
    return _call(_get, "v1/model-card")


def payload(candidates: pd.DataFrame, features: list[str]) -> list[dict]:
    """Linhas `id`, `prediction_group` e features, na ordem exigida pelo modelo."""
    missing = [name for name in features if name not in candidates.columns]
    if missing:
        raise ModelUnavailable(
            f"A ABT não tem {len(missing)} features exigidas pelo modelo publicado."
        )
    frame = candidates[["id", "prediction_group", *features]].copy()
    frame[features] = frame[features].astype(float).fillna(FEATURE_FILL)
    return json.loads(frame.to_json(orient="records"))


def predict(
    candidates: pd.DataFrame, features: list[str], *, intervals: bool = False
) -> dict[str, dict]:
    rows = payload(candidates, features)
    body = json.dumps({"values": rows, "include_intervals": intervals}, sort_keys=True)
    predictions = _call(_post, "v1/predict", body).get("predictions")
    identifiers = {row["id"] for row in rows}
    if not isinstance(predictions, dict) or set(predictions) != identifiers:
        raise ModelUnavailable("A API não devolveu todos os candidatos enviados.")
    for value in predictions.values():
        probability = value.get("probability") if isinstance(value, dict) else None
        if not isinstance(probability, int | float) or not (
            math.isfinite(probability) and 0 <= probability <= 1
        ):
            raise ModelUnavailable("A API devolveu probabilidade fora de [0, 1].")
    return predictions


def explain(row: pd.DataFrame, features: list[str], top_n: int = 12) -> dict:
    body = json.dumps(
        {"values": payload(row, features), "top_n": top_n, "include_intervals": False},
        sort_keys=True,
    )
    explanations = _call(_post, "v1/explain", body).get("explanations") or {}
    identifier = row["id"].iloc[0]
    if identifier not in explanations:
        raise ModelUnavailable("A API não devolveu explicação para o piloto.")
    return explanations[identifier]
