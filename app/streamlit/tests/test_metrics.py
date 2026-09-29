import pandas as pd
import pytest

import metrics


def season(frame, year=2024, column="season"):
    return frame[frame[column].eq(year)]


def test_standings_table_combines_marts(standings, driver_round):
    table = metrics.standings_table(season(standings), season(driver_round))
    by_id = table.set_index("driver_id")
    assert table["driver_id"].tolist() == ["a", "b", "c", "d"]
    assert by_id["points"].tolist() == [75, 51, 33, 0]
    assert by_id["wins"].tolist() == [2, 1, 0, 0]
    assert by_id["podiums"].tolist() == [3, 2, 2, 0]
    assert by_id["poles"].tolist() == [1, 2, 0, 0]
    assert by_id["dnfs"].tolist() == [0, 1, 1, 0]
    # Forma = pontos por rodada (Race + Sprint), só as rodadas disputadas.
    assert by_id.loc["b", "form"] == [18, 33, 0]
    assert by_id.loc["d", "form"] == [0, 0]


def test_season_summary(standings, driver_round):
    summary = metrics.season_summary(season(standings), season(driver_round))
    assert summary["leader"] == "Ana Alpha"
    assert summary["gap"] == 24
    assert summary["winners"] == 2
    assert (summary["races"], summary["rounds"]) == (3, 3)
    assert summary["last_event"] == "GP Três"
    assert not summary["tied"]


def test_title_fight_keeps_order_and_full_season(standings):
    frame = metrics.title_fight(season(standings), top=2)
    assert frame["driver_id"].unique().tolist() == ["a", "b"]
    assert frame.groupby("driver_id")["round_number"].count().tolist() == [3, 3]


def test_constructors_attribute_points_per_session(bronze):
    table = metrics.constructors(season(bronze, column="Year"))
    assert table["team"].tolist() == ["Blue", "Green"]
    assert table["points"].tolist() == [126, 33]


def test_race_result_labels_and_nullable_ints(driver_round):
    third = metrics.race_result(season(driver_round), 3)
    assert third["position"].tolist() == ["1", "2", "DNF"]
    assert third["status"].tolist() == ["Concluiu", "Concluiu", "Abandono"]
    assert third["gained"].tolist()[:2] == [0, 2]
    assert pd.isna(third["gained"].iloc[2])
    second = metrics.race_result(season(driver_round), 2).set_index("driver_id")
    assert second.loc["d", "status"] == "Não largou"
    assert pd.isna(second.loc["d", "official_grid"])  # float NaN, não pd.NA


def test_driver_season_and_race_by_race(standings, driver_round):
    profile = metrics.driver_season(season(standings), season(driver_round), "a")
    assert (profile["rank"], profile["points"], profile["wins"]) == (1, 75, 2)
    assert (profile["podiums"], profile["poles"], profile["dnfs"]) == (3, 1, 0)
    assert profile["avg_finish"] == pytest.approx(4 / 3)
    rounds = metrics.race_by_race(season(driver_round), "c")
    assert rounds["position"].tolist() == ["DNF", "3", "2"]
    assert metrics.driver_season(season(standings), season(driver_round), "zz") == {}


def test_teammate_duels(driver_round):
    duel = metrics.teammate_duels(season(driver_round), "a").iloc[0]
    assert duel["teammate"] == "Bruno Beta"
    assert (duel["races"], duel["race_ahead"]) == (3, 2)
    assert (duel["grid_ahead"], duel["grid_races"]) == (1, 3)
    assert (duel["points"], duel["points_mate"]) == (68, 43)
    # d não largou em R2: sem grid, o duelo de grid não conta essa corrida.
    duel_c = metrics.teammate_duels(season(driver_round), "c").iloc[0]
    assert (duel_c["races"], duel_c["grid_races"]) == (1, 0)


def test_career_by_season(standings, driver_round):
    history = metrics.career(
        standings[standings["driver_id"].eq("a")],
        driver_round[driver_round["driver_id"].eq("a")],
    )
    assert history["season"].tolist() == [2023, 2024]
    assert history["rank"].tolist() == [2, 1]
    assert history["points"].tolist() == [18, 75]
    assert history["wins"].tolist() == [0, 2]
    assert history["poles"].tolist() == [0, 1]


def test_window_form_reads_every_window(abt):
    table = metrics.window_form(abt.iloc[0])
    assert table["window"].tolist() == [f"Últimas {w}" for w in metrics.WINDOWS]
    assert table.loc[0, "Vitórias"] == 5


def test_candidates_exclude_drivers_before_debut(abt, standings):
    debuts = season(standings).groupby("driver_id")["event_date"].min()
    candidates = metrics.candidates(abt, debuts)
    first = candidates[candidates["prediction_group"].eq("2024-03-01")]
    assert first["DriverId"].tolist() == ["a", "b", "c"]
    assert "2024-03-10:d" in set(candidates["id"])
    frame = metrics.forecast_frame(
        {"2024-03-01:a": {"probability": 0.6}, "2024-03-01:b": {"probability": 0.4}},
        candidates,
    )
    assert frame.set_index("driver_id")["probability"].to_dict() == {"a": 0.6, "b": 0.4}


@pytest.mark.parametrize(
    "name,label",
    [
        ("qty_1place_r_20", "Vitórias em corridas · últimas 20 sessões"),
        ("qty_pos5_S_5", "Chegadas no top 5 em sprints · últimas 5 sessões"),
        ("total_points_50", "Pontos · últimas 50 sessões"),
        (
            "avg_overtake_r_10",
            "Posições ganhas (média) em corridas · últimas 10 sessões",
        ),
        ("unknown_feature", "unknown_feature"),
    ],
)
def test_feature_labels(name, label):
    assert metrics.feature_label(name) == label


def test_small_helpers():
    assert metrics.short_name("Kimi Antonelli") == "K. Antonelli"
    assert metrics.short_name("Senna") == "Senna"
    assert metrics.line_dashes([("a", "X"), ("b", "Y"), ("c", "X")]) == {
        "a": "solid",
        "b": "solid",
        "c": "dot",
    }
    assert metrics.team_color("FF8000") == "#FF8000"
    assert metrics.team_color("0600EF") != "#0600EF"  # clareada até 3:1
    assert metrics.team_color("") == metrics.FALLBACK_COLOR


def test_quality_checks_report_violations(standings, driver_round, abt):
    champions = pd.DataFrame({"Year": [2023, 2024]})
    checks = metrics.quality_checks(
        standings, driver_round, abt[["dt_ref", "DriverId"]], champions
    )
    assert checks["status"].eq("ok").all()
    broken = metrics.quality_checks(
        pd.concat([standings, standings.head(1)]),
        driver_round.assign(result_status="WHATEVER"),
        abt[["dt_ref", "DriverId"]],
        pd.DataFrame({"Year": [2024, 2024]}),
    ).set_index(["check", "table"])
    assert broken.loc[("Chave única", "mart_standings"), "failures"] == 1
    assert broken.loc[("Status no domínio", "mart_driver_round"), "failures"] == 12
    assert broken.loc[("Um líder por temporada", "champions"), "status"] == "falha"


def test_coverage_flags_partial_and_current(bronze):
    extra = bronze[bronze["Year"].eq(2024)].assign(Year=2022)
    table = metrics.coverage(pd.concat([bronze, extra]), current=2024).set_index(
        "season"
    )
    assert table["races"].to_dict() == {2022: 3, 2023: 1, 2024: 3}
    assert table["status"].to_dict() == {
        2022: "completa",
        2023: "parcial",
        2024: "em andamento",
    }
