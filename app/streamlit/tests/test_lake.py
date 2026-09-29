import pyarrow as pa
import pytest
from deltalake import write_deltalake

import lake


def test_read_projects_columns_and_filters(lake_root):
    frame = lake.read(
        "silver",
        "mart_driver_round",
        columns=["season", "driver_id"],
        filters=lake.season_filter(2023),
    )
    assert list(frame.columns) == ["season", "driver_id"]
    assert set(frame["season"]) == {2023}


def test_new_version_is_seen_after_ttl(lake_root, monkeypatch):
    clock = [0.0]
    monkeypatch.setattr(lake, "_now", lambda: clock[0])
    first = lake.read("silver", "champions", columns=["Year"])
    write_deltalake(
        lake.table_path("silver", "champions"),
        pa.table({"Year": [2025]}),
        mode="overwrite",
        schema_mode="overwrite",
    )
    clock[0] = 30.0  # mesma janela: versão em cache
    assert lake.read("silver", "champions", columns=["Year"]).equals(first)
    clock[0] = 61.0  # nova janela: lê a versão 1
    assert lake.read("silver", "champions", columns=["Year"])["Year"].tolist() == [2025]
    assert lake.version("silver", "champions") == 1


def test_missing_table_raises_readable_error(lake_root):
    with pytest.raises(lake.LakeUnavailable, match="Tabela Delta indisponível"):
        lake.read("silver", "nao_existe")


def test_catalog_uses_delta_metadata(lake_root):
    tables = lake.delta_tables()
    assert ("bronze", "results") in tables
    assert ("silver", "tb_abt") in tables
    info = lake.table_info("silver", "mart_driver_round")
    assert info["available"] and info["version"] == 0
    assert info["rows"] == 12
    assert info["files"] >= 1
    assert info["operation"]
    assert lake.table_info("silver", "nao_existe") == {
        "layer": "silver",
        "table": "nao_existe",
        "available": False,
    }
    raw = lake.raw_files()
    assert raw["files"] == 1 and raw["latest"] == "2024_01_R.parquet"
