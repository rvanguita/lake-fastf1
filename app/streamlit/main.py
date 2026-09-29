"""Lake FastF1 · Paddock — ponto de entrada do Streamlit."""

import streamlit as st

import lake

st.set_page_config(
    page_title="Lake FastF1 · Paddock",
    page_icon=":material/sports_motorsports:",
    layout="wide",
)

pages = {
    "Análises": [
        st.Page(
            "views/temporada.py",
            title="Temporada",
            icon=":material/leaderboard:",
            default=True,
        ),
        st.Page(
            "views/pilotos.py",
            title="Pilotos",
            icon=":material/person:",
            url_path="pilotos",
        ),
        st.Page(
            "views/previsao.py",
            title="Previsão e modelo",
            icon=":material/insights:",
            url_path="previsao",
        ),
    ],
    "Plataforma": [
        st.Page(
            "views/dados.py",
            title="Dados do lake",
            icon=":material/database:",
            url_path="dados",
        ),
    ],
}
page = st.navigation(pages, position="top")


@st.cache_data(ttl=300, show_spinner=False)
def _seasons(path: str, version: int) -> list[int]:
    del path, version  # chave de cache: outra tabela ou nova versão refazem a lista
    frame = lake.read("silver", "mart_standings", columns=["season"])
    return sorted(frame["season"].astype(int).unique().tolist(), reverse=True)


with st.sidebar:
    st.markdown("### :material/sports_motorsports: Lake FastF1")
    st.caption("Resultados FastF1 → Delta Lake → modelo de campeão")
    try:
        seasons = _seasons(
            lake.table_path("silver", "mart_standings"),
            lake.version("silver", "mart_standings"),
        )
    except lake.LakeUnavailable as exc:
        st.error(str(exc), icon=":material/cloud_off:")
        st.stop()
    # O valor vai para a URL (?ano=), então qualquer visão pode ser compartilhada.
    st.selectbox("Temporada", seasons, key="ano", bind="query-params")
    st.divider()
    st.caption(
        "Pontos somam Race e Sprint. A classificação é reconstruída dos resultados "
        "no lake e não substitui o resultado oficial do campeonato."
    )

page.run()
