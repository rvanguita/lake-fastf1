import os

import pandas as pd
import plotly.express as px
import requests
import streamlit as st
from deltalake import DeltaTable

URI_API = f"http://api-driver-champion:{os.environ['API_PORT']}"
TABLE_PATH_SILVER = os.environ["TABLE_PATH_SILVER"]
TABLE_PATH_BRONZE = os.environ["TABLE_PATH_BRONZE"]


def format_color(color: str):
    if color is None:
        return "#ffffff"
    if color.startswith("#"):
        return color.lower()
    return f"#{color}".lower()


def get_id_predictions(values):
    data = {"values": values.to_dict(orient="records")}
    resp = requests.post(f"{URI_API}/predict", json=data)
    return resp.json().get("predictions")


@st.cache_data(ttl="1d")
def get_predictions():
    data = DeltaTable(TABLE_PATH_SILVER).to_pyarrow_table().to_pandas()

    data = data.fillna(value=-10000)
    data["dt_ref"] = data["dt_ref"].astype("string")
    data["id"] = data["dt_ref"] + "_" + data["DriverId"]
    data["Year"] = pd.to_datetime(data["dt_ref"]).dt.year

    df = get_id_predictions(data)
    df = (
        pd.DataFrame(df)
        .T.reset_index()
        .rename(columns={"index": "id", "1": "prob_win"})
    )

    df = pd.merge(data, df, on="id")
    df["prob_win"] = pd.to_numeric(df["prob_win"], errors="coerce")

    results = (
        DeltaTable(TABLE_PATH_BRONZE)
        .to_pyarrow_table()
        .to_pandas()
        .drop_duplicates(subset=["DriverId"])
    )

    results = results[["DriverId", "TeamName", "TeamColor", "FullName", "TeamId"]]
    results["TeamColor"] = results["TeamColor"].apply(format_color)

    df = pd.merge(df, results, on="DriverId")
    df["driver_team_id"] = df["DriverId"] + "_" + df["TeamId"]

    return df


def render_kpi_row(data: pd.DataFrame) -> None:
    """Show top-3 drivers by latest win probability as metric cards."""
    latest_date = data["dt_ref"].max()
    latest = (
        data[data["dt_ref"] == latest_date]
        .sort_values("prob_win", ascending=False)
        .head(3)
        .reset_index(drop=True)
    )

    medals = ["🥇", "🥈", "🥉"]
    cols = st.columns(3)
    for i, col in enumerate(cols):
        if i >= len(latest):
            break
        row = latest.iloc[i]
        name = row.get("FullName", row["DriverId"])
        team = row.get("TeamName", "")
        prob = float(row["prob_win"]) * 100
        col.metric(
            label=f"{medals[i]} {name}",
            value=f"{prob:.1f}%",
            help=f"Team: {team} · Reference date: {latest_date}",
        )


def build_plotly_chart(
    data_pivot: pd.DataFrame,
    drivers_select: list[str],
    team_colors: list[str],
) -> None:
    """Render an interactive Plotly line chart for win probabilities."""
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
        labels={
            "dt_ref": "Post-Race Date",
            "Win Probability (%)": "Win Probability (%)",
        },
        template="plotly_dark",
    )

    fig.update_traces(line={"width": 2.5}, marker={"size": 6})
    fig.update_layout(
        hovermode="x unified",
        legend={"title": "Driver · Team", "orientation": "h", "y": -0.25},
        yaxis={"ticksuffix": "%", "range": [0, 100]},
        height=480,
        margin={"t": 20, "b": 10},
    )
    st.plotly_chart(fig, width="stretch")


def main() -> None:
    st.set_page_config(
        page_title="F1 Champion Predictor",
        page_icon="🏎️",
        layout="wide",
        initial_sidebar_state="collapsed",
    )

    st.markdown("# 🏁 F1 — Champion Win Predictor")
    st.caption(
        "Predicted championship win probability per driver, updated after each race."
    )
    st.divider()

    with st.spinner("Loading predictions…"):
        data = get_predictions()

    # ── KPI row ─────────────────────────────────────────────────────────────
    render_kpi_row(data)
    st.divider()

    # ── Filters ──────────────────────────────────────────────────────────────
    drivers_data = (
        data[["DriverId", "driver_team_id", "dt_ref"]]
        .sort_values(["dt_ref", "driver_team_id"])
        .drop_duplicates(subset=["DriverId"], keep="first")
        .dropna()
    )

    most_prob = data.sort_values(by=["dt_ref", "prob_win"], ascending=False).head(5)

    col_driver, col_year = st.columns(2)
    with col_driver:
        driver_selected = st.multiselect(
            "🏎️ Driver",
            options=drivers_data["driver_team_id"].tolist(),
            default=most_prob["driver_team_id"].tolist(),
        )
    with col_year:
        year_selected = st.multiselect(
            "📅 Season",
            options=sorted(data["Year"].unique(), reverse=True),
            default=[int(data["Year"].max())],
        )

    # ── Filtered data ────────────────────────────────────────────────────────
    data_filter = data[
        data["driver_team_id"].isin(driver_selected) & data["Year"].isin(year_selected)
    ]

    if data_filter.empty:
        st.warning(
            "No data for the selected filters. Try a different driver or season."
        )
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

    column_config = {
        col: st.column_config.NumberColumn(col, format="percent")
        for col in data_pivot.columns[1:]
    }
    column_config["dt_ref"] = st.column_config.DateColumn("Prediction Date")

    # ── Tabs ─────────────────────────────────────────────────────────────────
    tab_chart, tab_data = st.tabs(["📈 Chart", "📋 Data"])

    with tab_chart:
        build_plotly_chart(data_pivot, drivers_select, team_colors)

    with tab_data:
        st.markdown("#### Win probability by race")
        st.dataframe(data_pivot, column_config=column_config, width="stretch")

        with st.expander("Full feature table"):
            st.dataframe(data_filter, width="stretch")

    st.caption(f"Last prediction date: **{data['dt_ref'].max()}**")


if __name__ == "__main__":
    main()
