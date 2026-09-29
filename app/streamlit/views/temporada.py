"""Temporada: classificação, disputa pelo título, construtores e resultado de cada GP."""

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
    sessions = lake.read(
        "bronze",
        "results",
        columns=["Year", "Mode", "Date", "TeamName", "TeamColor", "Points"],
        filters=lake.season_filter(season, "Year"),
    )
except lake.LakeUnavailable as exc:
    ui.unavailable(str(exc))
    st.stop()

if standings.empty:
    ui.header(f"Temporada {season}", "Campeonato de pilotos")
    st.info("Não há resultados desta temporada nos marts do Silver.")
    st.stop()

summary = metrics.season_summary(standings, results)
live = season == metrics.current_year()
ui.header(
    f"Temporada {season}",
    "Campeonato de pilotos",
    meta=f"{summary['races']} corridas · {summary['rounds']} rodadas com pontos · "
    f"última etapa: {summary['last_event']} ({fmt.day(summary['last_date'])})",
    badge=("Em andamento", "green") if live else ("Temporada encerrada", "gray"),
)
ui.kpis(
    [
        (
            "Líder em pontos",
            "Empate" if summary["tied"] else metrics.short_name(summary["leader"]),
            f"{fmt.points(summary['leader_points'])} pts · {summary['leader_team']}",
        ),
        (
            "Vantagem",
            f"{fmt.points(summary['gap'])} pts" if summary["gap"] is not None else "—",
            f"sobre {metrics.short_name(summary['second'])}"
            if summary["second"]
            else None,
        ),
        (
            "Vencedores diferentes",
            str(summary["winners"]),
            f"em {summary['races']} corridas",
        ),
        (
            "Rodadas disputadas",
            str(summary["rounds"]),
            "Race e Sprint",
        ),
    ]
)


@st.fragment
def title_fight() -> None:
    ui.section(
        "Disputa pelo título",
        "Oito primeiros da classificação atual, rodada a rodada · a temporada inteira",
    )
    metric = st.segmented_control(
        "Métrica",
        ["points", "rank"],
        format_func={"points": "Pontos acumulados", "rank": "Posição"}.get,
        default="points",
        required=True,
        key="disputa",
        label_visibility="collapsed",
    )
    ui.plot(charts.title_fight(metrics.title_fight(standings), metric))


with st.container(border=True):
    title_fight()

table = metrics.standings_table(standings, results)
ui.section("Classificação")
drivers_tab, teams_tab = st.tabs(["Pilotos", "Construtores"])
with drivers_tab:
    st.dataframe(
        table,
        hide_index=True,
        column_order=[
            "rank",
            "driver",
            "team",
            "points",
            "wins",
            "podiums",
            "poles",
            "dnfs",
            "form",
        ],
        column_config={
            "rank": st.column_config.NumberColumn("Pos", width="small"),
            "driver": st.column_config.TextColumn("Piloto"),
            "team": st.column_config.TextColumn("Equipe"),
            "points": st.column_config.ProgressColumn(
                "Pontos",
                min_value=0,
                max_value=float(table["points"].max() or 1),
                format="%g",
            ),
            "wins": st.column_config.NumberColumn("Vitórias", width="small"),
            "podiums": st.column_config.NumberColumn("Pódios", width="small"),
            "poles": st.column_config.NumberColumn("Poles", width="small"),
            "dnfs": st.column_config.NumberColumn("Abandonos", width="small"),
            "form": st.column_config.LineChartColumn(
                "Forma", help="Pontos em cada uma das últimas 5 rodadas", y_min=0
            ),
        },
        height=38 + 35 * len(table),
    )
with teams_tab:
    st.caption("Pontos atribuídos à equipe de cada sessão (Race + Sprint)")
    ui.plot(charts.constructors(metrics.constructors(sessions)))


@st.fragment
def grand_prix() -> None:
    calendar = metrics.race_calendar(results)
    if calendar.empty:
        st.info("Sem corridas principais registradas.")
        return
    labels = {
        row.round_number: f"R{row.round_number:02d} · {row.event}"
        for row in calendar.itertuples()
    }
    head, picker = st.columns([3, 2], vertical_alignment="bottom")
    with head:
        ui.section("Resultado do GP", "Corrida principal · grid e chegada oficiais")
    with picker:
        chosen = st.selectbox(
            "Etapa",
            list(labels),
            index=len(labels) - 1,
            format_func=labels.get,
            key="etapa",
        )
    race = metrics.race_result(results, chosen)
    winner = race[race["official_finish"].eq(1)]
    pole = race[race["official_grid"].eq(1)]
    ui.kpis(
        [
            (
                "Vencedor",
                metrics.short_name(winner.iloc[0]["driver_name"])
                if len(winner)
                else "—",
                winner.iloc[0]["team_name"] if len(winner) else None,
            ),
            (
                "Pole",
                metrics.short_name(pole.iloc[0]["driver_name"]) if len(pole) else "—",
                f"chegou {pole.iloc[0]['position']}" if len(pole) else None,
            ),
            (
                "Abandonos",
                str(int(race["result_status"].eq("DNF").sum())),
                f"de {int(race['started'].sum())} largadas",
            ),
            (
                "Maior recuperação",
                f"+{fmt.number(race['gained'].max())}"
                if race["gained"].gt(0).any()
                else "—",
                "posições · "
                + metrics.short_name(race.loc[race["gained"].idxmax(), "driver_name"])
                if race["gained"].gt(0).any()
                else None,
            ),
        ]
    )
    st.dataframe(
        race,
        hide_index=True,
        column_order=[
            "position",
            "driver_name",
            "team_name",
            "official_grid",
            "gained",
            "points",
            "status",
        ],
        column_config={
            "position": st.column_config.TextColumn("Pos", width="small"),
            "driver_name": st.column_config.TextColumn("Piloto"),
            "team_name": st.column_config.TextColumn("Equipe"),
            "official_grid": st.column_config.NumberColumn(
                "Grid", width="small", help="Vazio = largou do pit lane"
            ),
            "gained": st.column_config.NumberColumn(
                "±", format="%+d", width="small", help="Grid menos chegada"
            ),
            "points": st.column_config.NumberColumn("Pts", format="%g", width="small"),
            "status": st.column_config.TextColumn("Status"),
        },
        height=38 + 35 * len(race),
    )


with st.container(border=True):
    grand_prix()
