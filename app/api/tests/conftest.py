"""Pytest config for the FastAPI service tests.

``app/api/main.py`` reads ``API_PORT`` / ``MLFLOW_URI`` / ``MLFLOW_MODEL_REGISTERED``
at import time and lives next to (not under) this package, so both the env vars
and ``sys.path`` are prepared here before ``import main``.
"""

import os
import sys
from pathlib import Path

os.environ.setdefault("API_PORT", "5002")
os.environ.setdefault("MLFLOW_URI", "http://localhost:5050")
os.environ.setdefault("MLFLOW_MODEL_REGISTERED", "f1-champion")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
