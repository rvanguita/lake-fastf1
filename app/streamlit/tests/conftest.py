"""Pytest config for the Streamlit dashboard tests.

``app/streamlit/main.py`` reads ``API_PORT`` / ``TABLE_PATH_SILVER`` /
``TABLE_PATH_BRONZE`` at import time into module constants (the cached data
loaders that would actually use the paths are never called from these tests).
"""

import os
import sys
from pathlib import Path

os.environ.setdefault("API_PORT", "5002")
os.environ.setdefault("TABLE_PATH_SILVER", "/data/silver/tb_abt")
os.environ.setdefault("TABLE_PATH_BRONZE", "/data/bronze/results")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
