from datetime import date
from unittest.mock import Mock

import pandas as pd
import pyarrow as pa
import pytest
import requests
from deltalake import write_deltalake

import repository
from repository import DataUnavailable, Repository, Settings, validate_predictions


@pytest.fixture
def repo(tmp_path, raw):
    bronze = str(tmp_path / "results")
    abt = str(tmp_path / "abt")
    write_deltalake(bronze, pa.Table.from_pandas(raw, preserve_index=False))
    features = pd.DataFrame(
        {
            "dt_ref": [date(2024, 3, 2)] * 3,
            "DriverId": ["a", "b", "c"],
            "feature": [25.0, 26.0, 99.0],
            "flChampion": [0, 1, 0],
        }
    )
    write_deltalake(abt, pa.Table.from_pandas(features, preserve_index=False))
    repository.clear_caches()
    return Repository(Settings(bronze, abt, "http://model.test"))


def test_delta_reads_filter_seasons_and_refresh_on_new_version(repo, raw, monkeypatch):
    now = [0.0]
    monkeypatch.setattr(repository, "_clock", lambda: now[0])
    assert repo.seasons() == [2024]
    assert repo.results([2025]).empty
    replacement = raw.assign(Points=0)
    write_deltalake(
        repo.settings.bronze,
        pa.Table.from_pandas(replacement, preserve_index=False),
        mode="overwrite",
    )
    # Dentro do TTL a versão anterior continua servida; depois dele, a nova aparece.
    now[0] = 30.0
    assert repo.results([2024]).points.sum() > 0
    now[0] = 61.0
    assert repo.results([2024]).points.sum() == 0
    assert repo.snapshots(2024) == ["2024-03-02"]
    assert repo.snapshots(2025) == []


def test_read_projects_columns_and_pushes_predicate(repo, monkeypatch):
    real = repository.DeltaTable
    calls = []

    class TableSpy:
        def __init__(self, *args, **kwargs):
            self.table = real(*args, **kwargs)

        def version(self):
            return self.table.version()

        def schema(self):
            return self.table.schema()

        def to_pandas(self, **kwargs):
            calls.append(kwargs)
            return self.table.to_pandas(**kwargs)

    monkeypatch.setattr(repository, "DeltaTable", TableSpy)
    repo.results([2024])
    assert calls[0]["filters"] == [("Year", "in", (2024,))]
    assert "Points" in calls[0]["columns"]
    assert "HeadshotUrl" not in calls[0]["columns"]


def test_missing_table_is_actionable(tmp_path):
    repo = Repository(
        Settings(str(tmp_path / "missing"), "missing", "http://model.test")
    )
    with pytest.raises(DataUnavailable, match="Delta indisponível"):
        repo.seasons()


def test_forecast_uses_snapshot_features_and_only_existing_participants(
    repo, monkeypatch
):
    monkeypatch.setattr(
        repository,
        "_model_metadata",
        lambda *_: ({"features": ["feature"]}, {"trained_through": 2023}),
    )
    post = Mock(
        return_value=Mock(
            json=lambda: {
                "predictions": {
                    "2024-03-02:a": {"probability": 0.4},
                    "2024-03-02:b": {"probability": 0.6},
                },
                "metadata": {"status": "experimental"},
            }
        )
    )
    monkeypatch.setattr(repository.requests, "post", post)
    predictions, context = repo.forecast(2024, "2024-03-02")
    payload = post.call_args.kwargs["json"]
    assert payload["include_intervals"] is False
    assert {r["id"] for r in payload["values"]} == {"2024-03-02:a", "2024-03-02:b"}
    assert all(
        set(r) == {"id", "prediction_group", "feature"} for r in payload["values"]
    )
    assert predictions.set_index("driver_id").loc["a", "team"] == "Red"
    assert predictions.probability.sum() == 1
    assert context["card"]["trained_through"] == 2023


def test_forecast_missing_participant_is_not_renormalized_silently(repo, monkeypatch):
    monkeypatch.setattr(
        repository, "_model_metadata", lambda *_: ({"features": ["feature"]}, {})
    )
    incomplete = pd.DataFrame(
        {"dt_ref": [date(2024, 3, 2)], "DriverId": ["a"], "feature": [25.0]}
    )
    write_deltalake(
        repo.settings.abt,
        pa.Table.from_pandas(incomplete, preserve_index=False),
        mode="overwrite",
        schema_mode="overwrite",
    )
    with pytest.raises(DataUnavailable, match="contrato esperado"):
        repo.forecast(2024, "2024-03-02")


def test_forecast_rejects_year_mismatch(repo):
    with pytest.raises(DataUnavailable, match="não pertence"):
        repo.forecast(2025, "2024-03-02")


def test_api_failure_does_not_break_results(repo, monkeypatch):
    monkeypatch.setattr(
        repository.requests,
        "get",
        Mock(side_effect=requests.ConnectionError("offline")),
    )
    with pytest.raises(DataUnavailable, match="não respondeu em http://model.test"):
        repo.forecast(2024, "2024-03-02")
    assert not repo.results([2024]).empty


def test_missing_model_reports_api_detail(repo, monkeypatch):
    response = requests.Response()
    response.status_code = 500
    response._content = b'{"detail": "Model not found"}'
    monkeypatch.setattr(repository.requests, "get", Mock(return_value=response))
    with pytest.raises(DataUnavailable, match=r"500 \(Model not found\)"):
        repo.forecast(2024, "2024-03-02")


def test_results_are_cached_copies(repo):
    first = repo.results([2024])
    first["points"] = -1
    assert repo.results([2024]).points.min() >= 0


def test_repository_can_be_replaced_for_tests():
    marker = object()
    repository.set_repository(marker)
    assert repository.get_repository() is marker
    repository.set_repository(None)
    assert isinstance(repository.get_repository(), Repository)


@pytest.mark.parametrize(
    "values", [(0.4, 0.4), (-0.1, 1.1), (float("nan"), 1), (float("inf"), 0)]
)
def test_invalid_probabilities_are_rejected(values):
    with pytest.raises(ValueError):
        validate_predictions(
            {
                "predictions": {
                    "a": {"probability": values[0]},
                    "b": {"probability": values[1]},
                }
            },
            ["a", "b"],
        )


def test_partial_api_response_is_rejected():
    with pytest.raises(ValueError):
        validate_predictions({"predictions": {"a": {"probability": 1}}}, ["a", "b"])
