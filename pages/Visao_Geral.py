"""
Solis Investimentos — Benchmarking Institucional
Visão Geral — Design System v3.0
"""

import streamlit as st
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from components.sidebar import load_css, render_sidebar, apply_sidebar_filters
from components.metrics_cards import institutional_header, render_executive_kpis, render_general_kpis
from components.charts import bar_foco_comparativo, bar_ranking, boxplot_solis_vs_mercado, donut_market_share_solis
from utils.data_loader import build_df_fidc, TAXA_LABELS, TAXA_COLS

# ─── CSS ──────────────────────────────────────────────────────────────────────
load_css()

# ─── Data ─────────────────────────────────────────────────────────────────────
with st.spinner("Carregando base de dados…"):
    df_full = build_df_fidc()

# ─── Sidebar ──────────────────────────────────────────────────────────────────
filters = render_sidebar(df_full)
df = apply_sidebar_filters(df_full, filters)

# ─── Divisão Solis vs Mercado ─────────────────────────────────────────────────
is_solis  = df['gestor'].str.contains('Solis', case=False, na=False)
df_solis  = df[is_solis]
df_mercado = df[~is_solis]

# ─── Institutional Header ─────────────────────────────────────────────────────
institutional_header(
    "Benchmarking Institucional",
    f"Análise comparativa · {len(df)} fundos · Mercado vs Solis Investimentos"
)

# ═══════════════════════════════════════════════════════════════════════════════
# SEÇÃO ESCURA — Posicionamento Solis
# ═══════════════════════════════════════════════════════════════════════════════
st.markdown('<div class="section-label">Posicionamento Solis</div>', unsafe_allow_html=True)
render_executive_kpis(df_solis, df_mercado)

st.markdown("<div style='height:32px'></div>", unsafe_allow_html=True)
st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════════════════
# SEÇÃO CLARA — Visão Geral do Mercado (alternância fundo claro)
# ═══════════════════════════════════════════════════════════════════════════════
st.markdown("""
    <div class="section-label" style="color:var(--accent-primary) !important;">
        Visão Geral do Mercado
    </div>
""", unsafe_allow_html=True)

render_general_kpis(df)


st.markdown("<div style='height:32px'></div>", unsafe_allow_html=True)
st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════════════════
# SEÇÃO ESCURA — Market Share & Segmentos
# ═══════════════════════════════════════════════════════════════════════════════
st.markdown('<div class="section-label">Market Share &amp; Segmentos</div>', unsafe_allow_html=True)
st.plotly_chart(donut_market_share_solis(df_solis, df_mercado, height=450), use_container_width=True)

st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
st.plotly_chart(bar_foco_comparativo(df_solis, df_mercado, height=450), use_container_width=True)

st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════════════════
# SEÇÃO CLARA — Distribuição de Taxas (alternância fundo claro)
# ═══════════════════════════════════════════════════════════════════════════════
st.markdown("""
    <div class="section-label" style="color:var(--accent-primary) !important;">
        Distribuição — Taxa de Gestão (Solis vs Mercado)
    </div>
""", unsafe_allow_html=True)

if "taxa_gestao" in df.columns:
    st.plotly_chart(
        boxplot_solis_vs_mercado(df_solis, df_mercado, "taxa_gestao", height=420),
        use_container_width=True,
    )
else:
    st.info("Sem dados de Taxa de Gestão")

st.markdown("<div style='height:32px'></div>", unsafe_allow_html=True)
st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════════════════
# SEÇÃO ESCURA — Rankings
# ═══════════════════════════════════════════════════════════════════════════════
st.markdown('<div class="section-label">Rankings</div>', unsafe_allow_html=True)

st.markdown("#### Gestores por Nº de Fundos")
ges_count = (
    df.dropna(subset=["gestor"])
    .groupby("gestor")
    .size()
    .reset_index(name="n_fundos")
)
st.plotly_chart(
    bar_ranking(
        ges_count.rename(columns={"n_fundos": "_val", "gestor": "_name"}),
        "_val", "_name", title="",
        top_n=15, height=420, is_percent=False, highlight_name="Solis",
    ),
    use_container_width=True,
)

st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)

st.markdown("#### Administradores por Nº de Fundos")
adm_count = (
    df.dropna(subset=["administrador"])
    .groupby("administrador")
    .size()
    .reset_index(name="n_fundos")
)
st.plotly_chart(
    bar_ranking(
        adm_count.rename(columns={"n_fundos": "_val", "administrador": "_name"}),
        "_val", "_name", title="",
        top_n=15, height=420, is_percent=False, highlight_name="Solis",
    ),
    use_container_width=True,
)

st.markdown("<div style='height:32px'></div>", unsafe_allow_html=True)
st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════════════════
# SEÇÃO CLARA — Ranking por Taxa Média (alternância)
# ═══════════════════════════════════════════════════════════════════════════════
st.markdown("""
    <div class="section-label" style="color:var(--accent-primary) !important;">
        Ranking por Taxa Média
    </div>
""", unsafe_allow_html=True)

entidade_opt = st.radio(
    "Visão:",
    ["Administradores (Taxa de Administração)", "Gestores (Taxa de Gestão)"],
    horizontal=True, label_visibility="collapsed",
)

if "Administradores" in entidade_opt:
    ent_col = "administrador"
    tax_col = "taxa_administracao"
    title   = "Taxa de Administração Média"
else:
    ent_col = "gestor"
    tax_col = "taxa_gestao"
    title   = "Taxa de Gestão Média"

df_ent = df.dropna(subset=[ent_col, tax_col])
if not df_ent.empty:
    df_agg = (
        df_ent.groupby(ent_col)
        .agg({tax_col: "mean"})
        .reset_index()
    )

    col1, col2 = st.columns([1, 4])
    with col1:
        top_n = st.slider("Entidades", 5, 50, 15, key="app_ent_topn")

    df_bar = df_agg.copy()
    df_bar["_name"] = df_bar[ent_col].str[:40]

    fig = bar_ranking(
        df_bar.rename(columns={tax_col: "_val"}),
        "_val", "_name", title=title,
        top_n=top_n, highlight_name="Solis",
    )
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info(f"Nenhum dado encontrado para {tax_col}.")

st.markdown("<div style='height:32px'></div>", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════════════════
# FOOTER ANIMADO — fiel ao site solisinvestimentos.com.br
# ═══════════════════════════════════════════════════════════════════════════════
st.markdown("""
<div class="solis-footer">
    <div class="footer-content">
        <div class="footer-logo-text">SOLIS INVESTIMENTOS</div>
        <div class="footer-divider"></div>
        <div class="footer-line">Plataforma de Inteligência Competitiva · FIDCs</div>
        <div class="footer-line" style="opacity:0.55; font-size:0.65rem;">
            Fonte: Regulamentos CVM / FNET · Uso interno · Não constitui recomendação de investimento
        </div>
    </div>
</div>
""", unsafe_allow_html=True)
