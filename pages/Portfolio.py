"""
Solis — Portfólio do Fundo (FoF Peers Dashboard)
"""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import os

from components.sidebar import load_css
from components.sidebar_fof import render_sidebar_fof
from components.charts import PALETTE
from utils.drive_loader import load_parquet

load_css()

# ─────────────────────────────────────────
# TEMA PLOTLY SOLIS  (derivado do PALETTE de charts.py)
# ─────────────────────────────────────────
_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_CHART = dict(
    template="plotly_dark",
    plot_bgcolor="rgba(0,0,0,0)",
    paper_bgcolor="rgba(0,0,0,0)",
    font=dict(family="Figtree, Inter, sans-serif", color=PALETTE["text"], size=12),
    hoverlabel=dict(
        bgcolor=PALETTE["bg_card"],
        bordercolor=PALETTE["blue"],
        font_color=PALETTE["text_hi"],
    ),
    xaxis=dict(
        showgrid=True, gridcolor=PALETTE["grid"],
        zeroline=False, color=PALETTE["text"],
        tickfont=dict(size=11, color=PALETTE["text"]),
    ),
    yaxis=dict(
        showgrid=True, gridcolor=PALETTE["grid"],
        zeroline=False, color=PALETTE["text"],
        tickfont=dict(size=11, color=PALETTE["text"]),
    ),
)
# Legenda padrão transparente — passada separadamente (Plotly 6)
_LEGEND_DEFAULT = dict(bgcolor="rgba(0,0,0,0)", bordercolor="rgba(0,0,0,0)")

# Escalas de cor contínua
_SCALE = [
    [0.00, PALETTE["bg_card"]],
    [0.40, PALETTE["blue"]],
    [0.75, PALETTE["blue_lt"]],
    [1.00, PALETTE["amber"]],
]
_SCALE_WARM = [
    [0.00, "#78350f"],
    [0.50, PALETTE["orange"]],
    [1.00, PALETTE["amber"]],
]

# Paleta sequencial para gráficos categóricos
_PALETTE = PALETTE["colors"]

GRUPO_COL = "Tipo_Composicao_Ajustado"


def fmt_brl(v, suffix="M"):
    if pd.isna(v):
        return "—"
    d = {"M": 1e6, "B": 1e9, "K": 1e3}.get(suffix, 1)
    s = f"{v/d:,.1f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {s} {suffix}"


def shorten(name: str, max_len: int = 55) -> str:
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
# ─────────────────────────────────────────
# CARREGAMENTO
# ─────────────────────────────────────────
@st.cache_data(show_spinner=False)
def _load():
    detail   = load_parquet("blc_total_detail")
    pivot    = load_parquet("blc_total_pivot")
    check    = load_parquet("check_pl")
    try:
        cadastro = load_parquet("cadastro_fof")
    except Exception:
        cadastro = pd.DataFrame()

    for col in ("PL", "Valor_Presente", "Quantidade_Posicao"):
        if col in detail.columns:
            detail[col] = pd.to_numeric(detail[col], errors="coerce")
    for col in ("PL_Conta", "PL_Est_Cap", "Percentual", "Percentual_Conta_PL_Est_Cap"):
        if col in pivot.columns:
            pivot[col] = pd.to_numeric(pivot[col], errors="coerce")

    return detail, pivot, check, cadastro


with st.spinner("Carregando base de dados…"):
    try:
        df_detail, df_pivot, df_check, df_cadastro = _load()
        dados_ok = True
    except FileNotFoundError as e:
        st.error(str(e))
        dados_ok = False

if not dados_ok:
    st.stop()

# ─────────────────────────────────────────
# SIDEBAR + FILTROS
# ─────────────────────────────────────────
sel = render_sidebar_fof(df_pivot, df_detail)
mes_sel  = sel["mes_sel"]
mes_str  = sel["mes_str"]
fundo_sel = sel["fundo_sel"]

mask_mes   = df_pivot["Data_Posicao"].dt.to_period("M") == mes_sel
mask_fundo = df_pivot["Nome_Fundo_CVM"] == fundo_sel
df_pivot_mes   = df_pivot[mask_mes].copy()
df_pivot_fundo = df_pivot_mes[mask_fundo].copy()

mask_detail_mes   = df_detail["Data_Posicao"].dt.to_period("M") == mes_sel
mask_detail_fundo = df_detail["Nome_Fundo_CVM"] == fundo_sel
df_fundo = df_detail[mask_detail_mes & mask_detail_fundo].copy()

# PL do fundo
pl_est = df_pivot_fundo["PL_Est_Cap"].iloc[0] if not df_pivot_fundo.empty else 0
status_check = df_pivot_fundo["Status_Check_PL"].iloc[0] if "Status_Check_PL" in df_pivot_fundo.columns and not df_pivot_fundo.empty else "N/D"
cnpj_fundo = df_pivot_fundo["ID_CNPJ_Fundo"].iloc[0] if not df_pivot_fundo.empty else "—"

# Atributos ANBIMA do fundo analisado
ATRIBS = [
    ("Gestor",           "Gestor"),
    ("Administrador",    "Administrador"),
    ("Tipo_Anbima",      "Tipo ANBIMA"),
    ("Categoria_1",      "Categoria 1"),
    ("Categoria_2",      "Categoria 2"),
    ("Sub_Categoria",    "Subcategoria"),
    ("Tipo_Investidor",  "Tipo Investidor"),
    ("Alavancado",       "Alavancado"),
    ("Forma_Condominio", "Condomínio"),
    ("Foco_Atuacao",     "Foco Atuação"),
    ("Tipo_conversao",   "Tipo Conversão"),
    ("Prazo_conversao",  "Prazo Conversão"),
    ("Tipo_resgate",     "Tipo Resgate"),
    ("Prazo_resgate",    "Prazo Resgate"),
]

# Busca atributos do pivot (que já contém cadastro ANBIMA do FoF)
if not df_pivot_fundo.empty:
    info_fundo = df_pivot_fundo.iloc[0]
else:
    info_fundo = pd.Series(dtype="object")


# ─────────────────────────────────────────
# HEADER INSTITUCIONAL
# ─────────────────────────────────────────
check_color = "var(--success)" if status_check == "OK" else "var(--danger)" if status_check == "NOK" else "var(--text-secondary)"
st.markdown(f"""
<div class="inst-header">
    <div class="header-text" style="flex:1">
        <h1>Portfólio do Fundo</h1>
        <p>{shorten(fundo_sel, 80)} &nbsp;·&nbsp; CNPJ: {cnpj_fundo} &nbsp;·&nbsp; Mês: {mes_str}</p>
    </div>
    <div style="text-align:right">
        <span style="font-size:0.65rem;text-transform:uppercase;letter-spacing:1px;
                     color:var(--text-muted);">Check PL</span><br>
        <span style="font-size:1.4rem;font-weight:700;color:{check_color};">{status_check}</span>
    </div>
</div>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────
# KPI CARDS (usando classes CSS Solis)
# ─────────────────────────────────────────
total_pl_contas = df_fundo["PL"].sum() if not df_fundo.empty else 0
n_emissores = df_fundo["Nome_Emissor"].nunique()   if not df_fundo.empty else 0

c1, c2, c3, c4 = st.columns(4)
for col, label, val, sub, css_class in [
    (c1, "PL Estimado (CDA)",     fmt_brl(pl_est),             f"Mês: {mes_str}",         "kpi-solis"),
    (c2, "PL Plano de Contas",    fmt_brl(total_pl_contas),    "Soma dos ativos (BLC)",    ""),
    (c3, "Ativos",       f"{len(df_fundo):,}",             f"{len(df_fundo):,} linhas",""),
    (c4, "Emissores Únicos",      f"{n_emissores:,}",          "",                         ""),
]:
    col.markdown(f"""
    <div class="kpi-card {css_class}">
        <div class="kpi-label">{label}</div>
        <div class="kpi-value">{val}</div>
        <div class="kpi-sub">{sub}</div>
    </div>
    """, unsafe_allow_html=True)

st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)

# ─────────────────────────────────────────
# BADGES ANBIMA DO FUNDO ANALISADO
# ─────────────────────────────────────────
badges = ""
for col, label in ATRIBS:
    val = info_fundo.get(col, None)
    if pd.notna(val) and str(val) not in ("nan", "None", ""):
        badges += (
            f"<span style='display:inline-block;margin:3px;padding:4px 12px;"
            f"background:rgba(62,91,125,0.25);border:1px solid rgba(137,155,183,0.2);"
            f"border-radius:20px;font-size:0.68rem;font-family:Figtree,sans-serif;'>"
            f"<span style='color:var(--text-muted);text-transform:uppercase;letter-spacing:0.5px;'>{label}:</span>"
            f"&nbsp;<span style='color:var(--accent-warm);font-weight:600;'>{val}</span></span>"
        )

if badges:
    with st.expander("Características do Fundo (ANBIMA)", expanded=True):
        st.markdown(f"<div style='line-height:2;'>{badges}</div>", unsafe_allow_html=True)

st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)

# ─────────────────────────────────────────
# TABS
# ─────────────────────────────────────────
tab_comp, tab_emissores, tab_historico, tab_carteira = st.tabs([
    "Composição por Tipo",
    "Top Emissores",
    "Evolução Histórica",
    "Carteira Completa",
])

# ── TAB 1: Composição ─────────────────────────────────────────────────────────
with tab_comp:
    if df_fundo.empty:
        st.info("Sem dados para o fundo/mês selecionado.")
    else:
        grupo_col = GRUPO_COL if GRUPO_COL in df_fundo.columns else "Tipo_Composicao"
        agg = (
            df_fundo
            .groupby(grupo_col, as_index=False)
            .agg(PL_Conta=("PL", "sum"), Qtd=("PL", "count"))
        )
        agg["Pct"] = (agg["PL_Conta"] / pl_est).round(4) if pl_est and pl_est > 0 else 0.0
        agg = agg.sort_values("PL_Conta", ascending=False)

        bar_col, donut_col = st.columns([6, 4])

        with bar_col:
            st.markdown('<div class="section-label">Alocação por Tipo (% do PL)</div>', unsafe_allow_html=True)
            agg_sorted = agg.sort_values("Pct")
            fig_bar = px.bar(
                agg_sorted, x="Pct", y=grupo_col, orientation="h",
                color="Pct", color_continuous_scale=_SCALE,
                custom_data=["PL_Conta", "Qtd"],
            )
            fig_bar.update_traces(
                text=agg_sorted["Pct"].apply(lambda x: f"{x*100:.1f}%" if pd.notna(x) else ""),
                textposition="outside", textfont=dict(color=PALETTE["text_light"], size=11),
                marker_line_width=0, cliponaxis=False,
                hovertemplate=(
                    "<b>%{y}</b><br>"
                    "PL: R$ %{customdata[0]:,.2f}<br>"
                    "Linhas: %{customdata[1]}<br>"
                    "% PL: <b>%{x:.1%}</b><extra></extra>"
                )
            )
            _mx = agg_sorted["Pct"].max() if not agg_sorted.empty else 0.1
            fig_bar.update_layout(
                **_CHART,
                legend=_LEGEND_DEFAULT,
                xaxis_tickformat=".0%",
                xaxis_range=[0, _mx * 1.35],
                height=max(300, len(agg) * 36),
                coloraxis_showscale=False,
                margin=dict(l=0, r=80, t=8, b=8),
            )
            fig_bar.update_yaxes(automargin=True)
            st.plotly_chart(fig_bar, use_container_width=True)

        with donut_col:
            st.markdown('<div class="section-label">Distribuição (PL)</div>', unsafe_allow_html=True)
            fig_donut = px.pie(
                agg, values="PL_Conta", names=grupo_col, hole=0.60,
                color_discrete_sequence=_PALETTE,
            )
            fig_donut.update_traces(
                textposition="none",
                hovertemplate="<b>%{label}</b><br>%{percent:.1%}<extra></extra>"
            )
            fig_donut.update_layout(
                **_CHART, height=350,
                margin=dict(l=10, r=10, t=8, b=8),
            )
            fig_donut.update_layout(
                legend=dict(font=dict(size=10, color=PALETTE["text"]), orientation="v",
                            x=1.02, y=0.5, xanchor="left", yanchor="middle"),
            )
            st.plotly_chart(fig_donut, use_container_width=True)

        # Tabela resumo
        tbl = agg.copy()
        tbl["% PL"] = tbl["Pct"].apply(lambda x: f"{x*100:.2f}%" if pd.notna(x) else "—")
        tbl["PL (R$)"] = tbl["PL_Conta"].apply(lambda x: fmt_brl(x, "M"))
        st.dataframe(
            tbl[[grupo_col, "PL (R$)", "% PL", "Qtd"]].rename(columns={grupo_col: "Tipo"}),
            hide_index=True, use_container_width=True
        )

# ── TAB 2: Emissores ──────────────────────────────────────────────────────────
with tab_emissores:
    if df_fundo.empty:
        st.info("Sem dados para o fundo/mês selecionado.")
    else:
        top_n = st.slider("Nº de emissores", 5, 40, 15, key="top_n_em")
        agg_em = (
            df_fundo.groupby("Nome_Emissor", as_index=False)
            .agg(PL_Em=("PL", "sum"))
        )
        if pl_est and pl_est > 0:
            agg_em["Pct"] = (agg_em["PL_Em"] / pl_est).round(4)
        else:
            agg_em["Pct"] = 0.0
        top = agg_em.nlargest(top_n, "PL_Em").copy()
        top["Nome_Curto"] = top["Nome_Emissor"].map(shorten)
        top_s = top.sort_values("Pct")

        fig_em = px.bar(
            top_s, x="Pct", y="Nome_Curto", orientation="h",
            color="Pct", color_continuous_scale=_SCALE,
            custom_data=["PL_Em"],
        )
        fig_em.update_traces(
            text=top_s["Pct"].apply(lambda x: f"{x*100:.2f}%" if pd.notna(x) else ""),
            textposition="outside", textfont=dict(color=PALETTE["text_light"], size=11),
            marker_line_width=0, cliponaxis=False,
            hovertemplate=(
                "<b>%{y}</b><br>"
                "PL: R$ %{customdata[0]:,.2f}<br>"
                "% PL: <b>%{x:.2%}</b><extra></extra>"
            )
        )
        _mx_em = top_s["Pct"].max() if not top_s.empty else 0.1
        fig_em.update_layout(
            **_CHART,
            legend=_LEGEND_DEFAULT,
            xaxis_tickformat=".1%",
            xaxis_range=[0, _mx_em * 1.35],
            height=max(320, top_n * 30),
            coloraxis_showscale=False,
            margin=dict(l=0, r=80, t=8, b=8),
        )
        fig_em.update_yaxes(automargin=True)
        st.plotly_chart(fig_em, use_container_width=True)

# ── TAB 3: Evolução Histórica ─────────────────────────────────────────────────
with tab_historico:
    df_hist = df_detail[df_detail["Nome_Fundo_CVM"] == fundo_sel].copy()
    if df_hist.empty:
        st.info("Sem histórico disponível.")
    else:
        grupo_col_h = GRUPO_COL if GRUPO_COL in df_hist.columns else "Tipo_Composicao"
        # Remover NaT antes de converter — evita AttributeError
        df_hist = df_hist[df_hist["Data_Posicao"].notna()].copy()
        # Formato "Jan/24" — string categórica para Plotly não tratar como data
        MESES_PT = {
            1: "Jan", 2: "Fev", 3: "Mar", 4: "Abr", 5: "Mai", 6: "Jun",
            7: "Jul", 8: "Ago", 9: "Set", 10: "Out", 11: "Nov", 12: "Dez",
        }
        df_hist["Mes"] = df_hist["Data_Posicao"].apply(
            lambda d: f"{MESES_PT[d.month]}/{str(d.year)[2:]}"
        )
        # Cria coluna de ordenação numérica (YYYYMM) para preservar ordem cronológica
        df_hist["_mes_ord"] = df_hist["Data_Posicao"].dt.to_period("M").astype(str)
        ordem_meses = (
            df_hist[["Mes", "_mes_ord"]]
            .drop_duplicates()
            .sort_values("_mes_ord")["Mes"]
            .tolist()
        )
        hist_agg = (
            df_hist.groupby(["Mes", grupo_col_h], as_index=False)
            .agg(PL_Conta=("PL", "sum"))
        )
        # Ordena categoricamente para o Plotly respeitar a ordem cronológica
        hist_agg["Mes"] = pd.Categorical(hist_agg["Mes"], categories=ordem_meses, ordered=True)
        hist_agg = hist_agg.sort_values("Mes")
        fig_hist = px.bar(
            hist_agg, x="Mes", y="PL_Conta", color=grupo_col_h,
            color_discrete_sequence=_PALETTE,
            labels={"PL_Conta": "PL (R$)", "Mes": ""},
            category_orders={"Mes": ordem_meses},
        )
        fig_hist.update_layout(
            **_CHART, barmode="stack", height=400,
            margin=dict(l=0, r=20, t=8, b=40),
            yaxis_tickformat=",.0f",
        )
        fig_hist.update_layout(
            legend=dict(font=dict(size=10, color=PALETTE["text"]),
                        orientation="h", x=0, y=-0.3),
        )
        st.plotly_chart(fig_hist, use_container_width=True)

# ── TAB 4: Carteira Completa ──────────────────────────────────────────────────
with tab_carteira:
    if df_fundo.empty:
        st.info("Sem dados para o fundo/mês selecionado.")
    else:
        COLS = [
            "Tipo_Composicao", GRUPO_COL, "Detalhe_Composicao",
            "Descricao_Ativo", "Nome_Emissor", "CPF_CNPJ_Emissor",
            "Quantidade_Posicao", "Valor_Presente", "PL", "PU_Teorico",
            "Tipo_Negociacao", "Codigo_Selic", "Data_Vencimento",
            "Nome_Fundo_Classe_Investida", "ID_CNPJ_Fundo_Investido",
        ]
        cols_ok = [c for c in COLS if c in df_fundo.columns]
        df_show = df_fundo[cols_ok].copy()

        tipos = sorted(df_show["Tipo_Composicao"].dropna().unique())
        tipo_f = st.multiselect("Filtrar tipo", tipos, default=[], key="tipo_f_cart")
        if tipo_f:
            df_show = df_show[df_show["Tipo_Composicao"].isin(tipo_f)]

        st.caption(f"{len(df_show):,} linhas")

        col_cfg = {c: st.column_config.NumberColumn(c, format="R$ %.4f")
                   for c in ("Valor_Presente", "PL", "PU_Teorico") if c in df_show.columns}
        if "Quantidade_Posicao" in df_show.columns:
            col_cfg["Quantidade_Posicao"] = st.column_config.NumberColumn("Quantidade", format="%.4f")

        st.dataframe(df_show, hide_index=True, use_container_width=True, column_config=col_cfg)

        csv = df_show.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
        st.download_button(
            "Baixar Carteira (.csv)", data=csv,
            file_name=f"carteira_{fundo_sel[:30]}_{mes_str}.csv",
            mime="text/csv",
        )
