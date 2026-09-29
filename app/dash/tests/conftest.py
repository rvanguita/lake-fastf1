import json

import pandas as pd
import plotly.utils
import pytest

import main  # noqa: F401  (registra as páginas antes de importá-las nos testes)
import repository
from analytics import prepare_results
from repository import DataUnavailable

COLUMNS = [
    "Year",
    "RoundNumber",
    "Mode",
    "Date",
    "DriverId",
    "FullName",
    "Abbreviation",
    "TeamName",
    "ClassifiedPosition",
    "GridPosition",
    "Points",
    "Status",
    "Time",
    "Laps",
]


@pytest.fixture
def raw():
    # Intencionais: a troca de equipe de a, a ausência de b na etapa 2, o grid 0
    # (pit lane) de b, o DNS de d e o 2º colocado retardatário da etapa 3.
    values = [
        (2024, 1, "Race", "2024-03-01", "a", "Alpha", "ALP", "Red", "1", 2, 25, "Finished", 5400.0, 50),
        (2024, 1, "Race", "2024-03-01", "b", "Beta", "BET", "Blue", "2", 0, 18, "Finished", 3.2, 50),
        (2024, 1, "Sprint", "2024-03-02", "b", "Beta", "BET", "Blue", "1", 1, 8, "Finished", 1800.0, 20),
        (2024, 1, "Sprint", "2024-03-02", "a", "Alpha", "ALP", "Red", "2", 2, 7, "Finished", 1.5, 20),
        (2024, 2, "Race", "2024-03-10", "a", "Alpha", "ALP", "Blue", "R", 1, 0, "Engine", None, 20),
        (2024, 2, "Race", "2024-03-10", "c", "Gamma", "GAM", "Green", "1", 3, 25, "Finished", 5500.0, 50),
        (2024, 2, "Race", "2024-03-10", "d", "Delta", "DEL", "Green", "W", 4, 0, "Did not start", None, 0),
        (2024, 3, "Race", "2024-03-20", "a", "Alpha", "ALP", "Blue", "2", 1, 18, "+1 Lap", None, 49),
        (2024, 3, "Race", "2024-03-20", "b", "Beta", "BET", "Blue", "1", 2, 25, "Finished", 5300.0, 50),
    ]  # fmt: skip
    frame = pd.DataFrame(values, columns=COLUMNS)
    frame["Date"] = pd.to_datetime(frame["Date"])
    frame["EventName"] = frame["RoundNumber"].map(lambda r: f"GP {r}")
    frame["Location"] = "Circuito"
    frame["Country"] = "País"
    frame["TeamColor"] = "3987E5"
    # Retired pode ter Position numérica; isso não o transforma em vencedor.
    frame["Position"] = pd.to_numeric(
        frame["ClassifiedPosition"], errors="coerce"
    ).fillna(1)
    return frame


@pytest.fixture
def results(raw):
    return prepare_results(raw)


PREDICTIONS = pd.DataFrame(
    {
        "id": ["2024-03-10:a", "2024-03-10:b", "2024-03-10:c"],
        "driver_id": ["a", "b", "c"],
        "driver": ["Alpha", "Beta", "Gamma"],
        "team": ["Blue", "Blue", "Green"],
        "color": ["#3987e5"] * 3,
        "probability": [0.2, 0.3, 0.5],
    }
)
CONTEXT = {
    "card": {
        "status": "experimental",
        "trained_through": 2023,
        "evaluations": [
            {"season": 2022, "top1_accuracy": 1.0, "baseline_accuracy": 0.5},
            {"season": 2023, "top1_accuracy": 0.5, "baseline_accuracy": 0.5},
        ],
    },
    "metadata": {"status": "experimental"},
    "snapshot": "2024-03-10",
}


class FakeRepository:
    """Repositório em memória com o mesmo contrato público do real."""

    def __init__(self, results, *, snapshots=("2024-03-10",), forecast_error=None):
        self._results = results
        self._snapshots = list(snapshots)
        self.forecast_error = forecast_error
        self.forecast_calls = []

    def seasons(self):
        return sorted(self._results["season"].unique().tolist(), reverse=True)

    def results(self, years):
        frame = self._results[self._results["season"].isin(years)].copy()
        frame.attrs = dict(self._results.attrs)
        return frame

    def snapshots(self, year):
        return [value for value in self._snapshots if value.startswith(str(year))]

    def forecast(self, year, snapshot):
        self.forecast_calls.append((year, snapshot))
        if self.forecast_error:
            raise DataUnavailable(self.forecast_error)
        return PREDICTIONS.copy(), CONTEXT


@pytest.fixture
def fake(results):
    repo = FakeRepository(results)
    repository.set_repository(repo)
    yield repo
    repository.set_repository(None)


def rendered(component) -> str:
    """Serializa como o Dash faria; falha se algo não for JSON."""
    encoded = json.dumps(component, cls=plotly.utils.PlotlyJSONEncoder)
    return json.dumps(json.loads(encoded), ensure_ascii=False)
