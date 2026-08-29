"""Shared pytest configuration for the root (``src/``) test suite.

Every ``src/*.py`` module reads its configuration from ``os.environ[...]`` at
import time and raises ``KeyError`` if a variable is missing.  The assignments
below run when pytest imports this ``conftest`` (before any test module is
collected), so the imports under test succeed without a sourced ``.env``.

``setdefault`` is used throughout so a real environment (``docker compose`` or a
sourced ``.env``) is never overridden.
"""

import os
import tempfile
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
_TMP_LAKE = Path(tempfile.mkdtemp(prefix="lakefastf1-tests-"))

os.environ.setdefault("PATH_RAW", str(_TMP_LAKE / "raw"))
os.environ.setdefault("PATH_BRONZE", str(_TMP_LAKE / "bronze"))
os.environ.setdefault("PATH_SILVER", str(_TMP_LAKE / "silver"))
os.environ.setdefault("PATH_QUERIES", str(_REPO_ROOT / "src" / "queries"))
os.environ.setdefault("FORMAT_READ", "parquet")

os.environ.setdefault("MYSQL_USER", "user")
os.environ.setdefault("MYSQL_PASSWORD", "secret")
os.environ.setdefault("MYSQL_HOST", "localhost")
os.environ.setdefault("MYSQL_PORT", "3306")
os.environ.setdefault("MYSQL_ID_TABLE", "fastf1")


@pytest.fixture
def fake_fastf1_session():
    """Minimal stand-in for a loaded ``fastf1`` session.

    Mirrors the attributes ``ExtractData.prepare_data`` touches: ``results``,
    ``date``, ``name`` and an ``event`` mapping.
    """

    def _make(*, year: int = 2024, mode: str = "Race", round_number: int = 1):
        results = pd.DataFrame(
            {
                "DriverId": ["max", "lando"],
                "Position": [1.0, 2.0],
                "Points": [25.0, 18.0],
                "Q1": pd.to_timedelta(["0:01:20.5", "0:01:21.0"]),
                "Q2": pd.to_timedelta(["0:01:19.5", "0:01:20.0"]),
                "Q3": pd.to_timedelta(["0:01:18.5", "0:01:19.0"]),
                "Time": pd.to_timedelta(["1:30:00", "1:30:05"]),
            }
        )
        event = {
            "RoundNumber": round_number,
            "OfficialEventName": f"FORMULA 1 GRAND PRIX {year}",
            "EventName": "Test Grand Prix",
            "Country": "Testland",
            "Location": "Test City",
        }
        return SimpleNamespace(
            results=results,
            # naive on purpose: prepare_data casts it to datetime64[us]
            date=datetime(year, 3, 10, 15, 0, 0),  # noqa: DTZ001
            name=mode,
            event=event,
        )

    return _make
