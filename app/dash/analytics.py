"""Análises puras de resultados de F1: nenhuma função muta a entrada nem acessa I/O."""

from __future__ import annotations

import re
from datetime import UTC, datetime

import pandas as pd

import formatting as fmt

KEY = ["season", "round", "session", "driver_id"]
NAMES = {
    "Year": "season",
    "RoundNumber": "round",
    "Mode": "session",
    "Date": "date",
    "EventName": "event",
    "DriverId": "driver_id",
    "FullName": "driver",
    "Abbreviation": "code",
    "TeamName": "team",
    "TeamColor": "color",
    "Points": "points",
    "Position": "order",
    "ClassifiedPosition": "classification",
    "GridPosition": "grid",
    "Status": "status",
    "Laps": "laps",
    "Time": "time",
    "Country": "country",
    "Location": "location",
}
FALLBACK_COLOR = "#898781"
COMPLETION_STATUS = re.compile(r"^(?:finished|lapped|\+\d+ laps?)$", re.IGNORECASE)
LAPS_DOWN = re.compile(r"^\+(\d+) laps?$", re.IGNORECASE)
NO_START_STATUS = {"did not start", "did not qualify", "did not prequalify"}
ADMIN_STATUS = {"disqualified", "excluded", "underweight"}

# Ordem importa: incidente é testado antes de falha técnica ("Collision damage").
INCIDENT = re.compile(r"accident|collision|spun|damage|debris|puncture|tyre")
TECHNICAL = re.compile(
    r"engine|gearbox|electric|suspension|brake|transmission|hydraulic|turbo|clutch|"
    r"throttle|fuel|wheel|overheat|power|oil|halfshaft|handling|steering|mechanical|"
    r"exhaust|drive(?:shaft|train)|ignition|differential|water|alternator|radiator|"
    r"chassis|battery|injection|heat shield|wing|vibration|distributor|\bers\b|"
    r"pneumatic|technical|spark|fire|undertray|cooling|cv joint|crankshaft|seat|"
    r"launch control|refuel|track rod|safety belt|misfire|stalled"
)
CAUSES = ["Falha técnica", "Incidente de pista", "Sem motivo detalhado"]


SURFACE_LUMINANCE = 0.0103  # #1a1a19, superfície dos gráficos e tabelas


def _luminance(rgb: tuple[float, float, float]) -> float:
    linear = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in rgb]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def current_year() -> int:
    return datetime.now(UTC).year


def team_color(value) -> str:
    """Cor oficial da equipe, clareada até 3:1 de contraste com o fundo escuro."""
    color = str(value).strip().lstrip("#")
    if not re.fullmatch(r"[0-9a-fA-F]{6}", color):
        return FALLBACK_COLOR
    rgb = tuple(int(color[i : i + 2], 16) / 255 for i in (0, 2, 4))
    while (_luminance(rgb) + 0.05) / (SURFACE_LUMINANCE + 0.05) < 3:
        rgb = tuple(c + (1 - c) * 0.15 for c in rgb)
    return "#" + "".join(f"{round(c * 255):02X}" for c in rgb)


def classify_retirement(status: str) -> str:
    text = str(status or "").strip().casefold()
    if INCIDENT.search(text):
        return "Incidente de pista"
    if TECHNICAL.search(text):
        return "Falha técnica"
    return "Sem motivo detalhado"


def prepare_results(raw: pd.DataFrame) -> pd.DataFrame:
    """Normaliza Race/Sprint do Bronze em uma linha por sessão e piloto."""
    frame = raw.rename(columns=NAMES).copy()
    required = {
        "season",
        "round",
        "session",
        "driver_id",
        "date",
        "points",
        "classification",
    }
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError("Colunas obrigatórias ausentes: " + ", ".join(sorted(missing)))
    frame = frame[frame["session"].isin(["Race", "Sprint"])].copy()
    for col in ["season", "round", "points", "grid", "order", "laps", "time"]:
        frame[col] = pd.to_numeric(
            frame.get(col, pd.Series(index=frame.index, dtype=float)), errors="coerce"
        )
    frame["date"] = pd.to_datetime(
        frame["date"], errors="coerce", utc=True
    ).dt.tz_localize(None)
    invalid = (
        frame[["season", "round", "driver_id", "date", "points"]].isna().any(axis=1)
    )
    invalid |= frame["driver_id"].astype(str).str.strip().eq("")
    invalid |= (frame["round"] <= 0) | (frame["points"] < 0)
    invalid |= (frame["season"] % 1 != 0) | (frame["round"] % 1 != 0)
    invalid_count = int(invalid.sum())
    frame = frame.loc[~invalid].copy()
    duplicate_count = int(frame.duplicated(KEY).sum())
    frame = frame.sort_values("date").drop_duplicates(KEY, keep="last")
    frame[["season", "round"]] = frame[["season", "round"]].astype(int)
    for col, default in [
        ("driver", ""),
        ("team", "Sem equipe"),
        ("code", ""),
        ("event", "Grande Prêmio"),
        ("country", ""),
        ("location", ""),
        ("status", ""),
        ("color", ""),
    ]:
        if col not in frame:
            frame[col] = default
        frame[col] = frame[col].fillna(default).astype(str).str.strip()
    frame["driver"] = frame["driver"].where(frame["driver"].ne(""), frame["driver_id"])
    frame["code"] = frame["code"].where(
        frame["code"].ne(""), frame["driver"].str.split().str[-1].str[:3].str.upper()
    )
    frame["color"] = frame["color"].map(team_color)

    classification = frame["classification"].fillna("").astype(str).str.strip()
    numeric = pd.to_numeric(classification, errors="coerce")
    frame["finish"] = numeric.where((numeric > 0) & (numeric % 1 == 0))
    frame["result"] = (
        classification.str.upper()
        .map({"R": "DNF", "D": "DSQ", "E": "DSQ", "W": "DNS", "F": "DNQ", "N": "NC"})
        .fillna("NC")
    )
    frame.loc[frame["finish"].notna(), "result"] = "FINISHED"
    status = frame["status"].str.casefold()
    frame["started"] = ~frame["result"].isin(["DNS", "DNQ"]) & ~status.isin(
        NO_START_STATUS
    )
    frame["grid"] = frame["grid"].where(frame["grid"] > 0)
    frame["gain"] = frame["grid"] - frame["finish"]
    frame["win"] = frame["finish"].eq(1) & frame["session"].eq("Race")
    frame["podium"] = frame["finish"].between(1, 3) & frame["session"].eq("Race")

    completed = frame["status"].str.match(COMPLETION_STATUS) | (
        frame["status"].eq("") & frame["finish"].notna()
    )
    administrative = frame["result"].eq("DSQ") | status.isin(ADMIN_STATUS)
    frame["retired"] = frame["started"] & ~completed & ~administrative
    frame["cause"] = frame["status"].map(classify_retirement).where(frame["retired"])

    # FastF1: Time do vencedor é o tempo total; dos demais, a diferença para ele.
    lead_lap = frame["status"].str.casefold().eq("finished")
    frame["gap_s"] = frame["time"].where(
        lead_lap & frame["finish"].gt(1) & frame["time"].gt(0)
    )
    frame.loc[frame["finish"].eq(1), "gap_s"] = 0.0
    frame["laps_down"] = pd.to_numeric(
        frame["status"].str.extract(LAPS_DOWN, expand=False), errors="coerce"
    )
    frame.attrs.update(duplicates=duplicate_count, invalid=invalid_count)
    return frame.sort_values(["season", "round", "date", "order", "driver_id"])


# ---------------------------------------------------------------- temporada


def driver_table(frame: pd.DataFrame) -> pd.DataFrame:
    """Classificação por pontos; a equipe exibida é a última do piloto no recorte."""
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
        "starts",
        "podium_points",
        "other_race_points",
        "sprint_points",
        "recent_points",
    ]
    if frame.empty:
        return pd.DataFrame(columns=columns)
    metadata = frame.sort_values("date").drop_duplicates("driver_id", keep="last")
    race = frame["session"].eq("Race")
    rounds = sorted(frame["round"].unique())
    recent = frame["round"].isin(rounds[-3:])
    values = frame.assign(
        podium_points=frame["points"].where(race & frame["podium"], 0),
        race_points=frame["points"].where(race, 0),
        sprint_points=frame["points"].where(~race, 0),
        recent_points=frame["points"].where(recent, 0),
        race_start=race & frame["started"],
    )
    table = values.groupby("driver_id", as_index=False).agg(
        points=("points", "sum"),
        wins=("win", "sum"),
        podiums=("podium", "sum"),
        starts=("race_start", "sum"),
        podium_points=("podium_points", "sum"),
        race_points=("race_points", "sum"),
        sprint_points=("sprint_points", "sum"),
        recent_points=("recent_points", "sum"),
    )
    table["other_race_points"] = table["race_points"] - table["podium_points"]
    table = table.merge(
        metadata[["driver_id", "driver", "code", "team", "color"]], on="driver_id"
    )
    table["rank"] = table["points"].rank(method="min", ascending=False).astype(int)
    table[["wins", "podiums", "starts"]] = table[["wins", "podiums", "starts"]].astype(
        int
    )
    return table.sort_values(
        ["points", "wins", "driver"], ascending=[False, False, True]
    ).reset_index(drop=True)[columns]


def standings_progression(frame: pd.DataFrame) -> pd.DataFrame:
    """Grade rodada × piloto desde a estreia; ausência numa etapa preserva os pontos."""
    columns = [
        "season",
        "round",
        "driver_id",
        "points",
        "cumulative",
        "rank",
        "gap_to_leader",
    ]
    if frame.empty:
        return pd.DataFrame(columns=columns)
    points = frame.groupby(["season", "round", "driver_id"])["points"].sum()
    rounds = frame[["season", "round"]].drop_duplicates()
    debut = frame.groupby(["season", "driver_id"], as_index=False).agg(
        debut=("round", "min")
    )
    grid = rounds.merge(debut, on="season")
    grid = grid[grid["round"] >= grid["debut"]].sort_values(
        ["season", "driver_id", "round"]
    )
    grid = grid.join(points, on=["season", "round", "driver_id"])
    grid["points"] = grid["points"].fillna(0.0)
    grid["cumulative"] = grid.groupby(["season", "driver_id"])["points"].cumsum()
    by_round = grid.groupby(["season", "round"])["cumulative"]
    grid["rank"] = by_round.rank(method="min", ascending=False).astype(int)
    grid["gap_to_leader"] = by_round.transform("max") - grid["cumulative"]
    return grid[columns].reset_index(drop=True)


def season_findings(frame: pd.DataFrame, *, in_progress: bool) -> list[str]:
    table = driver_table(frame)
    if table.empty:
        return []
    findings = []
    leader = table.iloc[0]
    tied = table[table["rank"].eq(1)]
    if len(tied) > 1:
        findings.append(
            f"{' e '.join(tied['driver'])} dividem a liderança com "
            f"{fmt.points(leader['points'])} pontos."
        )
    elif len(table) > 1:
        second = table.iloc[1]
        gap = leader["points"] - second["points"]
        verb = "lidera com" if in_progress else "terminou com"
        findings.append(
            f"{leader['driver']} {verb} {fmt.points(leader['points'])} pontos, "
            f"{fmt.points(gap)} à frente de {second['driver']}."
        )
        progression = standings_progression(frame)
        rounds = sorted(progression["round"].unique())
        if len(rounds) >= 4:
            before = progression[progression["round"].eq(rounds[-4])].set_index(
                "driver_id"
            )["cumulative"]
            past = before.get(leader["driver_id"], 0) - before.get(
                second["driver_id"], 0
            )
            change = gap - past
            if change:
                direction = "cresceu" if change > 0 else "caiu"
                findings.append(
                    f"A diferença entre os dois {direction} "
                    f"{fmt.points(abs(change))} pontos nas últimas 3 rodadas."
                )
            else:
                findings.append(
                    "A diferença entre os dois não mudou nas últimas 3 rodadas."
                )

    race = frame[frame["session"].eq("Race")]
    races = race["round"].nunique()
    winners = race.loc[race["win"], "driver_id"].nunique()
    if races and winners:
        top = table.sort_values(["wins", "points"], ascending=False).iloc[0]
        if winners == 1:
            findings.append(f"{top['driver']} venceu todas as {races} corridas.")
        else:
            findings.append(
                f"{winners} vencedores diferentes em {fmt.plural(races, 'corrida')}; "
                f"{top['driver']} venceu {fmt.plural(int(top['wins']), 'vez', 'vezes')}."
            )

    total = frame["points"].sum()
    if total > 0:
        teams = frame.groupby("team")["points"].sum().sort_values(ascending=False)
        findings.append(
            f"{teams.index[0]} somou {fmt.percent(teams.iloc[0] / total)} "
            "dos pontos distribuídos."
        )

    if table["sprint_points"].sum() > 0 and len(tied) == 1:
        without = table.assign(
            no_sprint=table["points"] - table["sprint_points"]
        ).sort_values("no_sprint", ascending=False)
        alternative = without.iloc[0]
        if (
            alternative["driver_id"] != leader["driver_id"]
            and alternative["no_sprint"] > without.iloc[1]["no_sprint"]
        ):
            leader_without = without.set_index("driver_id").loc[
                leader["driver_id"], "no_sprint"
            ]
            findings.append(
                f"Sem as sprints, {alternative['driver']} estaria na frente "
                f"({fmt.points(alternative['no_sprint'])} contra "
                f"{fmt.points(leader_without)} de {leader['driver']})."
            )
    return findings


# ------------------------------------------------------------------ corridas


def race_calendar(frame: pd.DataFrame) -> pd.DataFrame:
    """Uma linha por corrida principal: vencedor, pole, margem e abandonos."""
    columns = [
        "round",
        "event",
        "location",
        "country",
        "date",
        "winner",
        "winner_code",
        "team",
        "color",
        "winner_grid",
        "pole",
        "margin",
        "retirements",
        "has_sprint",
    ]
    race = frame[frame["session"].eq("Race")]
    sprint_rounds = set(frame.loc[frame["session"].eq("Sprint"), "round"])
    rows = []
    for number, group in race.groupby("round", sort=True):
        winner = group[group["win"]]
        pole = group[group["grid"].eq(1)]
        second = group[group["finish"].eq(2)]
        first = group.iloc[0]
        rows.append(
            {
                "round": int(number),
                "event": first["event"],
                "location": first["location"],
                "country": first["country"],
                "date": group["date"].max(),
                "winner": winner.iloc[0]["driver"] if len(winner) else None,
                "winner_code": winner.iloc[0]["code"] if len(winner) else None,
                "team": winner.iloc[0]["team"] if len(winner) else None,
                "color": winner.iloc[0]["color"] if len(winner) else FALLBACK_COLOR,
                "winner_grid": winner.iloc[0]["grid"] if len(winner) else None,
                "pole": pole.iloc[0]["driver"] if len(pole) else None,
                # Só há margem quando o 2º terminou na mesma volta com tempo registrado.
                "margin": second.iloc[0]["gap_s"] if len(second) else None,
                "retirements": int(group["retired"].sum()),
                "has_sprint": int(number) in sprint_rounds,
            }
        )
    calendar = pd.DataFrame(rows, columns=columns)
    calendar["margin"] = pd.to_numeric(calendar["margin"], errors="coerce")
    calendar["winner_grid"] = pd.to_numeric(calendar["winner_grid"], errors="coerce")
    return calendar


def race_findings(calendar: pd.DataFrame) -> list[str]:
    if calendar.empty:
        return []
    findings = []
    timed = calendar.dropna(subset=["margin", "winner"])
    if len(timed):
        closest = timed.loc[timed["margin"].idxmin()]
        findings.append(
            f"Vitória mais apertada: {closest['winner']}, "
            f"{fmt.seconds(closest['margin'])} à frente no {closest['event']}."
        )
        if len(timed) > 1:
            widest = timed.loc[timed["margin"].idxmax()]
            findings.append(
                f"Mais folgada: {widest['winner']}, "
                f"{fmt.seconds(widest['margin'])} à frente no {widest['event']}."
            )
    else:
        findings.append("Não há tempos registrados para medir margens de vitória.")
    gridded = calendar.dropna(subset=["winner_grid"])
    if len(gridded):
        from_pole = int(gridded["winner_grid"].eq(1).sum())
        findings.append(
            f"{from_pole} de {fmt.plural(len(gridded), 'vitória')} saíram da pole."
        )
        comeback = gridded.loc[gridded["winner_grid"].idxmax()]
        if comeback["winner_grid"] >= 4:
            findings.append(
                f"Maior recuperação: {comeback['winner']} venceu o "
                f"{comeback['event']} largando em P{int(comeback['winner_grid'])}."
            )
    return findings


def _result_label(row) -> str:
    if row["finish"] == 1:
        return fmt.race_time(row["time"])
    if pd.notna(row["gap_s"]):
        return "+" + fmt.seconds(row["gap_s"])
    if pd.notna(row["laps_down"]):
        laps = int(row["laps_down"])
        return f"+{fmt.plural(laps, 'volta')}"
    if row["retired"]:
        detail = row["status"]
        generic = detail.casefold() in {"", "retired", "dnf", "not classified"}
        return "Abandono" if generic else f"Abandono · {detail}"
    labels = {
        "DNS": "Não largou",
        "DNQ": "Não se classificou",
        "DSQ": "Desclassificado",
    }
    if row["result"] in labels:
        return labels[row["result"]]
    return row["status"] or "—"


def race_detail(frame: pd.DataFrame, round_number: int) -> pd.DataFrame:
    """Resultado de uma corrida principal, na ordem de chegada."""
    race = frame[frame["round"].eq(round_number) & frame["session"].eq("Race")].copy()
    if race.empty:
        return race.assign(position="", outcome="")
    race = race.sort_values(["finish", "order", "driver"], na_position="last")
    race["position"] = race["finish"].map(
        lambda value: str(int(value)) if pd.notna(value) else "—"
    )
    race.loc[race["finish"].isna(), "position"] = race["result"].where(
        race["result"].ne("FINISHED"), "—"
    )
    race["outcome"] = race.apply(_result_label, axis=1)
    return race.reset_index(drop=True)


def sprint_winner(frame: pd.DataFrame, round_number: int) -> str | None:
    sprint = frame[
        frame["round"].eq(round_number)
        & frame["session"].eq("Sprint")
        & frame["finish"].eq(1)
    ]
    return None if sprint.empty else sprint.iloc[0]["driver"]


# ------------------------------------------------------------------ previsão


def standings_at(frame: pd.DataFrame, snapshot: str) -> pd.DataFrame:
    """Classificação apenas com sessões ocorridas até a data do snapshot."""
    return driver_table(frame[frame["date"].dt.normalize() <= pd.Timestamp(snapshot)])


def forecast_view(predictions: pd.DataFrame, standings: pd.DataFrame) -> pd.DataFrame:
    merged = predictions[["driver_id", "probability"]].merge(
        standings[["driver_id", "driver", "code", "team", "color", "points", "rank"]],
        on="driver_id",
        how="left",
    )
    merged["points"] = merged["points"].fillna(0)
    merged["rank"] = (
        merged["points"].rank(method="min", ascending=False).astype(int)
        if merged["rank"].isna().any()
        else merged["rank"].astype(int)
    )
    merged["model_rank"] = (
        merged["probability"].rank(method="min", ascending=False).astype(int)
    )
    return merged.sort_values("probability", ascending=False).reset_index(drop=True)


def forecast_findings(view: pd.DataFrame) -> list[str]:
    if view.empty:
        return []
    favorite = view.iloc[0]
    findings = [
        (
            f"{favorite['driver']} é o favorito do modelo, com "
            f"{fmt.percent(favorite['probability'], 1)} de chance."
        )
    ]
    leaders = view[view["rank"].eq(1)]
    if favorite["driver_id"] in set(leaders["driver_id"]):
        findings.append("O favorito também lidera em pontos na data.")
    elif len(leaders):
        leader = leaders.iloc[0]
        findings.append(
            f"O líder em pontos na data é {leader['driver']} "
            f"({fmt.points(leader['points'])} pts); o modelo o coloca em "
            f"{int(leader['model_rank'])}º."
        )
    if len(view) > 3:
        findings.append(
            "Os três mais prováveis concentram "
            f"{fmt.percent(view['probability'].head(3).sum())} da chance."
        )
    contenders = view[view["rank"].le(10)].assign(
        divergence=lambda data: (data["rank"] - data["model_rank"]).abs()
    )
    if len(contenders) and contenders["divergence"].max() >= 2:
        row = contenders.sort_values(
            ["divergence", "rank"], ascending=[False, True]
        ).iloc[0]
        findings.append(
            f"Maior divergência: {row['driver']} é {int(row['rank'])}º em pontos "
            f"e {int(row['model_rank'])}º no modelo."
        )
    return findings


# ---------------------------------------------------------------------- eras


def era_summary(frame: pd.DataFrame, *, current_year: int) -> pd.DataFrame:
    """Uma linha por temporada: contagens explícitas e taxas com denominador declarado."""
    race = frame[frame["session"].eq("Race")]
    wins = race[race["win"]]
    gridded = wins.dropna(subset=["grid"])
    started = race[race["started"]]
    retired = started[started["retired"]]
    summary = pd.DataFrame(
        {
            "races": race.groupby("season")["round"].nunique(),
            "winners": wins.groupby("season")["driver_id"].nunique(),
            "gridded_wins": gridded.groupby("season").size(),
            "pole_wins": gridded[gridded["grid"].eq(1)].groupby("season").size(),
            "starts": started.groupby("season").size(),
            "retirements": retired.groupby("season").size(),
            "technical": retired[retired["cause"].eq("Falha técnica")]
            .groupby("season")
            .size(),
            "undetailed": retired[retired["cause"].eq("Sem motivo detalhado")]
            .groupby("season")
            .size(),
        }
    )
    summary = summary.fillna(0).astype(int).rename_axis("season").reset_index()

    # Mesmo critério de driver_table: pontos, vitórias e nome, sem laço por temporada.
    scores = frame.groupby(["season", "driver_id"]).agg(
        points=("points", "sum"), leader_wins=("win", "sum")
    )
    names = (
        frame.sort_values("date")
        .drop_duplicates(["season", "driver_id"], keep="last")
        .set_index(["season", "driver_id"])[["driver", "team"]]
    )
    leaders = (
        scores.join(names)
        .reset_index()
        .sort_values(
            ["season", "points", "leader_wins", "driver"],
            ascending=[True, False, False, True],
        )
        .drop_duplicates("season")
        .rename(columns={"driver": "leader", "team": "leader_team"})
    )
    summary = summary.merge(
        leaders[["season", "leader", "leader_team", "leader_wins"]],
        on="season",
        how="left",
    )
    summary["leader_wins"] = summary["leader_wins"].fillna(0).astype(int)
    summary["in_progress"] = summary["season"].eq(current_year)
    summary["pole_rate"] = _rate(summary["pole_wins"], summary["gridded_wins"])
    summary["leader_win_share"] = _rate(summary["leader_wins"], summary["races"])
    summary["retirement_rate"] = _rate(summary["retirements"], summary["starts"])
    summary["technical_rate"] = _rate(summary["technical"], summary["starts"])
    # Heurística declarada: poucas corridas em relação ao recorte indicam ingestão parcial.
    summary["partial"] = summary["races"] < 0.75 * summary["races"].median()
    return summary


def _rate(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    return numerator.div(denominator.where(denominator > 0)).astype(float)


def retirement_by_decade(frame: pd.DataFrame) -> pd.DataFrame:
    """Parcela das largadas que terminou em abandono, por década e causa."""
    started = frame[frame["session"].eq("Race") & frame["started"]].assign(
        decade=lambda data: data["season"] // 10 * 10
    )
    if started.empty:
        return pd.DataFrame(columns=["decade", "cause", "count", "starts", "rate"])
    starts = started.groupby("decade").size().rename("starts")
    counts = (
        started[started["retired"]]
        .groupby(["decade", "cause"])
        .size()
        .rename("count")
        .reindex(pd.MultiIndex.from_product([starts.index, CAUSES]), fill_value=0)
        .rename_axis(["decade", "cause"])
        .reset_index()
    )
    counts = counts.join(starts, on="decade")
    counts["rate"] = counts["count"] / counts["starts"]
    return counts


def _decade_rates(summary: pd.DataFrame, numerator: str, denominator: str):
    totals = summary.groupby(summary["season"] // 10 * 10)[
        [numerator, denominator]
    ].sum()
    totals = totals[totals[denominator] > 0]
    return (totals[numerator] / totals[denominator]).sort_index()


def era_findings(summary: pd.DataFrame) -> list[str]:
    if summary.empty:
        return []
    findings = []
    pole = _decade_rates(summary, "pole_wins", "gridded_wins")
    retire = _decade_rates(summary, "retirements", "starts")
    technical = _decade_rates(summary, "technical", "starts")
    if len(pole) > 1:
        findings.append(
            f"Vitórias saindo da pole: {fmt.percent(pole.iloc[0])} nos anos "
            f"{pole.index[0]} → {fmt.percent(pole.iloc[-1])} nos anos {pole.index[-1]}."
        )
    if len(retire) > 1:
        findings.append(
            f"Abandonos: {fmt.percent(retire.iloc[0])} das largadas nos anos "
            f"{retire.index[0]} → {fmt.percent(retire.iloc[-1])} nos anos "
            f"{retire.index[-1]}."
        )
        undetailed = _decade_rates(summary, "undetailed", "retirements")
        text = (
            f"Falhas técnicas: {fmt.percent(technical.iloc[0])} → "
            f"{fmt.percent(technical.iloc[-1])} das largadas"
        )
        if undetailed.iloc[-1] > 0.25:
            # A fonte recente usa "Retired" genérico; a queda por causa fica inflada.
            text += (
                f", mas a fonte não detalha o motivo de "
                f"{fmt.percent(undetailed.iloc[-1])} dos abandonos dos anos "
                f"{undetailed.index[-1]}"
            )
        findings.append(text + ".")
    elif len(retire):
        findings.append(
            f"{fmt.percent(retire.iloc[0])} das largadas terminaram em abandono."
        )
    complete = summary[~summary["partial"] & ~summary["in_progress"]]
    if len(complete):
        balanced = complete.sort_values(["winners", "season"]).iloc[-1]
        findings.append(
            f"Temporada mais equilibrada: {balanced['season']}, com "
            f"{balanced['winners']} vencedores diferentes."
        )
        dominant = complete.sort_values(["leader_win_share", "season"]).iloc[-1]
        findings.append(
            f"Maior domínio: {dominant['leader']} venceu {dominant['leader_wins']} "
            f"de {dominant['races']} corridas em {dominant['season']} "
            f"({fmt.percent(dominant['leader_win_share'])})."
        )
    return findings
