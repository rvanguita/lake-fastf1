import logging
import os
from datetime import datetime
from functools import reduce
from pathlib import Path

import dotenv
from pyspark.sql import DataFrame
from pyspark.sql import functions as F

from src.spark_session import (
    read_sql_file,
    spark_save_table,
    spark_session,
    spark_view_table,
)

dotenv.load_dotenv()

logger = logging.getLogger(__name__)

CURRENT_YEAR = datetime.now().year

JOIN_COLUMNS = ["dt_ref", "DriverId"]

SOURCES = {
    "life": "driver_statistic_life",
    "last5": "driver_statistic_5",
    "last10": "driver_statistic_10",
    "last20": "driver_statistic_20",
    "last40": "driver_statistic_40",
}


class SilverData:
    def __init__(self) -> None:
        self.path_bronze = Path(os.environ["PATH_BRONZE"])
        self.path_silver = Path(os.environ["PATH_SILVER"])
        self.spark = spark_session()

        logger.info(
            "Inicializando camada Silver: bronze=%s silver=%s",
            self.path_bronze,
            self.path_silver,
        )

        self._register_table(
            path=self.path_bronze / "results",
            table_name="results",
        )

    def save_query_table(self, query_name: str) -> None:
        destination = self.path_silver / query_name

        logger.info(
            "Executando query: query=%s destination=%s",
            query_name,
            destination,
        )

        try:
            query = read_sql_file(query_name)
            dataframe = self.spark.sql(query)

            spark_save_table(
                str(destination),
                dataframe,
            )

            logger.info(
                "Tabela salva: table=%s destination=%s",
                query_name,
                destination,
            )
        except Exception:
            logger.exception(
                "Erro ao criar tabela: table=%s",
                query_name,
            )
            raise

    def save_query_csv(self, query_name: str) -> None:
        destination = self.path_silver / f"{query_name}.csv"

        logger.info(
            "Gerando CSV: query=%s destination=%s",
            query_name,
            destination,
        )

        try:
            query = read_sql_file(query_name)
            dataframe = self.spark.sql(query).toPandas()

            dataframe.to_csv(
                destination,
                index=False,
                sep=";",
            )

            logger.info(
                "CSV salvo: query=%s destination=%s rows=%s",
                query_name,
                destination,
                len(dataframe),
            )
        except Exception:
            logger.exception(
                "Erro ao gerar CSV: query=%s",
                query_name,
            )
            raise

    def driver_n_race(
        self,
        query_name: str,
        number_of_races: int,
        year_stop: int = CURRENT_YEAR,
    ) -> None:
        suffix = (
            str(number_of_races)
            if number_of_races <= 50
            else "life"
        )

        table_name = f"{query_name}_{suffix}"
        destination = self.path_silver / table_name

        logger.info(
            "Criando estatística de pilotos: "
            "query=%s races=%s year_stop=%s destination=%s",
            query_name,
            number_of_races,
            year_stop,
            destination,
        )

        try:
            query = read_sql_file(query_name)

            dataframe = self.spark.sql(
                query.format(
                    year_start=1980,
                    year_stop=year_stop,
                    last_rounds=number_of_races,
                )
            )

            spark_save_table(
                str(destination),
                dataframe,
            )

            logger.info(
                "Estatística salva: table=%s races=%s",
                table_name,
                number_of_races,
            )
        except Exception:
            logger.exception(
                "Erro ao criar estatística: "
                "table=%s races=%s",
                table_name,
                number_of_races,
            )
            raise

    def consolidate_drivers_statistic(
        self,
        destination_table: str,
    ) -> None:
        destination = self.path_silver / destination_table

        logger.info(
            "Iniciando consolidação das estatísticas: destination=%s",
            destination,
        )

        try:
            for source_table in SOURCES.values():
                self._register_table(
                    path=self.path_silver / source_table,
                    table_name=source_table,
                )

            dataframes = [
                self.add_suffix(
                    dataframe=self.spark.table(source_table),
                    suffix=suffix,
                    join_columns=JOIN_COLUMNS,
                )
                for suffix, source_table in SOURCES.items()
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
                str(destination),
                driver_features,
            )

            logger.info(
                "Estatísticas consolidadas: table=%s sources=%s",
                destination_table,
                list(SOURCES.values()),
            )
        except Exception:
            logger.exception(
                "Erro ao consolidar estatísticas: table=%s",
                destination_table,
            )
            raise

    @staticmethod
    def add_suffix(
        dataframe: DataFrame,
        suffix: str,
        join_columns: list[str],
    ) -> DataFrame:
        missing_columns = set(join_columns) - set(dataframe.columns)

        if missing_columns:
            raise ValueError(
                "Colunas obrigatórias ausentes: "
                f"{sorted(missing_columns)}"
            )

        metric_columns = [
            F.col(column).alias(f"{column}_{suffix}")
            for column in dataframe.columns
            if column not in join_columns
        ]

        return dataframe.select(
            *[F.col(column) for column in join_columns],
            *metric_columns,
        )

    @staticmethod
    def _log_table_registration(
        table_name: str,
        path: Path,
    ) -> None:
        logger.info(
            "Registrando tabela temporária: table=%s path=%s",
            table_name,
            path,
        )

    def _register_table(
        self,
        path: Path,
        table_name: str,
    ) -> None:
        self._log_table_registration(table_name, path)

        try:
            spark_view_table(
                str(path),
                table_name,
            )
        except Exception:
            logger.exception(
                "Erro ao registrar tabela: table=%s path=%s",
                table_name,
                path,
            )
            raise


def main(year_stop: int | None = None) -> None:
    processing_year = year_stop or CURRENT_YEAR

    logger.info(
        "Iniciando processamento Silver: year_stop=%s",
        processing_year,
    )

    silver_data = SilverData()

    silver_data.save_query_table("champions")

    for number_of_races in (5, 10, 20, 40, 100):
        silver_data.driver_n_race(
            query_name="driver_statistic",
            number_of_races=number_of_races,
            year_stop=processing_year,
        )

    silver_data.consolidate_drivers_statistic(
        destination_table="driver_all_statistic",
    )

    silver_data._register_table(
        path=silver_data.path_silver / "champions",
        table_name="champions",
    )

    silver_data._register_table(
        path=silver_data.path_silver / "driver_all_statistic",
        table_name="driver_all_statistic",
    )

    silver_data.save_query_table("tb_abt")

    logger.info(
        "Processamento Silver concluído: year_stop=%s",
        processing_year,
    )