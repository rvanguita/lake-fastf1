# %%
import argparse
from src.spark_session import spark_session, spark_save_table

PATH_RAW = "data/raw"
PATH_BRONZE = "data/bronze"
FORMAT_READ = "parquet"


def consolidate_data(data):
    spark = spark_session()
    df = (spark
          .read
          .format(FORMAT_READ)
          .load(f"{PATH_RAW}/{data}/*.{FORMAT_READ}")
          )
    spark_save_table(f"{PATH_BRONZE}/{data}", df)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data_read", default="results")

    args, _ = parser.parse_known_args()

    consolidate_data(args.data_read)


# %%
if __name__ == "__main__":
    main()

# %%
