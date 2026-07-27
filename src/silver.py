# %%
import os
import pandas as pd
from datetime import datetime
from functools import reduce

from pyspark.sql import DataFrame
from pyspark.sql import functions as F
from rich.progress import track

from src.spark_session import spark_session, spark_view_table, spark_save_table, read_sql_file

import dotenv

dotenv.load_dotenv()  # Load environment variables from .env file

CURRENT_YEAR = datetime.now().year

JOIN_COLUMNS = ["dt_ref", "DriverId"]

SOURCES = {
    "life":   "driver_statistic_life",
    "last5": "driver_statistic_5",
    "last10": "driver_statistic_10",
    "last20": "driver_statistic_20",
    # "last30": "driver_statistic_30",
    "last40": "driver_statistic_40",
    # "last50": "driver_statistic_50",
}


class SilverData():
    def __init__(self) -> None:
        self.spark = spark_session()
        spark_view_table(f"{os.getenv("PATH_BRONZE")}/results", "results")

    def save_query_table(self, query_name):
        query = read_sql_file(query_name)
        df = self.spark.sql(query)

        spark_save_table(f"{os.getenv("PATH_SILVER")}/{query_name}", df)

    def save_query_csv(self, query_name):
        query = read_sql_file(query_name)
        df = self.spark.sql(query).toPandas()
        df.to_csv(f"{os.getenv("PATH_SILVER")}/{query_name}.csv",
                  index=0,
                  sep=";")

    def sessions_last_n_race(self, query_name, rounds):
        for round in track(rounds, description="Process rounds"):
            self.driver_n_race(query_name, round)

    def driver_n_race(self, query_name, round):
        query = read_sql_file(query_name)
        df = (self.spark
                  .sql(query.format(year_start=1980,
                                    year_stop=CURRENT_YEAR,
                                    last_rounds=round)))
        if round <= 50:
            spark_save_table(
                f"{os.getenv("PATH_SILVER")}/{query_name}_{round}", df)
        else:
            spark_save_table(
                f"{os.getenv("PATH_SILVER")}/{query_name}_life", df)

    def consolidate_drivers_statistic(self, table_name):
        for table in SOURCES.values():
            spark_view_table(
                f"{os.getenv("PATH_SILVER")}/{table}",
                f"{table}"
            )

        dataframes = [
            self.add_suffix(
                dataframe=self.spark.table(table_name),
                suffix=suffix,
                join_columns=JOIN_COLUMNS,
            )
            for suffix, table_name in SOURCES.items()
        ]

        driver_features = reduce(
            lambda left, right: left.join(
                right,
                on=JOIN_COLUMNS,
                how="inner",
            ),
            dataframes,
        )
        spark_save_table(
            f"{os.getenv("PATH_SILVER")}/{table_name}", driver_features)

    def add_suffix(
        self,
        dataframe: DataFrame,
        suffix: str,
        join_columns: list[str],
    ) -> DataFrame:

        metric_columns = [
            F.col(column).alias(f"{column}_{suffix}")
            for column in dataframe.columns
            if column not in join_columns
        ]

        return dataframe.select(
            *[F.col(column) for column in join_columns],
            *metric_columns,
        )


silver_data = SilverData()

# %%data/silver

silver_data.save_query_table("champions")


# %%
query_name = "driver_statistic"
rounds = [5, 10, 20, 40, 100]

# silver_data.sessions_last_n_race(query_name, rounds)
silver_data.driver_n_race(query_name, 5)
silver_data.driver_n_race(query_name, 10)
silver_data.driver_n_race(query_name, 20)
silver_data.driver_n_race(query_name, 40)
silver_data.driver_n_race(query_name, 100)


# %%
champions = "champions"
drivers = "driver_all_statistic"
spark_view_table(f"{os.getenv("PATH_SILVER")}/{champions}", f"{champions}")
spark_view_table(f"{os.getenv("PATH_SILVER")}/{drivers}", f"{drivers}")

silver_data.consolidate_drivers_statistic("driver_all_statistic")

# %%

query_name = "tb_abt"
# silver_data.save_query_csv(query_name)
silver_data.save_query_table(query_name)


# %%
