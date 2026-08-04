import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.append(str(ROOT))

os.environ.setdefault("API_PORT", "5002")
os.environ.setdefault("MLFLOW_URI", "192.168.31.4:5050")
os.environ.setdefault("MLFLOW_MODEL_REGISTERED", "demo-model")

import main


def test_normalize_mlflow_uri_adds_scheme():
    assert main._normalize_mlflow_uri("192.168.31.4:5050") == "http://192.168.31.4:5050"
    assert main._normalize_mlflow_uri("http://192.168.31.4:5050") == "http://192.168.31.4:5050"
