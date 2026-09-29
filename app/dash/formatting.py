"""Formatação pt-BR compartilhada pelos achados, tabelas e gráficos."""

from __future__ import annotations

import math

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


def percent(value, decimals: int = 0) -> str:
    return "—" if _missing(value) else number(float(value) * 100, decimals) + "%"


def seconds(value) -> str:
    if _missing(value):
        return "—"
    # Chegadas apertadas precisam de milésimos; o resto fica legível com décimos.
    return number(value, 3 if value < 1 else 1) + " s"


def race_time(value) -> str:
    """Tempo total do vencedor em h:mm:ss."""
    if _missing(value) or value <= 0:
        return "—"
    total = math.floor(float(value))
    hours, rest = divmod(total, 3600)
    minutes, secs = divmod(rest, 60)
    return f"{hours}:{minutes:02d}:{secs:02d}" if hours else f"{minutes}:{secs:02d}"


def day(value) -> str:
    return "—" if _missing(value) else pd.Timestamp(value).strftime("%d/%m/%Y")


def plural(count: int, singular: str, many: str | None = None) -> str:
    return f"{count} {singular if count == 1 else many or singular + 's'}"
