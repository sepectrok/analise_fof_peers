"""
Solis Investimentos — Relatório de Peers FoFs
Main Entry Point
"""

import streamlit as st

st.set_page_config(
    page_title="Solis · Peers FoFs",
    page_icon="SOLIS_BRANDMARK.png",
    layout="wide",
    initial_sidebar_state="expanded",
)

pages = {
    "Análise": [
        st.Page("pages/Portfolio.py",  title="Portfólio do Fundo"),
        st.Page("pages/Peers.py",      title="Análise de Peers"),
    ],
}

pg = st.navigation(pages)
pg.run()
