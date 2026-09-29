"""Transformações pandas puras sobre as tabelas do lake (sem Streamlit, sem I/O)."""

from __future__ import annotations

import re
from datetime import UTC, datetime

import pandas as pd

FALLBACK_COLOR = "#8a8a84"
_SURFACE_LUMINANCE = 0.0103  # #1a1a19
RESULT_STATUS = {"FINISHED", "DNF", "DNS", "DSQ"}
STATUS_LABELS = {
    "FINISHED": "Concluiu",
    "DNF": "Abandono",
    "DNS": "Não largou",
    "DSQ": "Desclassificado",
}


def current_year() -> int:
    return datetime.now(UTC).year


def line_dashes(driver_teams: list[tuple[str, str]]) -> dict[str, str]:
    """Companheiros dividem a cor da equipe; o segundo na ordem recebe traço pontilhado."""
    seen: set[str] = set()
    dashes = {}
    for driver_id, team in driver_teams:
        dashes[driver_id] = "dot" if team in seen else "solid"
        seen.add(team)
    return dashes


def short_name(full_name: str) -> str:
    """ "Kimi Antonelli" → "K. Antonelli" para caber em KPIs."""
    parts = str(full_name).split()
    return full_name if len(parts) < 2 else f"{parts[0][0]}. {' '.join(parts[1:])}"


def _luminance(rgb: tuple[float, ...]) -> float:
    linear = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in rgb]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def team_color(value) -> str:
    """Cor da equipe clareada até 3:1 de contraste com a superfície escura."""
    color = str(value or "").strip().lstrip("#")
    if not re.fullmatch(r"[0-9a-fA-F]{6}", color):
        return FALLBACK_COLOR
    rgb = tuple(int(color[i : i + 2], 16) / 255 for i in (0, 2, 4))
    while (_luminance(rgb) + 0.05) / (_SURFACE_LUMINANCE + 0.05) < 3:
        rgb = tuple(c + (1 - c) * 0.15 for c in rgb)
    return "#" + "".join(f"{round(c * 255):02X}" for c in rgb)


# ----------------------------------------------------------------- temporada


def final_round(standings: pd.DataFrame) -> pd.DataFrame:
    """Linha de cada piloto na última rodada disputada (o mart repete todos os pilotos)."""
    last = standings["round_number"].max()
    return standings[standings["round_number"].eq(last)]


def race_stats(results: pd.DataFrame) -> pd.DataFrame:
    """Vitórias, pódios, poles e abandonos por piloto (corrida principal)."""
    finish = results["official_finish"]
    return (
        results.assign(
            win=finish.eq(1),
            podium=finish.le(3),
            pole=results["official_grid"].eq(1),
            dnf=results["result_status"].eq("DNF"),
            start=results["started"].astype(bool),
        )
        .groupby("driver_id", as_index=False)[["win", "podium", "pole", "dnf", "start"]]
        .sum()
    )


def standings_table(
    standings: pd.DataFrame, results: pd.DataFrame, form_rounds: int = 5
) -> pd.DataFrame:
    """Classificação na última rodada com estatísticas e forma recente."""
    columns = [
        "rank",
        "driver_id",
        "driver",
        "code",
        "team",
        "color",
        "points",
        "wins",
        "podiums",
        "poles",
        "dnfs",
        "form",
    ]
    if standings.empty:
        return pd.DataFrame(columns=columns)
    table = final_round(standings).rename(
        columns={
            "championship_rank": "rank",
            "driver_name": "driver",
            "abbreviation": "code",
            "team_name": "team",
            "cumulative_points": "points",
        }
    )
    stats = race_stats(results).rename(
        columns={"win": "wins", "podium": "podiums", "pole": "poles", "dnf": "dnfs"}
    )
    table = table.merge(
        stats[["driver_id", "wins", "podiums", "poles", "dnfs"]],
        on="driver_id",
        how="left",
    )
    table[["wins", "podiums", "poles", "dnfs"]] = (
        table[["wins", "podiums", "poles", "dnfs"]].fillna(0).astype(int)
    )
    recent = sorted(standings["round_number"].unique())[-form_rounds:]
    form = (
        standings[standings["round_number"].isin(recent)]
        .sort_values("round_number")
        .groupby("driver_id")["round_points"]
        .agg(list)
    )
    table["form"] = table["driver_id"].map(form)
    table["color"] = table["team_color"].map(team_color)
    return table.sort_values(["rank", "driver"])[columns].reset_index(drop=True)


def season_summary(standings: pd.DataFrame, results: pd.DataFrame) -> dict:
    table = standings_table(standings, results)
    if table.empty:
        return {}
    leader = table.iloc[0]
    second = table.iloc[1] if len(table) > 1 else None
    winners = results.loc[results["official_finish"].eq(1), "driver_id"].nunique()
    return {
        "leader": leader["driver"],
        "leader_team": leader["team"],
        "leader_points": leader["points"],
        "tied": int(table["rank"].eq(1).sum()) > 1,
        "gap": leader["points"] - second["points"] if second is not None else None,
        "second": second["driver"] if second is not None else None,
        "winners": int(winners),
        "races": int(results["round_number"].nunique()),
        "rounds": int(standings["round_number"].nunique()),
        "last_event": standings.sort_values("round_number").iloc[-1]["event_name"],
        "last_date": pd.Timestamp(standings["event_date"].max()),
    }


def title_fight(standings: pd.DataFrame, top: int = 8) -> pd.DataFrame:
    """Pontos acumulados e posição por rodada dos `top` primeiros da classificação."""
    order = final_round(standings).sort_values(["championship_rank", "driver_name"])
    leaders = order.head(top)["driver_id"].tolist()
    frame = standings[standings["driver_id"].isin(leaders)].copy()
    frame["order"] = frame["driver_id"].map({d: i for i, d in enumerate(leaders)})
    frame["color"] = frame["team_color"].map(team_color)
    return frame.sort_values(["order", "round_number"]).reset_index(drop=True)


def constructors(results_bronze: pd.DataFrame) -> pd.DataFrame:
    """Pontos por equipe atribuídos à equipe de cada sessão (Race + Sprint)."""
    sessions = results_bronze[results_bronze["Mode"].isin(["Race", "Sprint"])]
    if sessions.empty:
        return pd.DataFrame(columns=["team", "points", "color"])
    colors = sessions.sort_values("Date").drop_duplicates("TeamName", keep="last")
    table = sessions.groupby("TeamName", as_index=False)["Points"].sum()
    table = table.merge(colors[["TeamName", "TeamColor"]], on="TeamName")
    table = table.rename(columns={"TeamName": "team", "Points": "points"})
    table["color"] = table["TeamColor"].map(team_color)
    return table.sort_values("points", ascending=False)[["team", "points", "color"]]


def _position_label(row) -> str:
    if pd.notna(row["official_finish"]):
        return str(int(row["official_finish"]))
    return row["result_status"]


def race_result(results: pd.DataFrame, round_number: int) -> pd.DataFrame:
    race = results[results["round_number"].eq(round_number)].sort_values(
        ["result_order", "driver_name"]
    )
    if race.empty:
        return race
    # Inteiros anuláveis viram float: NaN aparece vazio na tabela, não "None".
    grid = race["official_grid"].astype(float)
    race = race.assign(
        position=race.apply(_position_label, axis=1),
        official_grid=grid,
        gained=grid - race["official_finish"].astype(float),
        status=race["result_status"].map(STATUS_LABELS).fillna(race["result_status"]),
        color=race["team_color"].map(team_color),
    )
    return race.reset_index(drop=True)


def race_calendar(results: pd.DataFrame) -> pd.DataFrame:
    events = results.groupby("round_number", as_index=False).agg(
        event=("event_name", "first"), date=("event_date", "max")
    )
    winners = results[results["official_finish"].eq(1)][
        ["round_number", "driver_name", "team_name"]
    ]
    return events.merge(winners, on="round_number", how="left").sort_values(
        "round_number"
    )


# ------------------------------------------------------------------- pilotos


def driver_season(
    standings: pd.DataFrame, results: pd.DataFrame, driver_id: str
) -> dict:
    mine = results[results["driver_id"].eq(driver_id)]
    table = standings_table(standings, results)
    row = table[table["driver_id"].eq(driver_id)]
    if row.empty:
        return {}
    row = row.iloc[0]
    finished = mine[mine["result_status"].eq("FINISHED")]
    return {
        "rank": int(row["rank"]),
        "points": row["points"],
        "wins": int(row["wins"]),
        "podiums": int(row["podiums"]),
        "poles": int(row["poles"]),
        "dnfs": int(row["dnfs"]),
        "starts": int(mine["started"].sum()),
        "avg_finish": finished["official_finish"].mean(),
        "avg_grid": mine["official_grid"].mean(),
        "team": row["team"],
        "color": row["color"],
        "driver": row["driver"],
        "code": row["code"],
    }


def race_by_race(results: pd.DataFrame, driver_id: str) -> pd.DataFrame:
    mine = results[results["driver_id"].eq(driver_id)].sort_values("round_number")
    return mine.assign(position=mine.apply(_position_label, axis=1)).reset_index(
        drop=True
    )


def teammate_duels(results: pd.DataFrame, driver_id: str) -> pd.DataFrame:
    """Confronto com cada companheiro nas corridas em que dividiram a equipe."""
    mine = results[results["driver_id"].eq(driver_id)][
        ["round_number", "team_id", "result_order", "official_grid", "points"]
    ]
    others = results[results["driver_id"].ne(driver_id)][
        [
            "round_number",
            "team_id",
            "driver_id",
            "driver_name",
            "result_order",
            "official_grid",
            "points",
        ]
    ]
    pairs = mine.merge(others, on=["round_number", "team_id"], suffixes=("", "_mate"))
    if pairs.empty:
        return pd.DataFrame(
            columns=[
                "teammate",
                "races",
                "race_ahead",
                "grid_ahead",
                "grid_races",
                "points",
                "points_mate",
            ]
        )
    pairs["race_ahead"] = pairs["result_order"] < pairs["result_order_mate"]
    both_grid = pairs["official_grid"].notna() & pairs["official_grid_mate"].notna()
    pairs["grid_ahead"] = both_grid & (
        pairs["official_grid"] < pairs["official_grid_mate"]
    )
    pairs["grid_race"] = both_grid
    return (
        pairs.groupby(["driver_id", "driver_name"], as_index=False)
        .agg(
            races=("round_number", "nunique"),
            race_ahead=("race_ahead", "sum"),
            grid_ahead=("grid_ahead", "sum"),
            grid_races=("grid_race", "sum"),
            points=("points", "sum"),
            points_mate=("points_mate", "sum"),
        )
        .rename(columns={"driver_name": "teammate"})
        .sort_values("races", ascending=False)
        .drop(columns="driver_id")
        .reset_index(drop=True)
    )


def career(standings: pd.DataFrame, results: pd.DataFrame) -> pd.DataFrame:
    """Uma linha por temporada de um piloto (entrada já filtrada pelo piloto)."""
    if standings.empty:
        return pd.DataFrame(
            columns=[
                "season",
                "team",
                "rank",
                "points",
                "wins",
                "podiums",
                "poles",
                "starts",
            ]
        )
    last = standings.sort_values("round_number").drop_duplicates("season", keep="last")
    seasons = last.rename(
        columns={
            "team_name": "team",
            "championship_rank": "rank",
            "cumulative_points": "points",
        }
    )[["season", "team", "rank", "points"]]
    stats = (
        results.assign(
            wins=results["official_finish"].eq(1),
            podiums=results["official_finish"].le(3),
            poles=results["official_grid"].eq(1),
            starts=results["started"].astype(bool),
        )
        .groupby("season", as_index=False)[["wins", "podiums", "poles", "starts"]]
        .sum()
    )
    table = seasons.merge(stats, on="season", how="left").fillna(
        {"wins": 0, "podiums": 0, "poles": 0, "starts": 0}
    )
    table[["wins", "podiums", "poles", "starts"]] = table[
        ["wins", "podiums", "poles", "starts"]
    ].astype(int)
    return table.sort_values("season").reset_index(drop=True)


WINDOWS = (5, 10, 20, 40, 50)
WINDOW_METRICS = {
    "qty_sessions": "Sessões",
    "qty_1place": "Vitórias",
    "qty_place": "Pódios",
    "qty_sessions_with_points": "Com pontos",
    "total_points": "Pontos",
    "avg_gridposition": "Grid médio",
    "avg_position": "Chegada média",
}


def window_form(abt_row: pd.Series) -> pd.DataFrame:
    """Linha da ABT → tabela janela × métrica (sessões Race + Sprint)."""
    rows = []
    for window in WINDOWS:
        row = {"window": f"Últimas {window}"}
        for metric, label in WINDOW_METRICS.items():
            row[label] = abt_row.get(f"{metric}_{window}")
        rows.append(row)
    return pd.DataFrame(rows)


# ------------------------------------------------------------------ previsão


def candidates(abt: pd.DataFrame, debuts: pd.Series) -> pd.DataFrame:
    """Linhas da ABT de pilotos que já estrearam na temporada até cada `dt_ref`."""
    frame = abt.copy()
    frame["dt_ref"] = pd.to_datetime(frame["dt_ref"])
    frame["debut"] = pd.to_datetime(frame["DriverId"].map(debuts))
    frame = frame[frame["debut"].notna() & (frame["dt_ref"] >= frame["debut"])].copy()
    snapshot = frame["dt_ref"].dt.strftime("%Y-%m-%d")
    frame["id"] = snapshot + ":" + frame["DriverId"]
    frame["prediction_group"] = snapshot
    return frame.drop(columns="debut").sort_values(["dt_ref", "DriverId"])


def forecast_frame(predictions: dict, candidates_frame: pd.DataFrame) -> pd.DataFrame:
    values = pd.DataFrame.from_dict(predictions, orient="index")
    values.index.name = "id"
    merged = candidates_frame[["id", "dt_ref", "DriverId"]].merge(
        values.reset_index(), on="id", how="inner"
    )
    return merged.rename(columns={"DriverId": "driver_id"})


_BASE_LABELS = {
    "qty_seasons": "Temporadas",
    "qty_sessions": "Sessões",
    "qty_sessions_finished": "Sessões concluídas",
    "qty_1place": "Vitórias",
    "qty_2place": "Segundos lugares",
    "qty_3place": "Terceiros lugares",
    "qty_place": "Pódios",
    "total_points": "Pontos",
    "avg_gridposition": "Grid médio",
    "avg_position": "Chegada média",
    "qty_gridposition_1": "Poles",
    "qty_poli_win": "Vitórias saindo da pole",
    "qty_sessions_with_points": "Sessões com pontos",
    "qty_sessions_with_overtake": "Sessões ganhando posições",
    "avg_overtake": "Posições ganhas (média)",
    "qty_pos5": "Chegadas no top 5",
    "qty_gridpos5": "Largadas no top 5",
}
_FEATURE = re.compile(r"^(?P<base>[a-z_0-9]+?)(?:_(?P<mode>[rsS]))?_(?P<window>\d+)$")


def feature_label(name: str) -> str:
    """`qty_1place_r_20` → "Vitórias em corridas · últimas 20 sessões"."""
    match = _FEATURE.match(name)
    if not match or match["base"] not in _BASE_LABELS:
        return name
    label = _BASE_LABELS[match["base"]]
    mode = (match["mode"] or "").lower()
    if mode == "r":
        label += " em corridas"
    elif mode == "s":
        label += " em sprints"
    return f"{label} · últimas {match['window']} sessões"


# ---------------------------------------------------------------------- dados

CATALOG = {
    "results": "Bronze · um piloto por sessão (Race/Sprint) · resultados FastF1",
    "mart_standings": "Mart · piloto × rodada · pontos acumulados e posição",
    "mart_driver_round": "Mart · piloto × corrida principal · grid, chegada, status",
    "champions": "Líder em pontos de cada temporada",
    "driver_statistic_5": "Estatísticas nas últimas 5 sessões, por data",
    "driver_statistic_10": "Estatísticas nas últimas 10 sessões, por data",
    "driver_statistic_20": "Estatísticas nas últimas 20 sessões, por data",
    "driver_statistic_40": "Estatísticas nas últimas 40 sessões, por data",
    "driver_statistic_50": "Estatísticas nas últimas 50 sessões, por data",
    "driver_statistic_life": "Janela longa legada (fora do DAG)",
    "driver_all_statistic": "Todas as janelas lado a lado, por data e piloto",
    "tb_abt": "ABT do modelo · features + rótulo flChampion",
}
LEGACY_TABLES = {"driver_statistic_life"}


def _check(name: str, table: str, failures: int, detail: str) -> dict:
    return {
        "check": name,
        "table": table,
        "status": "ok" if failures == 0 else "falha",
        "failures": int(failures),
        "detail": detail,
    }


def quality_checks(
    standings: pd.DataFrame,
    driver_round: pd.DataFrame,
    abt_keys: pd.DataFrame,
    champions: pd.DataFrame,
) -> pd.DataFrame:
    """Regras do contrato analítico (docs/analytics-data-contract.md)."""
    key = ["season", "round_number", "driver_id"]
    checks = [
        _check(
            "Chave única",
            "mart_standings",
            standings.duplicated(key).sum(),
            "(season, round_number, driver_id)",
        ),
        _check(
            "Chave sem nulos",
            "mart_standings",
            standings[key].isna().any(axis=1).sum(),
            "campos da chave preenchidos",
        ),
        _check(
            "Pontos não negativos",
            "mart_standings",
            (standings["round_points"] < 0).sum(),
            "round_points ≥ 0",
        ),
        _check(
            "Chave única",
            "mart_driver_round",
            driver_round.duplicated(key).sum(),
            "(season, round_number, driver_id)",
        ),
        _check(
            "Status no domínio",
            "mart_driver_round",
            (~driver_round["result_status"].isin(RESULT_STATUS)).sum(),
            ", ".join(sorted(RESULT_STATUS)),
        ),
        _check(
            "DNS/DNQ não largam",
            "mart_driver_round",
            (driver_round["result_status"].eq("DNS") & driver_round["started"]).sum(),
            "started = falso para DNS",
        ),
        _check(
            "Chave única",
            "tb_abt",
            abt_keys.duplicated(["dt_ref", "DriverId"]).sum(),
            "(dt_ref, DriverId)",
        ),
        _check(
            "Um líder por temporada",
            "champions",
            champions.duplicated("Year").sum(),
            "uma linha por Year",
        ),
    ]
    return pd.DataFrame(checks)


def coverage(results_bronze: pd.DataFrame, *, current: int) -> pd.DataFrame:
    """Corridas principais por temporada; poucas corridas indicam ingestão parcial."""
    race = results_bronze[results_bronze["Mode"].eq("Race")]
    table = race.groupby("Year", as_index=False).agg(races=("RoundNumber", "nunique"))
    table = table.rename(columns={"Year": "season"})
    median = table["races"].median()
    table["status"] = "completa"
    table.loc[table["races"] < 0.75 * median, "status"] = "parcial"
    table.loc[table["season"].eq(current), "status"] = "em andamento"
    return table
