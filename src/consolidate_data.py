import argparse
import logging
import os
from collections.abc import Sequence
from pathlib import Path

import dotenv

from src.spark_session import spark_save_table, spark_session

dotenv.load_dotenv()

logger = logging.getLogger(__name__)

PATH_RAW = os.environ["PATH_RAW"]
PATH_BRONZE = os.environ["PATH_BRONZE"]
FORMAT_READ = os.environ.get("FORMAT_READ", "parquet")


def get_latest_modification(path: Path) -> float | None:
    if not path.exists():
        return None

    files = [file for file in path.rglob("*") if file.is_file()]

    if not files:
        return None

    return max(file.stat().st_mtime for file in files)


def has_new_data(source_path: Path, destination_path: Path) -> bool:
    source_modification = get_latest_modification(source_path)
    destination_modification = get_latest_modification(destination_path)

    if source_modification is None:
        logger.info("Nenhum arquivo encontrado em: %s", source_path)
        return False

    if destination_modification is None:
        logger.info(
            "Destino ainda não existe. Consolidação necessária: %s",
            destination_path,
        )
        return True

    updated = source_modification > destination_modification

    logger.info(
        "Verificação de atualização: source=%s destination=%s updated=%s",
        source_path,
        destination_path,
        updated,
    )

    return updated


def consolidate_data(data: str) -> bool:
    source_path = Path(PATH_RAW) / data
    destination_path = Path(PATH_BRONZE) / data

    logger.info(
        "Iniciando consolidação: data=%s source=%s destination=%s format=%s",
        data,
        source_path,
        destination_path,
        FORMAT_READ,
    )

    if not has_new_data(source_path, destination_path):
        logger.info(
            "Nenhum dado novo para consolidar: data=%s",
            data,
        )
        return False

    spark = spark_session()

    try:
        dataframe = (
            spark.read
            .format(FORMAT_READ)
            .load(str(source_path / f"*.{FORMAT_READ}"))
        )

        if dataframe.isEmpty():
            logger.info(
                "DataFrame vazio. Consolidação ignorada: data=%s",
                data,
            )
            return False

        row_count = dataframe.count()

        logger.info(
            "Dados carregados: data=%s rows=%s",
            data,
            row_count,
        )

        spark_save_table(
            str(destination_path),
            dataframe,
        )

        logger.info(
            "Consolidação concluída: data=%s rows=%s destination=%s",
            data,
            row_count,
            destination_path,
        )

        return True

    except Exception:
        logger.exception(
            "Erro durante a consolidação: data=%s",
            data,
        )
        raise


def parse_args(
    argv: Sequence[str] | None = None,
) -> argparse.Namespace:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--data_read",
        default="results",
        help="Diretório de dados dentro de PATH_RAW.",
    )

    return parser.parse_args(argv)


def main(
    argv: Sequence[str] | None = None,
) -> bool:
    args = parse_args(argv)

    updated = consolidate_data(args.data_read)

    logger.info(
        "Processamento finalizado: data=%s updated=%s",
        args.data_read,
        updated,
    )

    return updated


if __name__ == "__main__":
    main()