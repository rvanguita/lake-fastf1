"""Structural test for ``src.spark_session.spark_save_table`` — asserts the
Delta write chain without starting Spark (the DataFrame is a mock)."""

from unittest.mock import MagicMock

from src.spark_session import spark_save_table


def test_spark_save_table_writes_single_file_delta_overwrite():
    df = MagicMock(name="DataFrame")

    spark_save_table("/tmp/x/results", df)

    df.coalesce.assert_called_once_with(1)
    writer = df.coalesce.return_value.write
    writer.format.assert_called_once_with("delta")
    writer.format.return_value.mode.assert_called_once_with("overwrite")
    writer.format.return_value.mode.return_value.save.assert_called_once_with(
        "/tmp/x/results"
    )
