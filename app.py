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
    "Portfólio do Fundo": [
        st.Page("pages/Portfolio.py",       title="Portfólio"),
        st.Page("pages/RetornosFundo.py",   title="Retornos do Fundo"),
    ],
    "Peers": [
        st.Page("pages/Peers.py",           title="Análise de Portfolio"),
        st.Page("pages/Retornos.py",        title="Retornos & Risco"),
    ],
}

pg = st.navigation(pages)
pg.run()
