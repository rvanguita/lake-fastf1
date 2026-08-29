"""Tests for the pure helpers in ``src.sender_local`` — no Spark, no MySQL."""

from src.sender_local import (
    HOST,
    PORT,
    USER,
    create_mysql_engine,
    find_delta_tables,
)


class TestFindDeltaTables:
    def test_finds_nested_delta_logs(self, tmp_path):
        (tmp_path / "bronze" / "results" / "_delta_log").mkdir(parents=True)
        (tmp_path / "silver" / "champions" / "_delta_log").mkdir(parents=True)
        (tmp_path / "silver" / "not_a_table").mkdir(parents=True)

        found = {p.name for p in find_delta_tables(tmp_path)}
        assert found == {"results", "champions"}

    def test_empty_directory_returns_empty_list(self, tmp_path):
        assert find_delta_tables(tmp_path) == []

    def test_ignores_delta_log_that_is_a_file(self, tmp_path):
        (tmp_path / "table").mkdir()
        (tmp_path / "table" / "_delta_log").write_text("")  # a file, not a dir
        assert find_delta_tables(tmp_path) == []

    def test_accepts_str_path(self, tmp_path):
        (tmp_path / "t" / "_delta_log").mkdir(parents=True)
        assert [p.name for p in find_delta_tables(str(tmp_path))] == ["t"]


class TestCreateMysqlEngine:
    def test_builds_pymysql_url_without_connecting(self):
        engine = create_mysql_engine("bronze")
        url = engine.url
        assert url.drivername == "mysql+pymysql"
        assert url.database == "bronze"
        assert url.host == HOST
        assert url.username == USER
        assert url.port == PORT
