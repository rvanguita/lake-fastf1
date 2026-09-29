"""Pilotos: temporada, corrida a corrida, companheiros, carreira e forma no Silver."""

from datetime import date

import streamlit as st

import charts
import fmt
import lake
import metrics
import ui

season = ui.season()
try:
    standings = lake.read(
        "silver", "mart_standings", filters=lake.season_filter(season)
    )
    results = lake.read(
        "silver", "mart_driver_round", filters=lake.season_filter(season)
    )
except lake.LakeUnavailable as exc:
    ui.unavailable(str(exc))
    st.stop()

table = metrics.standings_table(standings, results)
if table.empty:
    ui.header("Pilotos", f"Temporada {season}")
    st.info("Não há resultados desta temporada nos marts do Silver.")
    st.stop()

names = dict(zip(table["driver_id"], table["driver"], strict=True))
title, picker = st.columns([3, 1], vertical_alignment="bottom")
with picker:
    # ?piloto=<nome> reproduz a visão; um nome fora da temporada volta ao líder.
    driver_id = st.selectbox(
        "Piloto",
        list(names),
        format_func=names.get,
        key="piloto",
        bind="query-params",
    )
profile = metrics.driver_season(standings, results, driver_id)
with title:
    ui.header(
        profile["driver"],
        f"Temporada {season} · {profile['team']}",
        badge=(f"{fmt.ordinal(profile['rank'])} no campeonato", "blue"),
    )

try:
    bronze = lake.read(
        "bronze",
        "results",
        columns=["DriverId", "Date", "DriverNumber", "HeadshotUrl", "CountryCode"],
        filters=(("Year", "=", season), ("DriverId", "=", driver_id)),
    ).sort_values("Date")
except lake.LakeUnavailable:
    bronze = None

photo, stats = st.columns([1, 5], vertical_alignment="center")
with photo:
    url = (
        ""
        if bronze is None or bronze.empty
        else str(bronze.iloc[-1]["HeadshotUrl"] or "")
    )
    if url.startswith("https://"):
        st.image(url, width=140)
    number = (
        ""
        if bronze is None or bronze.empty
        else str(bronze.iloc[-1]["DriverNumber"] or "")
    )
    st.caption(f"#{number} · {profile['code']}" if number else profile["code"])
with stats:
    ui.kpis(
        [
            ("Pontos", fmt.points(profile["points"]), None),
            ("Vitórias", str(profile["wins"]), f"{profile['podiums']} pódios"),
            (
                "Poles",
                str(profile["poles"]),
                f"grid médio {fmt.number(profile['avg_grid'], 1)}",
            ),
            (
                "Chegada média",
                fmt.number(profile["avg_finish"], 1),
                "concluídas",
            ),
            ("Abandonos", str(profile["dnfs"]), f"em {profile['starts']} largadas"),
        ]
    )

with st.container(border=True):
    ui.section(
        "Corrida a corrida",
        "Círculo vazio = largada · círculo cheio = chegada · × = não completou",
    )
    ui.plot(
        charts.race_by_race(metrics.race_by_race(results, driver_id), profile["color"])
    )

left, right = st.columns([1, 2], gap="large")
with left:
    ui.section(
        "Duelo com o companheiro", "Corridas principais em que dividiram a equipe"
    )
    duels = metrics.teammate_duels(results, driver_id)
    if duels.empty:
        st.info("Sem companheiro de equipe registrado nesta temporada.")
    for duel in duels.itertuples():
        with st.container(border=True):
            st.markdown(f"**vs {duel.teammate}** · {duel.races} corridas juntos")
            a, b = st.columns(2)
            a.metric("À frente na corrida", f"{duel.race_ahead}/{duel.races}")
            b.metric("À frente no grid", f"{duel.grid_ahead}/{duel.grid_races}")
            st.metric(
                "Pontos nas mesmas corridas",
                fmt.points(duel.points),
                delta=f"{fmt.points(duel.points_mate)} do companheiro",
                delta_color="off",
                delta_arrow="off",
            )

with right:
    ui.section(
        "Forma nas janelas do Silver",
        "Últimas N sessões (Race + Sprint) na data mais recente da ABT",
    )
    columns = [
        "dt_ref",
        "DriverId",
        *[
            f"{metric}_{window}"
            for metric in metrics.WINDOW_METRICS
            for window in metrics.WINDOWS
        ],
    ]
    try:
        abt = lake.read(
            "silver",
            "tb_abt",
            columns=columns,
            filters=(
                ("DriverId", "=", driver_id),
                ("dt_ref", ">=", date(season, 1, 1)),
                ("dt_ref", "<", date(season + 1, 1, 1)),
            ),
        )
    except lake.LakeUnavailable as exc:
        abt = None
        st.info(str(exc))
    if abt is not None and not abt.empty:
        latest = abt.sort_values("dt_ref").iloc[-1]
        st.dataframe(
            metrics.window_form(latest),
            hide_index=True,
            column_config={
                "window": st.column_config.TextColumn("Janela"),
                "Pontos": st.column_config.NumberColumn(format="%g"),
                "Grid médio": st.column_config.NumberColumn(format="%.1f"),
                "Chegada média": st.column_config.NumberColumn(format="%.1f"),
            },
        )
        st.caption(f"Referência: {fmt.day(latest['dt_ref'])}")
    elif abt is not None:
        st.info("A ABT não tem linhas deste piloto na temporada.")

with st.container(border=True):
    ui.section(
        "Carreira no lake",
        "Todas as temporadas do piloto disponíveis no lake (1980 em diante)",
    )
    try:
        career_standings = lake.read(
            "silver",
            "mart_standings",
            columns=[
                "season",
                "round_number",
                "team_name",
                "championship_rank",
                "cumulative_points",
            ],
            filters=(("driver_id", "=", driver_id),),
        )
        career_results = lake.read(
            "silver",
            "mart_driver_round",
            columns=["season", "official_finish", "official_grid", "started"],
            filters=(("driver_id", "=", driver_id),),
        )
        coverage = metrics.coverage(
            lake.read("bronze", "results", columns=["Year", "Mode", "RoundNumber"]),
            current=metrics.current_year(),
        )
    except lake.LakeUnavailable as exc:
        st.info(str(exc))
    else:
        history = metrics.career(career_standings, career_results).merge(
            coverage[["season", "status"]], on="season", how="left"
        )
        chart, grid = st.columns([1, 2], gap="large")
        with chart:
            ui.plot(charts.career(history))
        with grid:
            st.dataframe(
                history.sort_values("season", ascending=False),
                hide_index=True,
                height=min(38 + 35 * len(history), 740),
                column_config={
                    "season": st.column_config.NumberColumn("Ano", format="%d"),
                    "team": "Equipe",
                    "rank": st.column_config.NumberColumn("Pos", format="%dº"),
                    "points": st.column_config.NumberColumn("Pontos", format="%g"),
                    "wins": "Vitórias",
                    "podiums": "Pódios",
                    "poles": "Poles",
                    "starts": "Largadas",
                    "status": st.column_config.TextColumn(
                        "Cobertura",
                        help="Temporadas parciais têm corridas faltando no lake",
                    ),
                },
            )
