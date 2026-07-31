# %%

import os
from pathlib import Path

from src.spark_session import spark_session

import pandas as pd
# from deltalake import DeltaTable
from sqlalchemy import create_engine

PATH_BRONZE = os.environ["PATH_BRONZE"]
PATH_SILVER = os.environ["PATH_SILVER"]

spark = spark_session()
# %%
USER = os.getenv("MYSQL_USER")
PASSWORD = os.environ["MYSQL_PASSWORD"]
HOST = os.getenv("MYSQL_HOST")
PORT = os.getenv("MYSQL_PORT")
DATABASE = os.getenv("MYSQL_DATABASE")


# %%
connection_string = f"mysql+pymysql://{USER}:{PASSWORD}@{HOST}:{PORT}/{DATABASE}"
engine = create_engine(connection_string)

# %%


def find_delta_tables(root_path: str | Path) -> list[Path]:
    root_path = Path(root_path)

    return [
        path.parent
        for path in root_path.rglob("_delta_log")
        if path.is_dir()
    ]


def send_layer_to_mysql(
    layer: str,
    root_path: Path,
) -> None:
    delta_tables = find_delta_tables(root_path)

    for delta_path in delta_tables:
        relative_path = delta_path.relative_to(root_path)

        table_name = "_".join(
            [layer, *relative_path.parts]
        ).lower()

        table_name = table_name.replace("-", "_").replace(" ", "_")

        print(f"Enviando {delta_path} para {table_name}")
        df = (
            spark.read
            .format("delta")
            .load(str(delta_path))
            .toPandas()
        )

        df.to_sql(
            name=table_name,           # Name of the SQL table
            con=engine,             # SQLAlchemy engine
            # What to do if table exists ('fail', 'replace', or 'append')
            if_exists="replace",
            index=False             # Do not write the DataFrame index as a column
        )

        print(f"Tabela {table_name} enviada com sucesso")


try:
    send_layer_to_mysql(
        layer="bronze",
        root_path=PATH_BRONZE,
    )

    send_layer_to_mysql(
        layer="silver",
        root_path=PATH_SILVER,
    )

finally:
    spark.stop()
