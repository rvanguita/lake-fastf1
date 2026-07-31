import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.engine import URL

from src.spark_session import spark_session


USER = os.environ["MYSQL_USER"]
PASSWORD = os.environ["MYSQL_PASSWORD"]
HOST = os.environ["MYSQL_HOST"]
PORT = int(os.getenv("MYSQL_PORT", "3306"))
ID_TABLE = os.getenv("MYSQL_ID_TABLE", "")


def find_delta_tables(root_path: str | Path) -> list[Path]:
    root_path = Path(root_path)

    return [
        path.parent
        for path in root_path.rglob("_delta_log")
        if path.is_dir()
    ]


def create_mysql_engine(database: str):
    url = URL.create(
        drivername="mysql+pymysql",
        username=USER,
        password=PASSWORD,
        host=HOST,
        port=PORT,
        database=database,
    )

    return create_engine(
        url,
        pool_pre_ping=True,
        pool_recycle=3600,
    )


def send_layer_to_mysql(
    layer: str,
    root_path: str | Path,
) -> None:
    spark = spark_session()
    engine = create_mysql_engine(layer)

    try:
        for delta_path in find_delta_tables(root_path):
            relative_path = delta_path.relative_to(Path(root_path))
            table_suffix = "_".join(relative_path.parts)

            table_name = (
                f"{ID_TABLE}_{table_suffix}"
                if ID_TABLE
                else table_suffix
            )

            dataframe = (
                spark.read
                .format("delta")
                .load(str(delta_path))
                .toPandas()
            )

            dataframe.to_sql(
                name=table_name,
                con=engine,
                if_exists="replace",
                index=False,
                chunksize=1_000,
                method="multi",
            )
    finally:
        engine.dispose()
        spark.stop()