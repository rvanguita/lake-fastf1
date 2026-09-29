"""Dados do lake: linhagem, catálogo Delta, regras de qualidade e cobertura."""

import pandas as pd
import streamlit as st

import charts
import fmt
import lake
import metrics
import ui

ui.header(
    "Dados do lake",
    "Plataforma",
    meta="Raw → Bronze → Silver, orquestrado pelo Airflow; o modelo lê a ABT do Silver.",
)

LINEAGE = """
digraph {
  rankdir=LR; bgcolor="transparent"; nodesep=0.25; ranksep=0.45;
  node [shape=box, style="rounded,filled", fillcolor="#1a1a19", color="#3a3a37",
        fontcolor="#f2f1ec", fontname="Helvetica", fontsize=11];
  edge [color="#8a8a84", arrowsize=0.6];
  fastf1 [label="FastF1", fillcolor="#262624"];
  raw [label="Raw\\nParquet por sessão"];
  bronze [label="Bronze\\nresults (Delta)"];
  stats [label="Silver\\ndriver_statistic_5…50"];
  champions [label="Silver\\nchampions"];
  abt [label="Silver\\ntb_abt"];
  marts [label="Silver\\nmart_standings\\nmart_driver_round"];
  mlflow [label="MLflow\\nmodelo registrado"];
  api [label="FastAPI\\n/v1/predict"];
  apps [label="Streamlit · Dash", fillcolor="#1c2b40", color="#3987e5"];
  mysql [label="MySQL\\nespelho", fillcolor="#262624"];
  fastf1 -> raw -> bronze;
  bronze -> stats -> abt; bronze -> champions -> abt; bronze -> marts;
  abt -> mlflow -> api -> apps; marts -> apps; bronze -> apps;
  bronze -> mysql; marts -> mysql [style=dashed];
}
"""
st.graphviz_chart(LINEAGE, width="stretch")

try:
    infos = [lake.table_info(layer, name) for layer, name in lake.delta_tables()]
except lake.LakeUnavailable as exc:
    ui.unavailable(str(exc))
    st.stop()
catalog = pd.DataFrame([info for info in infos if info.get("available")])
raw = lake.raw_files()
if catalog.empty:
    ui.unavailable("Nenhuma tabela Delta encontrada em " + str(lake.lake_root()))
    st.stop()

bronze_write = catalog.loc[catalog["layer"].eq("bronze"), "last_write"].max()
catalog["description"] = catalog["table"].map(metrics.CATALOG).fillna("")
catalog["state"] = "atualizada"
# Silver escrito antes da última ingestão do Bronze não reflete os dados mais novos.
catalog.loc[
    catalog["layer"].eq("silver") & (catalog["last_write"] < bronze_write),
    "state",
] = "desatualizada"
catalog.loc[catalog["table"].isin(metrics.LEGACY_TABLES), "state"] = "legada"

silver = catalog[catalog["layer"].eq("silver")]
ui.kpis(
    [
        ("Tabelas Delta", str(len(catalog)), f"{len(silver)} no Silver"),
        (
            "Linhas no Silver",
            fmt.number(silver["rows"].sum()),
            f"{fmt.number(silver['size_mb'].sum(), 1)} MB",
        ),
        (
            "Arquivos Raw",
            fmt.number(raw["files"]),
            f"{fmt.number(raw['size_mb'], 1)} MB em Parquet",
        ),
        (
            "Última ingestão",
            fmt.day(bronze_write),
            f"Bronze versão {int(catalog.loc[catalog['layer'].eq('bronze'), 'version'].max())}",
        ),
    ]
)

with st.container(border=True):
    ui.section(
        "Catálogo", "Metadados do log Delta · nenhuma tabela é lida por completo"
    )
    st.dataframe(
        catalog.sort_values(["layer", "table"]),
        hide_index=True,
        column_order=[
            "layer",
            "table",
            "description",
            "state",
            "version",
            "rows",
            "columns",
            "files",
            "size_mb",
            "last_write",
            "operation",
        ],
        column_config={
            "layer": st.column_config.TextColumn("Camada", width="small"),
            "table": st.column_config.TextColumn("Tabela"),
            "description": st.column_config.TextColumn("Conteúdo", width="large"),
            "state": st.column_config.TextColumn(
                "Estado",
                help="desatualizada = escrita antes da última ingestão do Bronze; "
                "legada = fora do DAG",
            ),
            "version": st.column_config.NumberColumn("Versão", width="small"),
            "rows": st.column_config.NumberColumn("Linhas", format="localized"),
            "columns": st.column_config.NumberColumn("Colunas", width="small"),
            "files": st.column_config.NumberColumn("Arquivos", width="small"),
            "size_mb": st.column_config.NumberColumn("MB", format="%.2f"),
            "last_write": st.column_config.DatetimeColumn(
                "Última escrita", format="DD/MM/YYYY HH:mm"
            ),
            "operation": st.column_config.TextColumn("Operação", width="small"),
        },
        height=38 + 35 * len(catalog),
    )
    flagged = catalog[catalog["state"].ne("atualizada")]
    for row in flagged.itertuples():
        st.caption(
            f"**{row.table}** está {row.state}: última escrita em "
            f"{fmt.day(row.last_write)} (versão {row.version})."
        )


def quality_section() -> None:
    ui.section(
        "Regras de qualidade", "Contrato analítico dos marts, da ABT e de champions"
    )
    try:
        checks = metrics.quality_checks(
            lake.read(
                "silver",
                "mart_standings",
                columns=["season", "round_number", "driver_id", "round_points"],
            ),
            lake.read(
                "silver",
                "mart_driver_round",
                columns=[
                    "season",
                    "round_number",
                    "driver_id",
                    "result_status",
                    "started",
                ],
            ),
            lake.read("silver", "tb_abt", columns=["dt_ref", "DriverId"]),
            lake.read("silver", "champions", columns=["Year"]),
        )
    except lake.LakeUnavailable as exc:
        st.info(str(exc))
        return
    passed = int(checks["status"].eq("ok").sum())
    st.progress(
        passed / len(checks), text=f"{passed} de {len(checks)} regras atendidas"
    )
    st.dataframe(
        checks.style.map(
            lambda value: (
                "color: #0ca30c; font-weight: 600"
                if value == "ok"
                else "color: #e66767; font-weight: 600"
            ),
            subset=["status"],
        ),
        hide_index=True,
        column_config={
            "check": "Regra",
            "table": "Tabela",
            "status": "Resultado",
            "failures": st.column_config.NumberColumn("Violações", width="small"),
            "detail": "Critério",
        },
    )


def coverage_section() -> None:
    ui.section("Cobertura por temporada", "Corridas principais no Bronze")
    try:
        coverage = metrics.coverage(
            lake.read("bronze", "results", columns=["Year", "Mode", "RoundNumber"]),
            current=metrics.current_year(),
        )
    except lake.LakeUnavailable as exc:
        st.info(str(exc))
        return
    ui.plot(charts.coverage(coverage))
    partial = coverage.loc[coverage["status"].eq("parcial"), "season"].tolist()
    if partial:
        st.caption(
            "Temporadas parciais (menos de 75% da mediana de corridas): "
            + ", ".join(str(year) for year in partial)
            + ". Totais dessas temporadas não representam o campeonato completo."
        )


with st.container(border=True):
    quality_section()
with st.container(border=True):
    coverage_section()
