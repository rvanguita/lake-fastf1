import pandas as pd
import pytest

import analytics
from analytics import prepare_results


def test_driver_table_splits_points_and_keeps_latest_team(results):
    table = analytics.driver_table(results).set_index("driver_id")
    assert table["rank"].to_dict() == {"b": 1, "a": 2, "c": 3, "d": 4}
    alpha = table.loc["a"]
    assert alpha["points"] == 50
    assert alpha["team"] == "Blue"  # última equipe após a transferência
    assert (alpha["wins"], alpha["podiums"], alpha["starts"]) == (1, 2, 3)
    assert (alpha["podium_points"], alpha["other_race_points"]) == (43, 0)
    assert alpha["sprint_points"] == 7
    assert table.loc["d", "starts"] == 0


def test_sprints_score_but_are_not_race_wins(results):
    sprint_winner = results[results.session.eq("Sprint") & results.finish.eq(1)]
    assert not sprint_winner["win"].any()
    assert analytics.driver_table(results).set_index("driver_id").loc["b", "wins"] == 1


def test_progression_carries_absence_and_starts_at_debut(results):
    grid = analytics.standings_progression(results)
    beta = grid[grid.driver_id.eq("b")]
    assert beta["cumulative"].tolist() == [26, 26, 51]
    assert grid[grid.driver_id.eq("c")]["round"].tolist() == [2, 3]
    by_key = grid.set_index(["round", "driver_id"])
    assert by_key.loc[(1, "b"), "gap_to_leader"] == 6
    assert by_key.loc[(3, "a"), "gap_to_leader"] == 1
    assert by_key.loc[(3, "b"), "gap_to_leader"] == 0
    assert by_key.loc[(2, "d"), "rank"] == 4


def test_pit_lane_dns_and_retirement_semantics(results):
    race = results[results.session.eq("Race")].set_index(["round", "driver_id"])
    assert pd.isna(race.loc[(1, "b"), "grid"])  # grid 0 = pit lane
    assert pd.isna(race.loc[(1, "b"), "gain"])
    assert not race.loc[(2, "d"), "started"]
    assert not race.loc[(2, "d"), "retired"]
    assert race.loc[(2, "a"), "retired"]
    assert race.loc[(2, "a"), "cause"] == "Falha técnica"
    assert not race.loc[(3, "a"), "retired"]  # +1 Lap é conclusão
    assert race.loc[(3, "a"), "laps_down"] == 1


def test_gap_uses_fastf1_time_semantics(results):
    race = results[results.session.eq("Race")].set_index(["round", "driver_id"])
    assert race.loc[(1, "a"), "gap_s"] == 0  # vencedor: Time é o total
    assert race.loc[(1, "b"), "gap_s"] == pytest.approx(3.2)
    assert pd.isna(race.loc[(3, "a"), "gap_s"])  # retardatário não tem margem


@pytest.mark.parametrize(
    "classification,expected,started",
    [
        ("R", "DNF", True),
        ("D", "DSQ", True),
        ("E", "DSQ", True),
        ("F", "DNQ", False),
        ("W", "DNS", False),
        ("N", "NC", True),
        ("", "NC", True),
    ],
)
def test_explicit_result_categories(raw, classification, expected, started):
    row = raw.head(1).assign(ClassifiedPosition=classification, Status="")
    result = prepare_results(row).iloc[0]
    assert result["result"] == expected
    assert bool(result["started"]) == started
    assert not result["win"]


def test_duplicates_and_invalid_rows_are_counted_and_excluded(raw):
    bad = raw.head(1).assign(DriverId=None)
    frame = prepare_results(pd.concat([raw, raw.head(1), bad], ignore_index=True))
    assert frame.attrs == {"duplicates": 1, "invalid": 1}
    assert len(frame) == len(raw)


def test_equal_points_share_rank(raw):
    frame = prepare_results(raw.head(2).assign(Points=25))
    assert analytics.driver_table(frame)["rank"].tolist() == [1, 1]
    assert (
        "dividem a liderança" in analytics.season_findings(frame, in_progress=False)[0]
    )


@pytest.mark.parametrize(
    "status,cause",
    [
        ("Engine", "Falha técnica"),
        ("Drivetrain", "Falha técnica"),
        ("Safety belt", "Falha técnica"),
        ("Collision damage", "Incidente de pista"),
        ("Tyre", "Incidente de pista"),
        ("Retired", "Sem motivo detalhado"),
        ("Driver unwell", "Sem motivo detalhado"),
        ("", "Sem motivo detalhado"),
    ],
)
def test_retirement_causes(status, cause):
    assert analytics.classify_retirement(status) == cause


def test_team_color_keeps_hue_but_reaches_contrast():
    assert analytics.team_color("FF8000") == "#FF8000"
    assert analytics.team_color("0600EF") != "#0600EF"
    assert analytics.team_color("sem cor") == analytics.FALLBACK_COLOR


def test_season_findings(results):
    findings = analytics.season_findings(results, in_progress=False)
    assert findings[0] == "Beta terminou com 51 pontos, 1 à frente de Alpha."
    assert findings[1] == "3 vencedores diferentes em 3 corridas; Beta venceu 1 vez."
    assert findings[2] == "Blue somou 55% dos pontos distribuídos."
    assert len(findings) == 3  # sem sprints o empate continua: nada a relatar


def test_sprint_flip_is_reported_only_when_leader_changes(raw):
    changed = raw.copy()
    changed.loc[(changed.RoundNumber == 3) & (changed.DriverId == "a"), "Points"] = 20
    changed.loc[(changed.Mode == "Sprint") & (changed.DriverId == "b"), "Points"] = 10
    findings = analytics.season_findings(prepare_results(changed), in_progress=True)
    assert findings[0].startswith("Beta lidera com 53 pontos")
    assert findings[-1] == (
        "Sem as sprints, Alpha estaria na frente (45 contra 43 de Beta)."
    )


def test_trend_over_last_three_rounds(raw):
    extra = raw[raw.RoundNumber.eq(3)].assign(
        RoundNumber=4, Date=raw["Date"].max().replace(day=30)
    )
    findings = analytics.season_findings(
        prepare_results(pd.concat([raw, extra])), in_progress=True
    )
    # Etapa 1: Alpha 32 × Beta 26 (Beta atrás 6); agora Beta 76 × Alpha 68.
    assert (
        findings[1]
        == "A diferença entre os dois cresceu 14 pontos nas últimas 3 rodadas."
    )


def test_race_calendar_and_findings(results):
    calendar = analytics.race_calendar(results).set_index("round")
    assert calendar.loc[1, "margin"] == pytest.approx(3.2)
    assert pd.isna(calendar.loc[3, "margin"])  # 2º a uma volta
    assert pd.isna(calendar.loc[2, "margin"])
    assert calendar.loc[2, "retirements"] == 1
    assert calendar.loc[1, "has_sprint"] and not calendar.loc[2, "has_sprint"]
    assert calendar.loc[3, "pole"] == "Alpha"
    findings = analytics.race_findings(calendar.reset_index())
    assert findings == [
        "Vitória mais apertada: Alpha, 3,2 s à frente no GP 1.",
        "0 de 3 vitórias saíram da pole.",
    ]


def test_race_detail_labels(results):
    second = analytics.race_detail(results, 2)
    assert second["position"].tolist() == ["1", "DNF", "DNS"]
    assert second["outcome"].tolist() == ["1:31:40", "Abandono · Engine", "Não largou"]
    third = analytics.race_detail(results, 3)
    assert third["outcome"].tolist() == ["1:28:20", "+1 volta"]
    assert analytics.sprint_winner(results, 1) == "Beta"
    assert analytics.sprint_winner(results, 2) is None


def test_forecast_view_compares_model_with_table(results):
    predictions = pd.DataFrame(
        {"driver_id": ["a", "b", "c"], "probability": [0.2, 0.3, 0.5]}
    )
    standings = analytics.standings_at(results, "2024-03-10")
    assert standings.set_index("driver_id")["points"].to_dict() == {
        "a": 32,
        "b": 26,
        "c": 25,
        "d": 0,
    }
    view = analytics.forecast_view(predictions, standings)
    assert view["driver_id"].tolist() == ["c", "b", "a"]
    assert view.set_index("driver_id")["model_rank"].to_dict() == {
        "c": 1,
        "b": 2,
        "a": 3,
    }
    assert analytics.forecast_findings(view) == [
        "Gamma é o favorito do modelo, com 50,0% de chance.",
        "O líder em pontos na data é Alpha (32 pts); o modelo o coloca em 3º.",
        "Maior divergência: Alpha é 1º em pontos e 3º no modelo.",
    ]


def test_era_summary_counts_and_rates(results):
    summary = analytics.era_summary(results, current_year=2030).iloc[0]
    assert summary["races"] == 3
    assert summary["winners"] == 3
    assert (summary["pole_wins"], summary["gridded_wins"]) == (0, 3)
    assert (summary["starts"], summary["retirements"], summary["technical"]) == (
        6,
        1,
        1,
    )
    assert summary["retirement_rate"] == pytest.approx(1 / 6)
    assert summary["leader"] == "Beta"
    assert summary["leader_win_share"] == pytest.approx(1 / 3)
    assert not summary["partial"] and not summary["in_progress"]


def test_partial_and_in_progress_seasons_are_flagged(raw):
    short = raw[raw.RoundNumber.eq(1)].assign(
        Year=2025, Date=lambda data: data["Date"] + pd.DateOffset(years=1)
    )
    summary = analytics.era_summary(
        prepare_results(pd.concat([raw, short])), current_year=2025
    ).set_index("season")
    assert not summary.loc[2024, "partial"]
    assert summary.loc[2025, "partial"]
    assert summary.loc[2025, "in_progress"]


def test_retirements_by_decade_share_the_start_denominator(results):
    decades = analytics.retirement_by_decade(results).set_index("cause")
    assert set(decades.index) == set(analytics.CAUSES)
    assert decades.loc["Falha técnica", "rate"] == pytest.approx(1 / 6)
    assert decades["starts"].eq(6).all()


def test_era_findings_flag_undetailed_retirements(raw):
    older = raw.assign(Year=1990, Date=raw["Date"] - pd.DateOffset(years=34))
    recent = raw.assign(Status=raw["Status"].replace("Engine", "Retired"))
    summary = analytics.era_summary(
        prepare_results(pd.concat([older, recent])), current_year=2030
    )
    findings = analytics.era_findings(summary)
    assert (
        findings[0] == "Vitórias saindo da pole: 0% nos anos 1990 → 0% nos anos 2020."
    )
    assert findings[2] == (
        "Falhas técnicas: 17% → 0% das largadas, mas a fonte não detalha o motivo "
        "de 100% dos abandonos dos anos 2020."
    )
    assert findings[-1].startswith("Maior domínio: Beta venceu 1 de 3 corridas")
