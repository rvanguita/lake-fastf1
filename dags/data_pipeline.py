from __future__ import annotations

import os

import pendulum

from airflow.sdk import (
    Asset,
    dag,
    get_current_context,
    task,
    task_group,
)

from src.consolidate_data import consolidate_data
from src.extract_data import ExtractData
from src.silver_data import (
    build_champions_table,
    build_driver_all_statistic_table,
    build_driver_statistic_table,
    build_tb_abt_table,
)


PATH_RAW = os.environ["PATH_RAW"]
PATH_BRONZE = os.environ["PATH_BRONZE"]
PATH_SILVER = os.environ["PATH_SILVER"]


# ---------------------------------------------------------------------------
# Assets Raw
# ---------------------------------------------------------------------------

RAW_RESULTS = Asset(
    name="raw_results",
    uri=f"file://{PATH_RAW}/results",
)


# ---------------------------------------------------------------------------
# Assets Bronze
# ---------------------------------------------------------------------------

BRONZE_RESULTS = Asset(
    name="bronze_results",
    uri=f"file://{PATH_BRONZE}/results",
)


# ---------------------------------------------------------------------------
# Assets Silver
# ---------------------------------------------------------------------------

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

SILVER_DRIVER_STATISTIC_100 = Asset(
    name="silver_driver_statistic_100",
    uri=f"file://{PATH_SILVER}/driver_statistic_100",
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

    # -----------------------------------------------------------------------
    # Raw
    # -----------------------------------------------------------------------

    @task_group(group_id="raw")
    def raw_layer() -> None:

        @task(
            task_id="extract_fastf1",
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

        extracted = extract_fastf1()
        has_new_data(extracted)

    # -----------------------------------------------------------------------
    # Bronze
    # -----------------------------------------------------------------------

    @task_group(group_id="bronze")
    def bronze_layer() -> None:

        @task(
            task_id="consolidated_results",
            inlets=[RAW_RESULTS],
            outlets=[BRONZE_RESULTS],
        )
        def create_results() -> None:
            consolidate_data("results")

        create_results()

    # -----------------------------------------------------------------------
    # Silver
    # -----------------------------------------------------------------------

    @task_group(group_id="silver")
    def silver_layer() -> None:

        # -------------------------------------------------------------------
        # Silver: Champions
        # -------------------------------------------------------------------

        @task_group(group_id="champions")
        def champions_group() -> None:

            @task(
                task_id="create",
                inlets=[BRONZE_RESULTS],
                outlets=[SILVER_CHAMPIONS],
            )
            def create_champions() -> None:
                build_champions_table()

            create_champions()

        # -------------------------------------------------------------------
        # Silver: Driver statistics
        # -------------------------------------------------------------------

        @task_group(group_id="driver_statistics")
        def driver_statistics_group() -> None:

            @task(inlets=[BRONZE_RESULTS])
            def create_driver_statistic(
                number_of_races: int,
            ) -> None:
                context = get_current_context()
                execution_year = context["data_interval_end"].year

                build_driver_statistic_table(
                    number_of_races=number_of_races,
                    year_stop=execution_year,
                )

            create_driver_statistic.override(
                task_id="create_5_races",
                outlets=[SILVER_DRIVER_STATISTIC_5],
            )(
                number_of_races=5,
            )

            create_driver_statistic.override(
                task_id="create_10_races",
                outlets=[SILVER_DRIVER_STATISTIC_10],
            )(
                number_of_races=10,
            )

            create_driver_statistic.override(
                task_id="create_20_races",
                outlets=[SILVER_DRIVER_STATISTIC_20],
            )(
                number_of_races=20,
            )

            create_driver_statistic.override(
                task_id="create_40_races",
                outlets=[SILVER_DRIVER_STATISTIC_40],
            )(
                number_of_races=40,
            )

            create_driver_statistic.override(
                task_id="create_100_races",
                outlets=[SILVER_DRIVER_STATISTIC_100],
            )(
                number_of_races=100,
            )

        # -------------------------------------------------------------------
        # Silver: Consolidated driver statistics
        # -------------------------------------------------------------------

        @task_group(group_id="driver_all_statistic")
        def driver_all_statistic_group() -> None:

            @task(
                task_id="consolidate",
                inlets=[
                    SILVER_DRIVER_STATISTIC_5,
                    SILVER_DRIVER_STATISTIC_10,
                    SILVER_DRIVER_STATISTIC_20,
                    SILVER_DRIVER_STATISTIC_40,
                    SILVER_DRIVER_STATISTIC_100,
                ],
                outlets=[SILVER_DRIVER_ALL_STATISTIC],
            )
            def consolidate_driver_statistics() -> None:
                build_driver_all_statistic_table()

            consolidate_driver_statistics()

        # -------------------------------------------------------------------
        # Silver: ABT
        # -------------------------------------------------------------------

        @task_group(group_id="abt")
        def abt_group() -> None:

            @task(
                task_id="create",
                inlets=[
                    SILVER_CHAMPIONS,
                    SILVER_DRIVER_ALL_STATISTIC,
                ],
                outlets=[SILVER_TB_ABT],
            )
            def create_abt() -> None:
                build_tb_abt_table()

            create_abt()

        champions = champions_group()
        driver_statistics = driver_statistics_group()
        driver_all_statistic = driver_all_statistic_group()
        abt = abt_group()

        champions 
        driver_statistics >> driver_all_statistic 
        [champions, driver_all_statistic] >> abt
    # -----------------------------------------------------------------------
    # Fluxo principal
    # -----------------------------------------------------------------------

    raw = raw_layer()
    bronze = bronze_layer()
    silver = silver_layer()

    raw >> bronze >> silver


f1_data_pipeline = formula_one_data_pipeline()