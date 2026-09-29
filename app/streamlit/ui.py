"""Blocos de interface compartilhados pelas páginas."""

from __future__ import annotations

from collections.abc import Sequence

import streamlit as st

import charts


def season() -> int:
    """Temporada escolhida na barra lateral (sincronizada com `?ano=`)."""
    return int(st.session_state["ano"])


def header(title: str, eyebrow: str, meta: str | None = None, badge=None) -> None:
    st.caption(eyebrow.upper())
    st.title(title, anchor=False)
    if meta or badge:
        row = st.container(horizontal=True, vertical_alignment="center")
        if badge:
            label, color = badge
            row.badge(label, color=color)
        if meta:
            row.caption(meta)


def kpis(items: Sequence[tuple[str, str, str | None]]) -> None:
    for column, (label, value, note) in zip(st.columns(len(items)), items, strict=True):
        column.metric(
            label,
            value,
            delta=note,
            delta_color="off",
            delta_arrow="off",
            border=True,
        )


def section(title: str, caption: str | None = None) -> None:
    st.subheader(title, anchor=False)
    if caption:
        st.caption(caption)


def plot(figure, key: str | None = None) -> None:
    st.plotly_chart(figure, theme=None, config=charts.CONFIG, key=key)


def unavailable(message: str, *, title: str = "Dados indisponíveis") -> None:
    st.warning(f"**{title}.** {message}", icon=":material/cloud_off:")
