import os

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
import streamlit as st
from deltalake import DeltaTable

URI_API = f"http://api-driver-champion:{os.environ['API_PORT']}"
TABLE_PATH_SILVER = os.environ["TABLE_PATH_SILVER"]
TABLE_PATH_BRONZE = os.environ["TABLE_PATH_BRONZE"]

N_RECENT_RACES = 5


# ── Helpers ──────────────────────────────────────────────────────────────────

def format_color(color: str) -> str:
    if color is None:
        return "#ffffff"
    if color.startswith("#"):
        return color.lower()
    return f"#{color}".lower()


def get_id_predictions(values: pd.DataFrame):
    data = {"values": values.to_dict(orient="records")}
    resp = requests.post(f"{URI_API}/predict", json=data)
    return resp.json().get("predictions")


# ── Data loaders ─────────────────────────────────────────────────────────────

@st.cache_data(ttl="1d")
def get_bronze() -> pd.DataFrame:
    """Full race/qualifying results from the Bronze layer."""
    df = DeltaTable(TABLE_PATH_BRONZE).to_pyarrow_table().to_pandas()
    df["TeamColor"] = df["TeamColor"].apply(format_color)
    return df


@st.cache_data(ttl="1d")
def get_predictions() -> pd.DataFrame:
    """Silver ABT + predictions from the API, enriched with Bronze driver info."""
    data = DeltaTable(TABLE_PATH_SILVER).to_pyarrow_table().to_pandas()

    data = data.fillna(value=-10000)
    data["dt_ref"] = data["dt_ref"].astype("string")
    data["id"] = data["dt_ref"] + "_" + data["DriverId"]
    data["Year"] = pd.to_datetime(data["dt_ref"]).dt.year

    preds = get_id_predictions(data)
    preds_df = (
        pd.DataFrame(preds)
        .T.reset_index()
        .rename(columns={"index": "id", "1": "prob_win"})
    )
    data = pd.merge(data, preds_df, on="id")
    data["prob_win"] = pd.to_numeric(data["prob_win"], errors="coerce")

    driver_info = (
        get_bronze()
        .drop_duplicates(subset=["DriverId"])[
            ["DriverId", "TeamName", "TeamColor", "FullName", "TeamId",
             "HeadshotUrl", "CountryCode", "Abbreviation"]
        ]
    )
    data = pd.merge(data, driver_info, on="DriverId")
    data["driver_team_id"] = data["DriverId"] + "_" + data["TeamId"]
    return data


# ── Section renderers ─────────────────────────────────────────────────────────

def render_kpi_row(data: pd.DataFrame) -> None:
    """Top-3 drivers by latest prediction win probability."""
    latest_date = data["dt_ref"].max()
    top3 = (
        data[data["dt_ref"] == latest_date]
        .sort_values("prob_win", ascending=False)
        .head(3)
        .reset_index(drop=True)
    )
    medals = ["🥇", "🥈", "🥉"]
    cols = st.columns(3)
    for i, col in enumerate(cols):
        if i >= len(top3):
            break
        row = top3.iloc[i]
        name = row.get("FullName", row["DriverId"])
        team = row.get("TeamName", "")
        prob = float(row["prob_win"]) * 100

        # delta vs previous race
        prev_dates = sorted(data["dt_ref"].unique())
        delta_str = None
        if len(prev_dates) >= 2:
            prev_date = prev_dates[-2]
            prev_row = data[
                (data["dt_ref"] == prev_date) & (data["DriverId"] == row["DriverId"])
            ]
            if not prev_row.empty:
                delta = (float(row["prob_win"]) - float(prev_row["prob_win"].iloc[0])) * 100
                delta_str = f"{delta:+.1f}%"

        col.metric(
            label=f"{medals[i]} {name}",
            value=f"{prob:.1f}%",
            delta=delta_str,
            help=f"Team: {team} · Date: {latest_date}",
        )


def render_recent_races(bronze: pd.DataFrame, n: int = N_RECENT_RACES) -> None:
    """Top-5 finishers for each of the last N race rounds."""
    races = (
        bronze[bronze["Mode"] == "Race"]
        .dropna(subset=["Position"])
        .copy()
    )
    races["Position"] = races["Position"].astype(int)

    # last N unique rounds by date
    recent_rounds = (
        races.drop_duplicates(subset=["Year", "RoundNumber"])
        .sort_values("Date", ascending=False)
        .head(n)[["Year", "RoundNumber", "EventName", "Date"]]
    )

    st.markdown(f"### 🏆 Last {n} Race Results — Top 5")

    cols = st.columns(n)
    for col, (_, rnd) in zip(cols, recent_rounds.iterrows()):
        top5 = (
            races[
                (races["Year"] == rnd["Year"])
                & (races["RoundNumber"] == rnd["RoundNumber"])
                & (races["Position"] <= 5)
            ]
            .sort_values("Position")[
                ["Position", "Abbreviation", "TeamName", "TeamColor", "Points"]
            ]
            .reset_index(drop=True)
        )

        race_date = pd.to_datetime(rnd["Date"]).strftime("%b %d")
        col.markdown(f"**{rnd['EventName']}**  \n`{race_date}`")

        for _, driver in top5.iterrows():
            color = driver["TeamColor"] if driver["TeamColor"] else "#888888"
            col.markdown(
                f"<span style='color:{color}; font-weight:600'>"
                f"P{int(driver['Position'])} {driver['Abbreviation']}</span>"
                f" <span style='font-size:0.8em; color:#aaa'>({driver['TeamName']})</span>",
                unsafe_allow_html=True,
            )


def render_points_bar(bronze: pd.DataFrame, year: int) -> None:
    """Accumulated championship points for the selected season."""
    races = (
        bronze[(bronze["Mode"] == "Race") & (bronze["Year"] == year)]
        .dropna(subset=["Points"])
    )
    if races.empty:
        st.info("No race points data for this season.")
        return

    points_total = (
        races.groupby(["FullName", "TeamName", "TeamColor"], as_index=False)["Points"]
        .sum()
        .sort_values("Points", ascending=True)
    )

    fig = px.bar(
        points_total,
        x="Points",
        y="FullName",
        orientation="h",
        color="TeamName",
        color_discrete_map={
            row["TeamName"]: row["TeamColor"]
            for _, row in points_total.iterrows()
        },
        template="plotly_dark",
        labels={"FullName": "", "Points": "Championship Points"},
    )
    fig.update_layout(
        height=max(350, len(points_total) * 28),
        margin={"t": 10, "b": 10, "l": 10},
        showlegend=False,
    )
    st.plotly_chart(fig, width="stretch")


def render_win_prob_chart(
    data_pivot: pd.DataFrame,
    drivers_select: list[str],
    team_colors: list[str],
) -> None:
    """Win probability over time — Plotly line chart."""
    df_long = data_pivot.melt(
        id_vars="dt_ref",
        value_vars=drivers_select,
        var_name="Driver",
        value_name="Win Probability",
    )
    df_long["Win Probability (%)"] = df_long["Win Probability"] * 100

    color_map = dict(zip(drivers_select, team_colors))
    fig = px.line(
        df_long,
        x="dt_ref",
        y="Win Probability (%)",
        color="Driver",
        color_discrete_map=color_map,
        markers=True,
        labels={"dt_ref": "Post-Race Date"},
        template="plotly_dark",
    )
    fig.update_traces(line={"width": 2.5}, marker={"size": 6})
    fig.update_layout(
        hovermode="x unified",
        legend={"title": "Driver · Team", "orientation": "h", "y": -0.28},
        yaxis={"ticksuffix": "%", "range": [0, 100]},
        height=460,
        margin={"t": 20, "b": 10},
    )
    st.plotly_chart(fig, width="stretch")


def render_season_progression(bronze: pd.DataFrame, year: int) -> None:
    """Cumulative points progression per driver across rounds."""
    races = (
        bronze[(bronze["Mode"] == "Race") & (bronze["Year"] == year)]
        .dropna(subset=["Points", "RoundNumber"])
        .sort_values("RoundNumber")
    )
    if races.empty:
        return

    cumulative = (
        races.groupby(["FullName", "TeamName", "TeamColor", "RoundNumber", "EventName"])["Points"]
        .sum()
        .reset_index()
        .sort_values(["FullName", "RoundNumber"])
    )
    cumulative["Cumulative Points"] = cumulative.groupby("FullName")["Points"].cumsum()

    color_map = {
        row["FullName"]: row["TeamColor"]
        for _, row in cumulative.drop_duplicates("FullName").iterrows()
    }

    fig = px.line(
        cumulative,
        x="RoundNumber",
        y="Cumulative Points",
        color="FullName",
        color_discrete_map=color_map,
        markers=True,
        hover_data={"EventName": True},
        labels={"RoundNumber": "Round", "FullName": "Driver"},
        template="plotly_dark",
    )
    fig.update_traces(line={"width": 2}, marker={"size": 5})
    fig.update_layout(
        height=420,
        legend={"orientation": "h", "y": -0.3, "title": "Driver"},
        margin={"t": 10, "b": 10},
        hovermode="x unified",
    )
    st.plotly_chart(fig, width="stretch")


def render_head_to_head(bronze: pd.DataFrame, year: int) -> None:
    """Race-by-race head-to-head finishing position heatmap."""
    races = (
        bronze[(bronze["Mode"] == "Race") & (bronze["Year"] == year)]
        .dropna(subset=["Position", "RoundNumber"])
        .copy()
    )
    if races.empty:
        return

    races["Position"] = races["Position"].astype(int)
    pivot = races.pivot_table(
        index="Abbreviation", columns="EventName", values="Position", aggfunc="min"
    )

    fig = go.Figure(
        data=go.Heatmap(
            z=pivot.values,
            x=pivot.columns.tolist(),
            y=pivot.index.tolist(),
            colorscale="RdYlGn_r",
            zmin=1,
            zmax=20,
            colorbar={"title": "Position"},
            hovertemplate="Driver: %{y}<br>Race: %{x}<br>Position: %{z}<extra></extra>",
        )
    )
    fig.update_layout(
        template="plotly_dark",
        height=max(300, len(pivot) * 26),
        margin={"t": 10, "b": 80, "l": 60},
        xaxis={"tickangle": -35},
    )
    st.plotly_chart(fig, width="stretch")


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    st.set_page_config(
        page_title="F1 Champion Predictor",
        page_icon="🏎️",
        layout="wide",
        initial_sidebar_state="collapsed",
    )

    st.markdown("# 🏁 F1 — Champion Win Predictor")
    st.caption("Championship win probability per driver, updated after each race.")
    st.divider()

    with st.spinner("Loading data…"):
        data = get_predictions()
        bronze = get_bronze()

    # ── Top-3 KPI cards ───────────────────────────────────────────────────────
    render_kpi_row(data)
    st.divider()

    # ── Recent race results ───────────────────────────────────────────────────
    render_recent_races(bronze)
    st.divider()

    # ── Filters ───────────────────────────────────────────────────────────────
    most_prob = data.sort_values(by=["dt_ref", "prob_win"], ascending=False).head(5)
    drivers_data = (
        data[["DriverId", "driver_team_id", "dt_ref"]]
        .sort_values(["dt_ref", "driver_team_id"])
        .drop_duplicates(subset=["DriverId"], keep="first")
        .dropna()
    )

    col_driver, col_year = st.columns([2, 1])
    with col_driver:
        driver_selected = st.multiselect(
            "🏎️ Drivers",
            options=drivers_data["driver_team_id"].tolist(),
            default=most_prob["driver_team_id"].unique().tolist(),
        )
    with col_year:
        year_selected = st.multiselect(
            "📅 Season",
            options=sorted(data["Year"].unique(), reverse=True),
            default=[int(data["Year"].max())],
        )

    data_filter = data[
        data["driver_team_id"].isin(driver_selected) & data["Year"].isin(year_selected)
    ]

    if data_filter.empty:
        st.warning("No data for the selected filters. Try a different driver or season.")
        return

    data_pivot = data_filter.pivot_table(
        index="dt_ref", columns="driver_team_id", values="prob_win"
    ).reset_index()
    drivers_select = data_pivot.columns.tolist()[1:]

    team_colors = (
        data_filter[["driver_team_id", "TeamColor"]]
        .drop_duplicates("driver_team_id")
        .set_index("driver_team_id")
        .reindex(drivers_select)["TeamColor"]
        .tolist()
    )

    column_config_pivot = {
        col: st.column_config.NumberColumn(col, format="percent")
        for col in data_pivot.columns[1:]
    }
    column_config_pivot["dt_ref"] = st.column_config.DateColumn("Prediction Date")

    # ── Tabs ──────────────────────────────────────────────────────────────────
    tab_prob, tab_points, tab_progression, tab_heatmap, tab_data = st.tabs(
        ["📈 Win Probability", "🏅 Points Ranking", "📊 Season Progression", "🗺️ Position Heatmap", "📋 Data"]
    )

    with tab_prob:
        render_win_prob_chart(data_pivot, drivers_select, team_colors)

    with tab_points:
        sel_year = year_selected[0] if year_selected else int(data["Year"].max())
        render_points_bar(bronze, sel_year)

    with tab_progression:
        sel_year = year_selected[0] if year_selected else int(data["Year"].max())
        render_season_progression(bronze, sel_year)

    with tab_heatmap:
        sel_year = year_selected[0] if year_selected else int(data["Year"].max())
        render_head_to_head(bronze, sel_year)

    with tab_data:
        st.markdown("#### Win probability by race")
        st.dataframe(data_pivot, column_config=column_config_pivot, width="stretch")
        with st.expander("Full feature table"):
            st.dataframe(data_filter, width="stretch")

    st.caption(f"Last prediction date: **{data['dt_ref'].max()}**")


if __name__ == "__main__":
    main()
