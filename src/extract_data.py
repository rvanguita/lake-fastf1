import logging
import os
import time
from pathlib import Path
from typing import Any

import fastf1
import pandas as pd

logger = logging.getLogger(__name__)

fastf1.set_log_level(100)


class ExtractData:
    def __init__(
        self,
        years: list[int],
        reload_data: bool,
        identifiers: list[str],
        base_path: str | None = None,
    ) -> None:
        self.years = years
        self.identifiers = identifiers
        self.reload_data = reload_data

        resolved_base_path = base_path or os.environ["PATH_RAW"]
        self.path_save_data = Path(resolved_base_path) / "results"
        self.path_save_data.mkdir(parents=True, exist_ok=True)

        logger.info(
            "Extração inicializada: years=%s identifiers=%s reload_data=%s path=%s",
            self.years,
            self.identifiers,
            self.reload_data,
            self.path_save_data,
        )

    def get_data(
        self,
        year: int,
        gp: int,
        identifier: str,
    ) -> pd.DataFrame:
        logger.info(
            "Carregando sessão: year=%s gp=%s identifier=%s",
            year,
            gp,
            identifier,
        )

        try:
            session = fastf1.get_session(year, gp, identifier)
        except ValueError:
            logger.info(
                "Sessão não encontrada: year=%s gp=%s identifier=%s",
                year,
                gp,
                identifier,
            )
            return pd.DataFrame()

        try:
            session.load()
        except Exception:
            logger.exception(
                "Erro ao carregar sessão: year=%s gp=%s identifier=%s",
                year,
                gp,
                identifier,
            )
            raise

        dataframe = self.prepare_data(session)

        logger.info(
            "Sessão carregada: year=%s gp=%s identifier=%s rows=%s",
            year,
            gp,
            identifier,
            len(dataframe),
        )

        return dataframe

    @staticmethod
    def prepare_data(session: Any) -> pd.DataFrame:
        dataframe = session.results.copy()

        dataframe["Year"] = session.date.year
        dataframe["Date"] = pd.to_datetime(session.date)
        dataframe["Mode"] = session.name
        dataframe["RoundNumber"] = session.event["RoundNumber"]
        dataframe["OfficialEventName"] = session.event["OfficialEventName"]
        dataframe["EventName"] = session.event["EventName"]
        dataframe["Country"] = session.event["Country"]
        dataframe["Location"] = session.event["Location"]

        for column in ("Q1", "Q2", "Q3", "Time"):
            if column in dataframe.columns:
                dataframe[column] = dataframe[column].dt.total_seconds()

        return dataframe

    def process_data(
        self,
        year: int,
        gp: int,
        identifier: str,
    ) -> bool:
        filename = (
            self.path_save_data
            / f"{year}_{gp:02d}_{identifier}.parquet"
        )

        if filename.exists() and not self.reload_data:
            logger.info("Arquivo já existe. Ignorando: %s", filename)
            return False

        dataframe = self.get_data(
            year=year,
            gp=gp,
            identifier=identifier,
        )

        if dataframe.empty:
            logger.info(
                "Nenhum dado disponível: year=%s gp=%s identifier=%s",
                year,
                gp,
                identifier,
            )
            return False

        self.save_data_parquet(dataframe, filename)

        logger.info(
            "Novo dado salvo: file=%s rows=%s",
            filename,
            len(dataframe),
        )

        time.sleep(1)
        return True

    @staticmethod
    def save_data_parquet(
        dataframe: pd.DataFrame,
        filename: Path,
    ) -> None:
        temporary_filename = filename.with_suffix(".tmp.parquet")

        try:
            dataframe.to_parquet(temporary_filename, index=False)
            temporary_filename.replace(filename)
        except Exception:
            temporary_filename.unlink(missing_ok=True)
            logger.exception("Erro ao salvar arquivo: %s", filename)
            raise

    def process_identifiers(
        self,
        year: int,
    ) -> bool:
        added_new_data = False

        for identifier in self.identifiers:
            for gp in range(1, 30):
                was_added = self.process_data(
                    year=year,
                    gp=gp,
                    identifier=identifier,
                )

                added_new_data = added_new_data or was_added

                if not was_added and identifier == "R":
                    logger.info(
                        "Fim das corridas encontrado: year=%s gp=%s",
                        year,
                        gp,
                    )
                    break

        return added_new_data

    def process_years(self) -> bool:
        added_new_data = False

        logger.info("Iniciando extração para %s ano(s)", len(self.years))

        for year in self.years:
            logger.info("Iniciando processamento do ano %s", year)

            year_updated = self.process_identifiers(year)
            added_new_data = added_new_data or year_updated

            logger.info(
                "Processamento do ano finalizado: year=%s updated=%s",
                year,
                year_updated,
            )

            time.sleep(10)

        logger.info(
            "Extração finalizada: updated=%s",
            added_new_data,
        )

        return added_new_data