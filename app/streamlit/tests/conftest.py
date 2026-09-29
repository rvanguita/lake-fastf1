"""Mini-lake Delta coerente para os testes (sem Spark, API ou dados reais).

Temporada 2024, três etapas, equipes Blue (a, b) e Green (c, d):
- R1: a vence de P2 no grid; b P2 saindo da pole; c abandona.
- R2: b vence da pole; sprint b 8 / a 7; d estreia e não larga (DNS).
- R3: a vence da pole; c P2 saindo de P4; b abandona.
Final: a 75, b 51, c 33, d 0. Em 2023, uma etapa: b 25, a 18.
A ABT tem d em 2024-03-01, antes da estreia (deve ficar fora dos candidatos).
"""

from datetime import date, datetime
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pytest
from deltalake import write_deltalake

import lake
import metrics
import model_api

DRIVERS = {
    "a": ("Ana Alpha", "ALP", "blue", "Blue", "3671C6"),
    "b": ("Bruno Beta", "BET", "blue", "Blue", "3671C6"),
    "c": ("Carla Gamma", "GAM", "green", "Green", "00D7B6"),
    "d": ("Davi Delta", "DEL", "green", "Green", "00D7B6"),
}
EVENTS = {
    (2023, 1): (date(2023, 3, 5), "GP Zero"),
    (2024, 1): (date(2024, 3, 1), "GP Um"),
    (2024, 2): (date(2024, 3, 10), "GP Dois"),
    (2024, 3): (date(2024, 3, 20), "GP Três"),
}
# season, round, driver, points, order, grid, finish, status, started
RACES = [
    (2023, 1, "b", 25.0, 1, 1, 1, "FINISHED", True),
    (2023, 1, "a", 18.0, 2, 2, 2, "FINISHED", True),
    (2024, 1, "a", 25.0, 1, 2, 1, "FINISHED", True),
    (2024, 1, "b", 18.0, 2, 1, 2, "FINISHED", True),
    (2024, 1, "c", 0.0, 3, 3, None, "DNF", True),
    (2024, 2, "b", 25.0, 1, 1, 1, "FINISHED", True),
    (2024, 2, "a", 18.0, 2, 3, 2, "FINISHED", True),
    (2024, 2, "c", 15.0, 3, 2, 3, "FINISHED", True),
    (2024, 2, "d", 0.0, 4, None, None, "DNS", False),
    (2024, 3, "a", 25.0, 1, 1, 1, "FINISHED", True),
    (2024, 3, "c", 18.0, 2, 4, 2, "FINISHED", True),
    (2024, 3, "b", 0.0, 3, 2, None, "DNF", True),
]
SPRINTS = [(2024, 2, "b", 8.0), (2024, 2, "a", 7.0)]


def _driver_columns(driver_id: str) -> dict:
    name, code, team_id, team, color = DRIVERS[driver_id]
    return {
        "driver_id": driver_id,
        "driver_name": name,
        "abbreviation": code,
        "team_id": team_id,
        "team_name": team,
        "team_color": color,
    }


def build_driver_round() -> pd.DataFrame:
    rows = []
    for season, number, driver, points, order, grid, finish, status, started in RACES:
        event_date, event = EVENTS[(season, number)]
        rows.append(
            {
                "season": season,
                "round_number": number,
                "event_date": event_date,
                "event_name": event,
                **_driver_columns(driver),
                "points": points,
                "result_order": order,
                "official_grid": grid,
                "official_finish": finish,
                "result_status": status,
                "started": started,
            }
        )
    frame = pd.DataFrame(rows)
    frame["official_grid"] = frame["official_grid"].astype("Int32")
    frame["official_finish"] = frame["official_finish"].astype("Int32")
    return frame


def build_standings() -> pd.DataFrame:
    points: dict[tuple, float] = {}
    for season, number, driver, value, *_ in RACES:
        points[(season, number, driver)] = (
            points.get((season, number, driver), 0) + value
        )
    for season, number, driver, value in SPRINTS:
        points[(season, number, driver)] += value
    rows = []
    for season in (2023, 2024):
        rounds = sorted(n for s, n in EVENTS if s == season)
        debut: dict[str, int] = {}
        for s, n, driver, *_ in RACES:
            if s == season:
                debut[driver] = min(debut.get(driver, n), n)
        cumulative = dict.fromkeys(debut, 0.0)
        for number in rounds:
            present = [d for d in debut if debut[d] <= number]
            for driver in present:
                cumulative[driver] += points.get((season, number, driver), 0.0)
            ranking = pd.Series({d: cumulative[d] for d in present}).rank(
                method="min", ascending=False
            )
            event_date, event = EVENTS[(season, number)]
            for driver in present:
                rows.append(
                    {
                        "season": season,
                        **_driver_columns(driver),
                        "round_number": number,
                        "event_date": event_date,
                        "event_name": event,
                        "round_points": points.get((season, number, driver), 0.0),
                        "cumulative_points": cumulative[driver],
                        "championship_rank": int(ranking[driver]),
                    }
                )
    return pd.DataFrame(rows)


def build_bronze() -> pd.DataFrame:
    rows = []
    sessions = [(*race[:4], "Race") for race in RACES] + [
        (*sprint, "Sprint") for sprint in SPRINTS
    ]
    for season, number, driver, points, mode in sessions:
        name, _, _, team, color = DRIVERS[driver]
        event_date, _ = EVENTS[(season, number)]
        rows.append(
            {
                "Year": season,
                "RoundNumber": number,
                "Mode": mode,
                "Date": datetime.combine(event_date, datetime.min.time()),
                "DriverId": driver,
                "FullName": name,
                "TeamName": team,
                "TeamColor": color,
                "Points": points,
                "DriverNumber": str(ord(driver) - 96),
                "HeadshotUrl": "",
                "CountryCode": "",
            }
        )
    return pd.DataFrame(rows)


def build_abt() -> pd.DataFrame:
    rows = []
    for dt_ref, drivers in [
        (date(2024, 3, 1), "abcd"),
        (date(2024, 3, 10), "abcd"),
        (date(2024, 3, 20), "abcd"),
    ]:
        for index, driver in enumerate(drivers):
            row = {"dt_ref": dt_ref, "DriverId": driver, "flChampion": 0}
            for metric in metrics.WINDOW_METRICS:
                for window in metrics.WINDOWS:
                    row[f"{metric}_{window}"] = float(window - index)
            row["qty_1place_r_20"] = float(3 - index)
            rows.append(row)
    return pd.DataFrame(rows)


def write_lake(root: Path) -> Path:
    tables = {
        ("bronze", "results"): build_bronze(),
        ("silver", "mart_standings"): build_standings(),
        ("silver", "mart_driver_round"): build_driver_round(),
        ("silver", "champions"): pd.DataFrame(
            {
                "Year": [2023, 2024],
                "DriverId": ["b", "a"],
                "total_points": [25.0, 75.0],
                "wins": [1, 2],
                "second_places": [0, 1],
                "third_places": [0, 0],
                "rank_driver": [1, 1],
            }
        ),
        ("silver", "tb_abt"): build_abt(),
    }
    for (layer, name), frame in tables.items():
        write_deltalake(
            str(root / layer / name), pa.Table.from_pandas(frame, preserve_index=False)
        )
    raw = root / "raw" / "results"
    raw.mkdir(parents=True)
    build_bronze().head(2).to_parquet(raw / "2024_01_R.parquet")
    return root


def clear_caches() -> None:
    for cached in (lake._read, lake._version, model_api._get, model_api._post):
        cached.clear()


@pytest.fixture
def lake_root(tmp_path, monkeypatch):
    root = write_lake(tmp_path / "data")
    monkeypatch.setenv("LAKE_ROOT", str(root))
    clear_caches()
    yield root
    clear_caches()


@pytest.fixture
def standings():
    return build_standings()


@pytest.fixture
def driver_round():
    return build_driver_round()


@pytest.fixture
def bronze():
    return build_bronze()


@pytest.fixture
def abt():
    return build_abt()
