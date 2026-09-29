import pandas as pd

import charts
import metrics


def test_identity_uses_team_colors_and_dots_the_teammate():
    frame = pd.DataFrame(
        {
            "driver_id": ["a", "b", "c"],
            "team_name": ["X", "X", "Y"],
            "color": ["#3671C6", "#3671C6", "#FF8000"],
        }
    )
    styles = charts.identity_styles(frame)
    assert styles == {
        "a": ("#3671C6", "solid"),
        "b": ("#3671C6", "dot"),
        "c": ("#FF8000", "solid"),
    }


def test_identity_falls_back_to_palette_without_team_colors():
    frame = pd.DataFrame(
        {
            "driver_id": ["a", "b"],
            "team": ["X", "X"],
            "color": [metrics.FALLBACK_COLOR] * 2,
        }
    )
    assert charts.identity_styles(frame) == {
        "a": (charts.SERIES[0], "solid"),
        "b": (charts.SERIES[1], "solid"),
    }


def test_race_by_race_keeps_round_order_with_retirements(driver_round):
    rounds = metrics.race_by_race(driver_round[driver_round["season"].eq(2024)], "b")
    figure = charts.race_by_race(rounds, "#3671C6")
    assert list(figure.layout.xaxis.categoryarray) == ["R01", "R02", "R03"]
    assert [trace.name for trace in figure.data if trace.name] == [
        "Largada",
        "Chegada",
        "Não completou",
    ]
