# %%
import os

from delta import configure_spark_with_delta_pip
from pyspark.sql import SparkSession

PATH_RAW = os.environ["PATH_RAW"]
PATH_BRONZE = os.environ["PATH_BRONZE"]


def spark_session():
    builder = (
        SparkSession.builder.appName("PySpark")
        .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension")
        .config(
            "spark.sql.catalog.spark_catalog",
            "org.apache.spark.sql.delta.catalog.DeltaCatalog",
        )
    )
    return configure_spark_with_delta_pip(builder).getOrCreate()


def spark_save_table(path, df):
    (df.coalesce(1).write.format("delta").mode("overwrite").save(path))


def consolidate_data(data_set: str = "results"):
    spark = spark_session()
    df = spark.read.format("parquet").load(f"{PATH_RAW}/{data_set}/*.parquet")
    spark_save_table(f"{PATH_BRONZE}/{data_set}", df)
    spark.stop()


def main():
    consolidate_data("results")


# %%
if __name__ == "__main__":
    main()

# %%
