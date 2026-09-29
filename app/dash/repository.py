"""Leituras Delta projetadas por temporada e cliente da API versionada."""

from __future__ import annotations

import json
import logging
import math
import os
import time
from dataclasses import dataclass, field
from datetime import date
from functools import lru_cache
from pathlib import Path

import pandas as pd
import requests
from deltalake import DeltaTable
from deltalake.exceptions import DeltaError
from dotenv import load_dotenv

from analytics import NAMES, prepare_results

ROOT = next(
    (
        parent
        for parent in Path(__file__).resolve().parents
        if (parent / "docker-compose.yml").is_file()
    ),
    Path(__file__).resolve().parent,
)
load_dotenv(ROOT / ".env", override=False)
LOG = logging.getLogger(__name__)
# Intervalo máximo até uma nova versão Delta aparecer sem reiniciar o processo.
VERSION_TTL = 60


class DataUnavailable(RuntimeError):
    """Falha de acesso ou contrato que pode ser apresentada sem detalhes internos."""


@dataclass(frozen=True)
class Settings:
    bronze: str = field(
        default_factory=lambda: (
            os.getenv("TABLE_PATH_BRONZE") or str(ROOT / "data/bronze/results")
        )
    )
    abt: str = field(
        default_factory=lambda: (
            os.getenv("TABLE_PATH_SILVER") or str(ROOT / "data/silver/tb_abt")
        )
    )
    api: str = field(
        default_factory=lambda: (
            os.getenv("API_URL") or "http://localhost:5002"
        ).rstrip("/")
    )


def _clock() -> float:
    return time.time()


def _version(path: str) -> int:
    return _version_at(path, int(_clock() // VERSION_TTL))


@lru_cache(maxsize=8)
def _version_at(path: str, bucket: int) -> int:
    try:
        return DeltaTable(path).version()
    except (DeltaError, OSError) as exc:
        LOG.warning("Delta indisponível em %s: %s", path, exc)
        raise DataUnavailable(
            "Tabela Delta indisponível. Confira os caminhos e execute a etapa de dados correspondente."
        ) from exc


@lru_cache(maxsize=16)
def _read(
    path: str, version: int, columns: tuple[str, ...], filters: tuple = ()
) -> pd.DataFrame:
    try:
        table = DeltaTable(path, version=version)
        available = {f.name for f in table.schema().fields}
        selected = [c for c in columns if c in available]
        if not selected:
            raise ValueError("Nenhuma coluna solicitada está disponível")
        return table.to_pandas(columns=selected, filters=list(filters) or None)
    except (DeltaError, OSError, ValueError, TypeError) as exc:
        LOG.exception("Não foi possível ler Delta")
        raise DataUnavailable(
            "Não foi possível ler a tabela Delta; verifique seu schema e os arquivos de dados."
        ) from exc


@lru_cache(maxsize=32)
def _prepared(path: str, version: int, years: tuple[int, ...]) -> pd.DataFrame:
    frame = _read(path, version, tuple(NAMES), (("Year", "in", years),))
    try:
        return prepare_results(frame)
    except ValueError as exc:
        raise DataUnavailable(str(exc)) from exc


def _get(api: str, endpoint: str) -> dict:
    response = requests.get(f"{api}/{endpoint}", timeout=(3, 15))
    response.raise_for_status()
    value = response.json()
    if not isinstance(value, dict):
        raise TypeError("Resposta da API deve ser um objeto")
    return value


@lru_cache(maxsize=8)
def _model_metadata(api: str, bucket: int) -> tuple[dict, dict]:
    info = _get(api, "model_info")
    try:
        card = _get(api, "v1/model-card")
    except (requests.RequestException, ValueError, TypeError):
        card = {}
    return info, card


def validate_predictions(body: dict, identifiers: list[str]) -> pd.DataFrame:
    if not isinstance(body, dict):
        raise TypeError("Resposta de previsão deve ser um objeto")
    predictions = body.get("predictions", {})
    if not isinstance(predictions, dict) or set(predictions) != set(identifiers):
        raise ValueError("A API não retornou todos os candidatos do snapshot")
    rows = []
    for identifier in identifiers:
        value = float(predictions[identifier]["probability"])
        if not math.isfinite(value) or not 0 <= value <= 1:
            raise ValueError("Probabilidade fora do domínio")
        rows.append({"id": identifier, "probability": value})
    if not math.isclose(sum(row["probability"] for row in rows), 1, abs_tol=1e-9):
        raise ValueError("Probabilidades do snapshot não somam 100%")
    return pd.DataFrame(rows)


class Repository:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or Settings()

    def seasons(self) -> list[int]:
        frame = _read(self.settings.bronze, _version(self.settings.bronze), ("Year",))
        return sorted(
            pd.to_numeric(frame["Year"], errors="coerce")
            .dropna()
            .astype(int)
            .unique()
            .tolist(),
            reverse=True,
        )

    def results(self, years: list[int]) -> pd.DataFrame:
        if not years:
            raise DataUnavailable("Selecione pelo menos uma temporada.")
        # Cópia: o cache é compartilhado entre callbacks e requisições.
        return _prepared(
            self.settings.bronze,
            _version(self.settings.bronze),
            tuple(sorted(set(map(int, years)))),
        ).copy()

    def snapshots(self, year: int) -> list[str]:
        frame = _read(
            self.settings.abt,
            _version(self.settings.abt),
            ("dt_ref",),
            (("dt_ref", ">=", date(year, 1, 1)), ("dt_ref", "<", date(year + 1, 1, 1))),
        )
        return sorted(
            pd.to_datetime(frame["dt_ref"]).dt.strftime("%Y-%m-%d").unique().tolist(),
            reverse=True,
        )

    def forecast(self, year: int, snapshot: str) -> tuple[pd.DataFrame, dict]:
        if date.fromisoformat(snapshot).year != int(year):
            raise DataUnavailable(
                "A data da previsão não pertence à temporada selecionada."
            )
        try:
            info, card = _model_metadata(self.settings.api, int(time.time() // 300))
            features = info.get("features", [])
            if not features or not all(isinstance(name, str) for name in features):
                raise ValueError("Modelo sem contrato de features")
            raw = _read(
                self.settings.abt,
                _version(self.settings.abt),
                ("DriverId", "dt_ref", *features),
                (("dt_ref", "=", date.fromisoformat(snapshot)),),
            ).copy()
            if not set(features).issubset(raw.columns):
                raise ValueError("Features do modelo ausentes na ABT")
            if raw.duplicated(["DriverId", "dt_ref"]).any():
                raise ValueError("Candidatos duplicados na ABT")
            results = self.results([year])
            # Não usa metadados futuros nem inclui pilotos que ainda não estrearam.
            results = results[results["date"].dt.normalize() <= pd.Timestamp(snapshot)]
            people = results.sort_values("date").drop_duplicates(
                "driver_id", keep="last"
            )[["driver_id", "driver", "team", "color"]]
            frame = raw.merge(
                people, left_on="DriverId", right_on="driver_id", how="inner"
            )
            if frame.empty:
                raise DataUnavailable(
                    "Não há candidatos com participação registrada nesta data."
                )
            if set(people["driver_id"]) != set(frame["driver_id"]):
                raise ValueError("ABT incompleta para os participantes da temporada")
            frame["id"] = snapshot + ":" + frame["driver_id"]
            frame["prediction_group"] = snapshot
            payload = json.loads(
                frame[["id", "prediction_group", *features]].to_json(orient="records")
            )
            body = _predict(
                self.settings.api,
                json.dumps(payload, sort_keys=True),
                int(time.time() // 300),
            )
            predictions = validate_predictions(body, frame["id"].tolist())
            output = frame[["id", "driver_id", "driver", "team", "color"]].merge(
                predictions, on="id"
            )
            return output.sort_values("probability", ascending=False), {
                "card": card,
                "metadata": body.get("metadata", {}),
                "snapshot": snapshot,
            }
        except (
            requests.RequestException,
            ValueError,
            KeyError,
            TypeError,
            OverflowError,
        ) as exc:
            LOG.warning("Previsão indisponível: %s", exc)
            raise DataUnavailable(_forecast_reason(exc, self.settings.api)) from exc


def _forecast_reason(exc: Exception, api: str) -> str:
    """Mensagem acionável sem expor traceback: onde a cadeia de previsão parou."""
    if isinstance(exc, requests.HTTPError) and exc.response is not None:
        try:
            detail = exc.response.json().get("detail")
        except ValueError:
            detail = None
        return (
            f"A API respondeu {exc.response.status_code}"
            + (f" ({detail})" if isinstance(detail, str) else "")
            + ". Confira se o modelo está registrado no MLflow."
        )
    if isinstance(exc, requests.RequestException):
        return f"A API de previsão não respondeu em {api}."
    return (
        "A resposta da API ou a ABT não segue o contrato esperado; "
        "confira a compatibilidade entre modelo e features."
    )


@lru_cache(maxsize=16)
def _predict(api: str, payload: str, bucket: int) -> dict:
    response = requests.post(
        f"{api}/v1/predict",
        json={"values": json.loads(payload), "include_intervals": False},
        timeout=(3, 45),
    )
    response.raise_for_status()
    body = response.json()
    validate_predictions(body, [row["id"] for row in json.loads(payload)])
    return body


_REPOSITORY: Repository | None = None


def get_repository() -> Repository:
    """Instância única do processo; páginas e callbacks resolvem por aqui."""
    global _REPOSITORY
    if _REPOSITORY is None:
        _REPOSITORY = Repository()
    return _REPOSITORY


def set_repository(repository) -> None:
    """Injeta outra implementação (testes) ou restaura a padrão com `None`."""
    global _REPOSITORY
    _REPOSITORY = repository


def clear_caches() -> None:
    for cached in (_version_at, _read, _prepared, _model_metadata, _predict):
        cached.cache_clear()
