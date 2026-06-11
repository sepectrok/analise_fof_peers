"""
sidebar_fof.py — Sidebar customizado para o dashboard de Peers FoF
Reutiliza load_css() e o design system Solis existente.
"""
import streamlit as st
import pandas as pd
import os
import base64
from components.sidebar import load_css, _get_logo_html   # reutiliza CSS e logo

# Nome padrão a pré-selecionar (busca parcial, case-insensitive)
_FUNDO_PADRAO = "SOLIS CAPITAL CORE"


def _shorten(name: str, max_len: int = 60) -> str:
    """Abrevia o nome do fundo para exibição no dropdown."""
    if not isinstance(name, str):
        return str(name)
    s = name.upper()
    for long, short in [
        ("FUNDO DE INVESTIMENTO EM COTAS DE FUNDOS DE INVESTIMENTO", "FIC FI"),
        ("FUNDO DE INVESTIMENTO EM COTAS DE FUNDO DE INVESTIMENTO", "FIC FI"),
        ("FUNDO DE INVESTIMENTO EM COTAS", "FIC"),
        ("FUNDO DE INVESTIMENTO", "FI"),
        ("EM DIREITOS CREDITÓRIOS - RESPONSABILIDADE LIMITADA", "FIDC RL"),
        ("EM DIREITOS CREDITÓRIOS", "FIDC"),
        ("CRÉDITO PRIVADO", "CP"),
        ("MULTIMERCADO", "MM"),
        ("RENDA FIXA", "RF"),
    ]:
        s = s.replace(long.upper(), short)
    return s[:max_len - 3] + "..." if len(s) > max_len else s


def _find_default_index(fundos: list[str], termo: str) -> int:
    """Retorna o índice do fundo que contém `termo` (case-insensitive), ou 0."""
    termo_up = termo.upper()
    for i, f in enumerate(fundos):
        if termo_up in f.upper():
            return i
    return 0


def render_sidebar_fof(df_pivot: pd.DataFrame, df_detail: pd.DataFrame) -> dict:
    """
    Renderiza a sidebar do dashboard FoF.
    Retorna dict com 'mes_sel', 'mes_str', 'fundo_sel'.
    """
    with st.sidebar:
        logo_html = _get_logo_html()
        st.markdown(f"""
        <div class="sidebar-logo">
            {logo_html}
            <div class="logo-sub">Peers FoFs · Análise CVM</div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown(
            '<div class="sidebar-section-title">Seleção</div>',
            unsafe_allow_html=True,
        )

        # ── Mês ────────────────────────────────────────────────────────────
        meses = sorted(
            df_pivot["Data_Posicao"].dropna().dt.to_period("M").unique(),
            reverse=True
        )
        mes_options = [str(m) for m in meses]
        mes_str = st.selectbox("Mês de Posição", mes_options, key="fof_mes")

        # ── Fundo — selectbox único com busca nativa ────────────────────────
        # O Streamlit exibe os nomes abreviados (format_func) mas retorna o
        # valor original da lista. O usuário pode digitar livremente dentro
        # do selectbox para filtrar — sem precisar apagar caractere a caractere.
        mes_sel = pd.Period(mes_str, freq="M")
        mask = df_pivot["Data_Posicao"].dt.to_period("M") == mes_sel
        fundos = sorted(
            df_pivot.loc[mask, "Nome_Fundo_CVM"].dropna().unique().tolist()
        )

        # Índice padrão: Solis Capital Core (ou 0 se não encontrar)
        idx_padrao = _find_default_index(fundos, _FUNDO_PADRAO)

        fundo_str = st.selectbox(
            "Fundo",
            options=fundos,
            index=idx_padrao,
            format_func=_shorten,
            key="fof_fundo",
        )

        # ── Stats dinâmicos ────────────────────────────────────────────────
        n_fundos  = df_pivot.loc[mask, "ID_CNPJ_Fundo"].nunique()
        n_meses   = df_pivot["Data_Posicao"].dt.to_period("M").nunique()

        st.markdown("---")
        st.markdown(f"""
        <div class="sidebar-stats">
            <div class="sidebar-stat">
                <span class="stat-value">{n_fundos}</span>
                <span class="stat-label">Fundos</span>
            </div>
            <div class="sidebar-stat">
                <span class="stat-value">{n_meses}</span>
                <span class="stat-label">Meses</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("---")
        st.markdown("""
        <div style="font-size:0.6rem; color:var(--text-muted); text-align:center;
                    letter-spacing:0.5px; line-height:1.6;">
            Fonte: CVM · ANBIMA<br>
            <span style="opacity:0.6;">© Solis Investimentos</span>
        </div>
        """, unsafe_allow_html=True)

    return {"mes_str": mes_str, "mes_sel": mes_sel, "fundo_sel": fundo_str}
