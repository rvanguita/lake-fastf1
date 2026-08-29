"""Unit tests for the pure (pandas-only) helpers in ``app/streamlit/main.py``.

The ``render_*`` functions need a live Streamlit runtime and are out of scope;
only ``format_color``, ``_rank_by``, ``_color_map``, ``get_id_predictions`` and
the ``compute_*`` aggregators are exercised here.
"""

from unittest.mock import Mock

import numpy as np
import pandas as pd
import pytest

import main

# ── format_color ────────────────────────────────────────────────────────────

@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, "#ffffff"),
        ("#AABBCC", "#aabbcc"),
        ("1A2B3C", "#1a2b3c"),
        ("#already", "#already"),
    ],
)
def test_format_color(value, expected):
    assert main.format_color(value) == expected


# ── _rank_by ────────────────────────────────────────────────────────────────

def test_rank_by_sorts_desc_and_prepends_rank():
    df = pd.DataFrame({"FullName": ["a", "b", "c"], "Points": [10, 30, 20]})
    out = main._rank_by(df)

    assert next(iter(out.columns)) == "Rank"
    assert out["Points"].tolist() == [30, 20, 10]
    assert out["Rank"].tolist() == [1, 2, 3]


def test_rank_by_custom_column():
    df = pd.DataFrame({"x": [1, 2], "Wins": [5, 2]})
    out = main._rank_by(df, col="Wins")
    assert out["Wins"].tolist() == [5, 2]
    assert out["Rank"].tolist() == [1, 2]


# ── _color_map ──────────────────────────────────────────────────────────────

@pytest.fixture
def team_color_df():
    return pd.DataFrame(
        {
            "TeamName": ["RB", "RB", "McLaren"],
            "TeamColor": ["#aaa", "#bbb", "#ccc"],
        }
    )


def test_color_map_keep_last(team_color_df):
    assert main._color_map(team_color_df, "TeamName") == {
        "RB": "#bbb",
        "McLaren": "#ccc",
    }


def test_color_map_keep_first(team_color_df):
    assert main._color_map(team_color_df, "TeamName", keep="first")["RB"] == "#aaa"


# ── get_id_predictions ──────────────────────────────────────────────────────

def test_get_id_predictions_calls_api_and_unwraps(monkeypatch):
    resp = Mock()
    resp.json.return_value = {"predictions": {"x": {"1": 0.9}}}
    post = Mock(return_value=resp)
    monkeypatch.setattr(main.requests, "post", post)

    values = pd.DataFrame([{"id": "x", "f": 1}])
    out = main.get_id_predictions(values)

    assert out == {"x": {"1": 0.9}}
    post.assert_called_once_with(
        f"{main.URI_API}/predict", json={"values": [{"id": "x", "f": 1}]}
    )


# ── compute_driver_stats / compute_team_stats ───────────────────────────────

@pytest.fixture
def bronze():
    rows = [
        # Max — RB — wins R1 & R2 from pole-ish grids, P2 in R3
        ("Race", 2024, 1, 1.0, 1.0, 25.0, "Max V", "RB", "#3671C6", "VER", "1"),
        ("Race", 2024, 2, 1.0, 2.0, 25.0, "Max V", "RB", "#3671C6", "VER", "1"),
        ("Race", 2024, 3, 2.0, 1.0, 18.0, "Max V", "RB", "#3671C6", "VER", "2"),
        # Lando — McLaren — P2, P3, DNF
        ("Race", 2024, 1, 2.0, 3.0, 18.0, "Lando N", "McLaren", "#FF8000", "NOR", "2"),
        ("Race", 2024, 2, 3.0, 3.0, 15.0, "Lando N", "McLaren", "#FF8000", "NOR", "3"),
        ("Race", 2024, 3, np.nan, 4.0, 0.0, "Lando N", "McLaren", "#FF8000", "NOR", "R"),
        # noise that must be filtered out
        ("Sprint", 2024, 1, 1.0, 1.0, 8.0, "Max V", "RB", "#3671C6", "VER", "1"),
        ("Race", 2023, 1, 1.0, 1.0, 25.0, "Max V", "RB", "#3671C6", "VER", "1"),
    ]
    return pd.DataFrame(
        rows,
        columns=[
            "Mode", "Year", "RoundNumber", "Position", "GridPosition", "Points",
            "FullName", "TeamName", "TeamColor", "Abbreviation", "ClassifiedPosition",
        ],
    )


def test_compute_driver_stats_empty_when_year_absent(bronze):
    assert main.compute_driver_stats(bronze, 1999).empty


def test_compute_driver_stats_values(bronze):
    stats = main.compute_driver_stats(bronze, 2024).set_index("FullName")

    mx = stats.loc["Max V"]
    assert mx["Rank"] == 1
    assert mx["Races"] == 3
    assert mx["Points"] == 68.0
    assert mx["Wins"] == 2
    assert mx["Podiums"] == 3
    assert mx["Poles"] == 2
    assert mx["DNFs"] == 0
    assert mx["BestFinish"] == 1.0
    assert mx["AvgGain"] == pytest.approx(0.0)
    assert mx["PodiumRate"] == pytest.approx(1.0)

    ln = stats.loc["Lando N"]
    assert ln["Rank"] == 2
    assert ln["Points"] == 33.0
    assert ln["Wins"] == 0
    assert ln["Podiums"] == 2          # NaN finish is not a podium
    assert ln["DNFs"] == 1
    assert ln["AvgFinish"] == pytest.approx(2.5)   # NaN skipped
    assert ln["PodiumRate"] == pytest.approx(2 / 3)


def test_compute_team_stats_values(bronze):
    teams = main.compute_team_stats(bronze, 2024).set_index("TeamName")

    assert teams.loc["RB", "Rank"] == 1
    assert teams.loc["RB", "Points"] == 68.0
    assert teams.loc["RB", "Wins"] == 2
    assert teams.loc["RB", "Podiums"] == 3
    assert teams.loc["McLaren", "Points"] == 33.0
    assert teams.loc["McLaren", "Wins"] == 0
