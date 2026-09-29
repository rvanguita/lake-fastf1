"""Formatação pt-BR usada em KPIs, tabelas e rótulos de gráficos."""

from __future__ import annotations

import pandas as pd


def _missing(value) -> bool:
    return value is None or (not isinstance(value, str) and pd.isna(value))


def number(value, decimals: int = 0) -> str:
    if _missing(value):
        return "—"
    text = f"{float(value):,.{decimals}f}"
    return text.replace(",", "X").replace(".", ",").replace("X", ".")


def points(value) -> str:
    if _missing(value):
        return "—"
    return number(value, 0 if float(value).is_integer() else 1)


def percent(value, decimals: int = 1) -> str:
    return "—" if _missing(value) else number(float(value) * 100, decimals) + "%"


def day(value) -> str:
    return "—" if _missing(value) else pd.Timestamp(value).strftime("%d/%m/%Y")


def ordinal(value) -> str:
    return "—" if _missing(value) else f"{int(value)}º"
