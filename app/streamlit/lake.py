"""Leitura somente leitura das tabelas Delta do lake, com cache por versão."""

from __future__ import annotations

import os
import time
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import pyarrow as pa
import streamlit as st
from deltalake import DeltaTable
from deltalake.exceptions import DeltaError

_HERE = Path(__file__).resolve()
# Repositório local: a pasta que contém o docker-compose.yml; no container, /data.
_REPO = next(
    (p for p in _HERE.parents if (p / "docker-compose.yml").is_file()), _HERE.parent
)
VERSION_TTL = 60


class LakeUnavailable(RuntimeError):
    """Tabela ausente ou ilegível; a página mostra a mensagem em vez de quebrar."""


def lake_root() -> Path:
    return Path(os.getenv("LAKE_ROOT") or _REPO / "data")


def table_path(layer: str, name: str) -> str:
    return str(lake_root() / layer / name)


def _now() -> float:
    return time.time()


def version(layer: str, name: str) -> int:
    return _version(table_path(layer, name), int(_now() // VERSION_TTL))


@st.cache_data(ttl=VERSION_TTL * 2, show_spinner=False)
def _version(path: str, bucket: int) -> int:
    del bucket  # só separa janelas de checagem
    try:
        return DeltaTable(path).version()
    except (DeltaError, OSError) as exc:
        raise LakeUnavailable(
            f"Tabela Delta indisponível em {path}. Execute o pipeline ou confira LAKE_ROOT."
        ) from exc


@st.cache_data(max_entries=64, show_spinner=False)
def _read(
    path: str, version: int, columns: tuple | None, filters: tuple
) -> pd.DataFrame:
    try:
        table = DeltaTable(path, version=version)
        return table.to_pandas(
            columns=list(columns) if columns else None, filters=list(filters) or None
        )
    except (DeltaError, OSError, ValueError) as exc:
        raise LakeUnavailable(f"Não foi possível ler {path}: {exc}") from exc


def read(
    layer: str, name: str, columns: list[str] | None = None, filters: tuple = ()
) -> pd.DataFrame:
    """Lê só as colunas e partições pedidas; a chave de cache inclui a versão Delta."""
    path = table_path(layer, name)
    return _read(
        path,
        _version(path, int(_now() // VERSION_TTL)),
        tuple(columns) if columns else None,
        tuple(filters),
    )


def season_filter(season: int, column: str = "season") -> tuple:
    return ((column, "=", int(season)),)


# ------------------------------------------------------------------ catálogo


def table_info(layer: str, name: str) -> dict:
    """Metadados Delta (sem ler os dados): versão, linhas, arquivos, última escrita."""
    path = table_path(layer, name)
    try:
        table = DeltaTable(path)
    except (DeltaError, OSError):
        return {"layer": layer, "table": name, "available": False}
    actions = pa.table(table.get_add_actions(flatten=True))
    last = table.history(1)[0]
    records = actions.column("num_records").to_pylist() if actions.num_rows else []
    return {
        "layer": layer,
        "table": name,
        "available": True,
        "version": table.version(),
        "rows": int(sum(value or 0 for value in records)),
        "files": actions.num_rows,
        "size_mb": sum(actions.column("size_bytes").to_pylist()) / 1_048_576
        if actions.num_rows
        else 0.0,
        "columns": len(table.schema().fields),
        "last_write": datetime.fromtimestamp(last["timestamp"] / 1000, tz=UTC),
        "operation": last.get("operation", ""),
    }


def delta_tables() -> list[tuple[str, str]]:
    """Todas as tabelas Delta de Bronze e Silver presentes no lake."""
    found = []
    for layer in ("bronze", "silver"):
        base = lake_root() / layer
        if not base.is_dir():
            continue
        for child in sorted(base.iterdir()):
            if (child / "_delta_log").is_dir():
                found.append((layer, child.name))
    return found


def raw_files() -> dict:
    files = sorted((lake_root() / "raw" / "results").glob("*.parquet"))
    if not files:
        return {"files": 0, "latest": None, "size_mb": 0.0}
    newest = max(files, key=lambda file: file.stat().st_mtime)
    return {
        "files": len(files),
        "latest": newest.name,
        "size_mb": sum(file.stat().st_size for file in files) / 1_048_576,
        "last_write": datetime.fromtimestamp(newest.stat().st_mtime, tz=UTC),
    }
