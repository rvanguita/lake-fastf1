from __future__ import annotations

import os

import pendulum

from airflow.sdk import Asset, dag, get_current_context, task

from src.consolidate_data import consolidate_data
from src.extract_data import ExtractData
from src.silver_data import main as process_silver_data

PATH_RAW = os.environ["PATH_RAW"]
PATH_BRONZE = os.environ["PATH_BRONZE"]
PATH_SILVER = os.environ["PATH_SILVER"]


# ---------------------------------------------------------------------------
# Assets
# ---------------------------------------------------------------------------

RAW_RESULTS = Asset(
    name="raw_results",
    uri=f"file://{PATH_RAW}/results",
)

BRONZE_RESULTS = Asset(
    name="bronze_results",
    uri=f"file://{PATH_BRONZE}/results",
)

SILVER_CHAMPIONS = Asset(
    name="silver_champions",
    uri=f"file://{PATH_SILVER}/champions",
)

SILVER_DRIVER_STATISTIC_5 = Asset(
    name="silver_driver_statistic_5",
    uri=f"file://{PATH_SILVER}/driver_statistic_5",
)

SILVER_DRIVER_STATISTIC_10 = Asset(
    name="silver_driver_statistic_10",
    uri=f"file://{PATH_SILVER}/driver_statistic_10",
)

SILVER_DRIVER_STATISTIC_20 = Asset(
    name="silver_driver_statistic_20",
    uri=f"file://{PATH_SILVER}/driver_statistic_20",
)

SILVER_DRIVER_STATISTIC_40 = Asset(
    name="silver_driver_statistic_40",
    uri=f"file://{PATH_SILVER}/driver_statistic_40",
)

SILVER_DRIVER_STATISTIC_LIFE = Asset(
    name="silver_driver_statistic_life",
    uri=f"file://{PATH_SILVER}/driver_statistic_life",
)

SILVER_DRIVER_ALL_STATISTIC = Asset(
    name="silver_driver_all_statistic",
    uri=f"file://{PATH_SILVER}/driver_all_statistic",
)

SILVER_TB_ABT = Asset(
    name="silver_tb_abt",
    uri=f"file://{PATH_SILVER}/tb_abt",
)


# ---------------------------------------------------------------------------
# DAG
# ---------------------------------------------------------------------------

@dag(
    dag_id="data-pipeline",
    description="Pipeline Raw, Bronze e Silver",
    schedule="0 0 * * 1",
    start_date=pendulum.datetime(
        2026,
        7,
        28,
        tz="America/Sao_Paulo",
    ),
    catchup=False,
    max_active_runs=1,
    tags=["f1", "etl"],
)
def formula_one_data_pipeline() -> None:

    @task(task_id="extract_fastf1",
          outlets=[RAW_RESULTS],
          )
    def extract_fastf1() -> bool:
        context = get_current_context()
        execution_year = context["data_interval_end"].year

        extractor = ExtractData(
            years=[execution_year],
            identifiers=["R", "S"],
            reload_data=False,
        )

        return extractor.process_years()

    @task.short_circuit(task_id="has_new_data")
    def has_new_data(updated: bool) -> bool:
        return updated

    @task(
        task_id="create_bronze_results",
        inlets=[RAW_RESULTS],
        outlets=[BRONZE_RESULTS],
    )
    def create_bronze_results() -> None:
        consolidate_data("results")

    @task(
        task_id="create_silver_tables",
        inlets=[BRONZE_RESULTS],
        outlets=[
            SILVER_CHAMPIONS,
            SILVER_DRIVER_STATISTIC_5,
            SILVER_DRIVER_STATISTIC_10,
            SILVER_DRIVER_STATISTIC_20,
            SILVER_DRIVER_STATISTIC_40,
            SILVER_DRIVER_STATISTIC_LIFE,
            SILVER_DRIVER_ALL_STATISTIC,
            SILVER_TB_ABT,
        ],
    )
    def create_silver_tables() -> None:
        context = get_current_context()
        execution_year = context["data_interval_end"].year

        process_silver_data(
            year_stop=execution_year,
        )
        
    # -----------------------------------------------------------------------
    # Instâncias das tasks
    # -----------------------------------------------------------------------
    
    extracted = extract_fastf1()
    validation = has_new_data(extracted)
    bronze = create_bronze_results()
    silver = create_silver_tables()

    # -----------------------------------------------------------------------
    # Ordem real de execução
    # -----------------------------------------------------------------------

    # validation >> bronze >> silver
    bronze >> silver


f1_data_pipeline = formula_one_data_pipeline()