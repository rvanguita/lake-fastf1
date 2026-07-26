# %%
from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from delta import configure_spark_with_delta_pip

DATA_FORMAT = "delta"
PATH_QUERIES = "src/queries"


def spark_session():
    builder = (SparkSession
               .builder
               .appName("PySpark")
               .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension")
               .config("spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog"))
    return configure_spark_with_delta_pip(builder).getOrCreate()


def spark_view_table(path, table_name):
    spark = spark_session()
    table_view = (spark
                  .read
                  .format(DATA_FORMAT)
                  .load(path)
                  )
    table_view.createOrReplaceTempView(table_name)


def spark_save_table(path, df):
    (df
     .coalesce(1)
     .write
     .format(DATA_FORMAT)
     .mode("overwrite")
     .save(path)
     )


def read_sql_file(query_name):
    with open(f'{PATH_QUERIES}/{query_name}.sql', 'r') as file:
        query = file.read()
    return query
