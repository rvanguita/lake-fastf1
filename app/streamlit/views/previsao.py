"""Previsão e modelo: chances de título pela API, evolução, explicação e model card."""

from datetime import date

import pandas as pd
import streamlit as st

import charts
import fmt
import lake
import metrics
import model_api
import ui

season = ui.season()
ui.header(
    f"Previsão {season}",
    "Modelo de campeão",
    meta="Probabilidades do modelo publicado no MLflow, servidas pela API.",
)

try:
    info = model_api.model_info()
except model_api.ModelUnavailable as exc:
    ui.unavailable(
        f"{exc} As páginas de temporada, pilotos e dados continuam funcionando.",
        title="Previsão indisponível",
    )
    st.stop()
features = [str(name) for name in info.get("features", [])]

try:
    standings = lake.read(
        "silver", "mart_standings", filters=lake.season_filter(season)
    )
    results = lake.read(
        "silver", "mart_driver_round", filters=lake.season_filter(season)
    )
    abt = lake.read(
        "silver",
        "tb_abt",
        columns=["dt_ref", "DriverId", *features],
        filters=(
            ("dt_ref", ">=", date(season, 1, 1)),
            ("dt_ref", "<", date(season + 1, 1, 1)),
        ),
    )
except lake.LakeUnavailable as exc:
    ui.unavailable(str(exc))
    st.stop()

debuts = standings.groupby("driver_id")["event_date"].min()
candidates = metrics.candidates(abt, debuts)
if candidates.empty:
    st.info(f"A ABT não tem datas de referência para {season}.")
    st.stop()

drivers = metrics.standings_table(standings, results).set_index("driver_id")
latest_date = candidates["dt_ref"].max()
latest_candidates = candidates[candidates["dt_ref"].eq(latest_date)]
try:
    with st.spinner("Consultando o modelo…"):
        latest_predictions = model_api.predict(
            latest_candidates, features, intervals=True
        )
        all_predictions = model_api.predict(candidates, features)
except model_api.ModelUnavailable as exc:
    ui.unavailable(str(exc), title="Previsão indisponível")
    st.stop()


def with_names(frame: pd.DataFrame) -> pd.DataFrame:
    frame = frame.join(drivers[["driver", "team", "color"]], on="driver_id")
    frame["driver"] = frame["driver"].fillna(frame["driver_id"])
    frame["color"] = frame["color"].fillna(metrics.FALLBACK_COLOR)
    return frame


latest = with_names(
    metrics.forecast_frame(latest_predictions, latest_candidates)
).sort_values("probability", ascending=False)
card: dict = {}
try:
    card = model_api.model_card()
except model_api.ModelUnavailable:
    pass

trained = card.get("trained_through")
simulated = season < metrics.current_year() or (
    isinstance(trained, int) and season <= trained
)
if simulated:
    st.info(
        "Temporada passada: estas chances são uma simulação com o modelo publicado "
        "hoje, não uma previsão feita na época.",
        icon=":material/history:",
    )

favorite = latest.iloc[0]
ui.kpis(
    [
        (
            "Favorito",
            metrics.short_name(favorite["driver"]),
            f"{fmt.percent(favorite['probability'])} de chance",
        ),
        (
            "Três mais prováveis",
            fmt.percent(latest["probability"].head(3).sum()),
            "da chance total",
        ),
        ("Candidatos", str(len(latest)), "pilotos que já estrearam"),
        (
            "Data de referência",
            fmt.day(latest_date),
            f"{candidates['dt_ref'].nunique()} datas na ABT",
        ),
    ]
)

odds, evolution = st.columns(2, gap="large")
with odds, st.container(border=True):
    ui.section(
        "Chances de título",
        "Dez maiores · barra = estimativa, traço = faixa p10–p90 do ensemble",
    )
    ui.plot(charts.odds(latest.head(10)))
with evolution, st.container(border=True):
    ui.section("Evolução ao longo da temporada", "Cinco favoritos na data mais recente")
    history = with_names(metrics.forecast_frame(all_predictions, candidates))
    top = latest.head(5)["driver_id"].tolist()
    history = history[history["driver_id"].isin(top)].copy()
    history["order"] = history["driver_id"].map({d: i for i, d in enumerate(top)})
    ui.plot(charts.odds_evolution(history.sort_values(["order", "dt_ref"])))


@st.fragment
def explanation() -> None:
    ui.section(
        "Por que o modelo pensa assim",
        "Contribuições SHAP da data mais recente · azul aumenta a chance, laranja reduz",
    )
    options = latest.head(10)["driver_id"].tolist()
    chosen = st.selectbox(
        "Piloto",
        options,
        format_func=dict(zip(latest["driver_id"], latest["driver"], strict=True)).get,
        key="explicar",
    )
    row = latest_candidates[latest_candidates["DriverId"].eq(chosen)]
    try:
        result = model_api.explain(row, features)
    except model_api.ModelUnavailable as exc:
        st.info(f"Explicação indisponível. {exc}")
        return
    frame = pd.DataFrame(result.get("contributions", []))
    if frame.empty:
        st.info("A API não retornou contribuições para este piloto.")
        return
    frame["label"] = frame["feature"].map(metrics.feature_label)
    ui.plot(charts.contributions(frame))


with st.container(border=True):
    explanation()


def importance_chart(importances: pd.Series) -> None:
    if importances.empty:
        return
    st.markdown("**Features mais importantes**")
    top_features = (
        importances.sort_values(ascending=False)
        .head(12)
        .rename("importance")
        .rename_axis("feature")
        .reset_index()
    )
    top_features["label"] = top_features["feature"].map(metrics.feature_label)
    ui.plot(charts.importances(top_features))


def validation(evaluations: pd.DataFrame, calibration: pd.DataFrame) -> None:
    if not evaluations.empty:
        st.markdown("**Backtests por temporada**")
        st.dataframe(
            evaluations,
            hide_index=True,
            column_config={
                "season": st.column_config.NumberColumn("Ano", format="%d"),
                "top1_accuracy": st.column_config.NumberColumn(
                    "Acerto do campeão", format="percent"
                ),
                "baseline_accuracy": st.column_config.NumberColumn(
                    "Referência ingênua", format="percent"
                ),
            },
        )
    if {"predicted", "observed"}.issubset(calibration.columns):
        st.markdown("**Calibração**")
        ui.plot(charts.calibration(calibration))


with st.container(border=True):
    ui.section("Sobre o modelo")
    status = card.get("status")
    row = st.container(horizontal=True)
    row.badge(
        {"validated": "Validado", "experimental": "Experimental"}.get(
            status, str(status or "Status não informado")
        ),
        color="green" if status == "validated" else "orange",
    )
    row.badge(
        f"Treinado até {trained}" if trained else "Corte de treino não publicado",
        color="gray",
    )
    row.badge(f"{len(features)} features", color="gray")

    evaluations = pd.DataFrame(card.get("evaluations") or [])
    calibration = pd.DataFrame(card.get("calibration") or [])
    if evaluations.empty and calibration.empty:
        st.caption(
            "A versão publicada não traz backtests nem curva de calibração no model "
            "card; eles aparecem aqui após um novo treino."
        )
    importances = pd.Series(info.get("importances") or {}, dtype=float)
    has_validation = not (evaluations.empty and calibration.empty)
    if has_validation:
        left, right = st.columns(2, gap="large")
        with left:
            importance_chart(importances)
        with right:
            validation(evaluations, calibration)
    else:
        importance_chart(importances)
    for limitation in card.get("limitations") or []:
        st.caption(f"• {limitation}")
