"""
Solis — Análise de Peers (FoF Peers Dashboard)
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

# Paleta sequencial para gráficos categóricos
_PALETTE = PALETTE["colors"]

GRUPO_COL = "Tipo_Composicao_Ajustado"

# Atributos ANBIMA do FUNDO ANALISADO disponíveis no pivot
ATRIBS_ANALISADO = [
    ("Tipo_Investidor",   "Tipo Investidor"),
    ("Forma_Condominio",  "Condomínio"),
    ("Alavancado",        "Alavancado"),
    ("Tipo_Anbima",       "Tipo ANBIMA"),
    ("Categoria_1",       "Categoria 1"),
    ("Categoria_2",       "Categoria 2"),
    ("Sub_Categoria",     "Subcategoria"),
    ("Foco_Atuacao",      "Foco Atuação"),
    ("Gestor",            "Gestor"),
    ("Administrador",     "Administrador"),
    ("Periodicidade_envio_cota", "Periodicidade Cota"),
    ("Tipo_conversao",    "Tipo Conversão"),
    ("Prazo_conversao",   "Prazo Conversão"),
    ("Tipo_resgate",      "Tipo Resgate"),
    ("Prazo_resgate",     "Prazo Resgate"),
]


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


def fmt_brl(v, suffix="M"):
    if pd.isna(v) or v == 0:
        return "—"
    d = {"M": 1e6, "B": 1e9, "K": 1e3}.get(suffix, 1)
    s = f"{v/d:,.1f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {s} {suffix}"


# ─────────────────────────────────────────
# CARREGAMENTO
# ─────────────────────────────────────────
@st.cache_data(show_spinner=False)
def _load():
    pivot = load_parquet("blc_total_pivot")
    for col in ("PL_Conta", "PL_Est_Cap", "Percentual", "Percentual_Conta_PL_Est_Cap"):
        if col in pivot.columns:
            pivot[col] = pd.to_numeric(pivot[col], errors="coerce")
    return pivot


with st.spinner("Carregando base de dados…"):
    try:
        df_pivot = _load()
        dados_ok = True
    except FileNotFoundError as e:
        st.error(str(e))
        dados_ok = False

if not dados_ok:
    st.stop()

# ─────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────
sel = render_sidebar_fof(df_pivot, df_pivot)
mes_sel  = sel["mes_sel"]
mes_str  = sel["mes_str"]
fundo_alvo = sel["fundo_sel"]

mask_mes = df_pivot["Data_Posicao"].dt.to_period("M") == mes_sel
df_pivot_mes = df_pivot[mask_mes].copy()
df_alvo_rows = df_pivot_mes[df_pivot_mes["Nome_Fundo_CVM"] == fundo_alvo].copy()

cnpj_alvo = df_alvo_rows["ID_CNPJ_Fundo"].iloc[0] if not df_alvo_rows.empty else None
pl_alvo   = df_alvo_rows["PL_Est_Cap"].iloc[0] if not df_alvo_rows.empty else 0

# Atributos do fundo alvo (vêm do pivot que já tem join com cadastro_fof)
alvo_info = df_alvo_rows.iloc[0] if not df_alvo_rows.empty else pd.Series(dtype="object")

# % FIDC do alvo
grupo_col = GRUPO_COL if GRUPO_COL in df_alvo_rows.columns else "Tipo_Composicao"
pct_fidc_alvo = df_alvo_rows.loc[
    df_alvo_rows[grupo_col].str.contains("FIDC", na=False), "Percentual"
].sum()


# ─────────────────────────────────────────
# HEADER
# ─────────────────────────────────────────
st.markdown(f"""
<div class="inst-header">
    <div class="header-text" style="flex:1">
        <h1>Análise de Peers</h1>
        <p>Fundo alvo: <strong>{shorten(fundo_alvo, 70)}</strong> &nbsp;·&nbsp; {mes_str}</p>
    </div>
    <div style="text-align:right">
        <span style="font-size:0.65rem;text-transform:uppercase;letter-spacing:1px;
                     color:var(--text-muted);">% em FIDC</span><br>
        <span style="font-size:1.4rem;font-weight:700;color:var(--accent-warm);">
            {pct_fidc_alvo*100:.1f}%
        </span>
    </div>
</div>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────
# BADGES DO FUNDO ALVO
# ─────────────────────────────────────────
badges = ""
for col, label in ATRIBS_ANALISADO:
    val = alvo_info.get(col, None)
    if pd.notna(val) and str(val) not in ("nan", "None", ""):
        badges += (
            f"<span style='display:inline-block;margin:3px;padding:4px 12px;"
            f"background:rgba(255,195,106,0.08);border:1px solid rgba(255,195,106,0.2);"
            f"border-radius:20px;font-size:0.68rem;font-family:Figtree,sans-serif;'>"
            f"<span style='color:var(--text-muted);text-transform:uppercase;letter-spacing:0.5px;'>{label}:</span>"
            f"&nbsp;<span style='color:var(--accent-warm);font-weight:600;'>{val}</span></span>"
        )

if badges:
    with st.expander("Perfil do Fundo Alvo (ANBIMA)", expanded=True):
        st.markdown(f"<div style='line-height:2;'>{badges}</div>", unsafe_allow_html=True)

st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)


# ─────────────────────────────────────────
# PAINEL DE FILTROS DE SIMILARIDADE
# ─────────────────────────────────────────
st.markdown('<div class="section-label">Critérios de Similaridade</div>', unsafe_allow_html=True)

with st.expander("Configurar filtros", expanded=True):
    fc1, fc2 = st.columns(2)

    with fc1:
        st.markdown("**Atributos categóricos** — selecione os que devem ser iguais ao fundo alvo")
        FILTROS_CATEG_OPTS = [col for col, _ in ATRIBS_ANALISADO
                              if col in df_pivot_mes.columns]
        labels_map = {col: label for col, label in ATRIBS_ANALISADO}
        filtros_cat = st.multiselect(
            "Igualar atributo",
            options=FILTROS_CATEG_OPTS,
            format_func=lambda c: labels_map.get(c, c),
            default=["Tipo_Investidor"] if "Tipo_Investidor" in FILTROS_CATEG_OPTS else [],
            key="peers_categ",
        )

    with fc2:
        st.markdown("**Faixa de alocação em FIDC**")
        faixa_min_pct = st.number_input(
            "% mínima FIDC", 0, 100,
            max(0, int((pct_fidc_alvo - 0.10) * 100)), step=5, key="fidc_min"
        ) / 100
        faixa_max_pct = st.number_input(
            "% máxima FIDC", 0, 200,
            min(200, int((pct_fidc_alvo + 0.10) * 100)), step=5, key="fidc_max"
        ) / 100

        pl_min_m = st.number_input(
            "PL mínimo (R$ Milhões)", 0, 100_000, 0, step=10, key="pl_min"
        ) * 1_000_000

        # Prazo
        prazo_col_ok = "Prazo_conversao" in df_pivot_mes.columns
        _prazo_alvo_raw = alvo_info.get("Prazo_conversao", None) if prazo_col_ok else None
        _sem_info = "Sem Informação Anbima"
        # Só aplica filtro numérico se o alvo tem prazo válido (não é NA nem "Sem Informação Anbima")
        prazo_alvo_valido = (
            prazo_col_ok
            and pd.notna(_prazo_alvo_raw)
            and str(_prazo_alvo_raw) != _sem_info
        )
        prazo_alvo = pd.to_numeric(_prazo_alvo_raw, errors="coerce") or 0 if prazo_alvo_valido else 0
        delta_prazo = st.slider("Tolerância Prazo Conversão (+/- dias)", 0, 90, 30, key="d_prazo")


# ─────────────────────────────────────────
# CALCULAR % FIDC POR FUNDO × MÊS
# ─────────────────────────────────────────
pct_fidc_all = (
    df_pivot_mes[df_pivot_mes[grupo_col].str.contains("FIDC", na=False)]
    .groupby(["ID_CNPJ_Fundo", "Nome_Fundo_CVM"], as_index=False)
    .agg(Pct_FIDC=("Percentual", "sum"), PL_FIDC=("PL_Conta", "sum"))
)

pl_mes = (
    df_pivot_mes
    .drop_duplicates(subset=["ID_CNPJ_Fundo", "Nome_Fundo_CVM"])
    [["ID_CNPJ_Fundo", "Nome_Fundo_CVM", "PL_Est_Cap"] +
     [c for c, _ in ATRIBS_ANALISADO if c in df_pivot_mes.columns]]
)

universo = pct_fidc_all.merge(pl_mes, on=["ID_CNPJ_Fundo", "Nome_Fundo_CVM"], how="left")

# ─────────────────────────────────────────
# APLICAR FILTROS
# ─────────────────────────────────────────
peers = universo[universo["Nome_Fundo_CVM"] != fundo_alvo].copy()

# % FIDC
peers = peers[
    (peers["Pct_FIDC"] >= faixa_min_pct) &
    (peers["Pct_FIDC"] <= faixa_max_pct)
]

# PL mínimo
if pl_min_m > 0:
    peers = peers[peers["PL_Est_Cap"].fillna(0) >= pl_min_m]

# Categóricos
for col in filtros_cat:
    if col in universo.columns:
        val_alvo = alvo_info.get(col, None)
        if pd.notna(val_alvo) and str(val_alvo) not in ("nan", "None", ""):
            peers = peers[peers[col] == val_alvo]

# Prazo
# Só filtra se o fundo alvo tem prazo válido na ANBIMA.
# Peers com "Sem Informação Anbima" passam livremente (não são excluídos).
if prazo_alvo_valido and "Prazo_conversao" in peers.columns:
    _sem_info = "Sem Informação Anbima"
    mask_sem_info = peers["Prazo_conversao"].astype(str) == _sem_info
    prazo_num = pd.to_numeric(peers["Prazo_conversao"], errors="coerce")
    mask_ok = (
        mask_sem_info |  # sem dado ANBIMA: não exclui
        (
            prazo_num.notna() &
            (prazo_num >= prazo_alvo - delta_prazo) &
            (prazo_num <= prazo_alvo + delta_prazo)
        )
    )
    peers = peers[mask_ok]

peers = peers.sort_values("Pct_FIDC", ascending=False).reset_index(drop=True)


# ─────────────────────────────────────────
# RESULTADOS
# ─────────────────────────────────────────
cor_cnt = "var(--success)" if len(peers) > 0 else "var(--danger)"
st.markdown(f"""
<div style="display:flex;align-items:center;gap:16px;margin:12px 0;">
    <span style="font-size:2rem;font-weight:700;color:{cor_cnt};">{len(peers)}</span>
    <span style="color:var(--text-secondary);font-size:0.9rem;">
        peers encontrados com os critérios selecionados
    </span>
</div>
""", unsafe_allow_html=True)

tab_lista, tab_scatter, tab_ranking, tab_comp = st.tabs([
    "Lista de Peers",
    "Dispersão",
    "Ranking FIDC",
    "Comparativo de Carteiras",
])

# ── Lista ─────────────────────────────────────────────────────────────────────
with tab_lista:
    if peers.empty:
        st.warning("Nenhum peer encontrado. Relaxe os filtros de similaridade.")
    else:
        peers["Δ FIDC vs Alvo"] = peers["Pct_FIDC"] - pct_fidc_alvo

        COLS_LISTA = ["Nome_Fundo_CVM", "Pct_FIDC", "Δ FIDC vs Alvo", "PL_Est_Cap", "PL_FIDC"] + \
                     [c for c, _ in ATRIBS_ANALISADO if c in peers.columns]

        tbl = peers[[c for c in COLS_LISTA if c in peers.columns]].copy()
        rename_map = {col: label for col, label in ATRIBS_ANALISADO if col in tbl.columns}
        tbl = tbl.rename(columns=rename_map)

        col_cfg = {
            "Nome_Fundo_CVM":    st.column_config.TextColumn("Fundo"),
            "Pct_FIDC":          st.column_config.NumberColumn("% FIDC",       format="%.1f%%"),
            "Δ FIDC vs Alvo":    st.column_config.NumberColumn("Δ vs Alvo",    format="%+.1f%%"),
            "PL_Est_Cap":        st.column_config.NumberColumn("PL (R$)",      format="R$ %.0f"),
            "PL_FIDC":           st.column_config.NumberColumn("PL FIDC (R$)", format="R$ %.0f"),
        }
        st.dataframe(tbl, hide_index=True, use_container_width=True, column_config=col_cfg)

        csv = tbl.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
        st.download_button(
            "Baixar lista de peers (.csv)", data=csv,
            file_name=f"peers_{fundo_alvo[:30]}_{mes_str}.csv",
            mime="text/csv",
        )

# ── Scatter ───────────────────────────────────────────────────────────────────
with tab_scatter:
    if peers.empty:
        st.info("Sem peers para exibir.")
    else:
        df_sc = peers[["Nome_Fundo_CVM", "Pct_FIDC", "PL_Est_Cap"]].copy()
        df_sc["Grupo"] = "Peer"
        alvo_row = pd.DataFrame([{
            "Nome_Fundo_CVM": fundo_alvo, "Pct_FIDC": pct_fidc_alvo,
            "PL_Est_Cap": pl_alvo, "Grupo": "Alvo"
        }])
        df_sc = pd.concat([df_sc, alvo_row], ignore_index=True)
        df_sc["PL_M"] = df_sc["PL_Est_Cap"].fillna(0) / 1e6
        df_sc["Nome_Curto"] = df_sc["Nome_Fundo_CVM"].map(shorten)

        fig_sc = px.scatter(
            df_sc, x="Pct_FIDC", y="PL_M",
            color="Grupo",
            color_discrete_map={"Alvo": PALETTE["amber"], "Peer": PALETTE["blue"]},
            size="PL_M", size_max=38,
            hover_name="Nome_Curto",
            labels={"Pct_FIDC": "% em FIDC", "PL_M": "PL (R$ M)"},
        )
        fig_sc.update_traces(
            hovertemplate="<b>%{hovertext}</b><br>% FIDC: %{x:.1%}<br>PL: R$ %{y:,.1f}M<extra></extra>",
            selector=dict(mode="markers")
        )
        fig_sc.add_vline(
            x=pct_fidc_alvo, line_dash="dash",
            line_color=PALETTE["amber"], opacity=0.5,
            annotation_text=f"Alvo {pct_fidc_alvo*100:.1f}%",
            annotation_font_color=PALETTE["amber"],
        )
        fig_sc.update_xaxes(tickformat=".0%")
        fig_sc.update_layout(**_CHART, height=480,
                             legend=_LEGEND_DEFAULT,
                             margin=dict(l=0, r=20, t=20, b=10))
        st.plotly_chart(fig_sc, use_container_width=True)

# ── Ranking ───────────────────────────────────────────────────────────────────
with tab_ranking:
    if peers.empty:
        st.info("Sem peers para exibir.")
    else:
        df_rk = peers[["Nome_Fundo_CVM", "Pct_FIDC", "PL_Est_Cap"]].copy()
        alvo_rk = pd.DataFrame([{
            "Nome_Fundo_CVM": fundo_alvo, "Pct_FIDC": pct_fidc_alvo, "PL_Est_Cap": pl_alvo
        }])
        df_rk = pd.concat([df_rk, alvo_rk], ignore_index=True)
        df_rk["Nome_Curto"] = df_rk["Nome_Fundo_CVM"].map(shorten)
        df_rk["Cor"] = df_rk["Nome_Fundo_CVM"].apply(
            lambda n: PALETTE["amber"] if n == fundo_alvo else PALETTE["blue"]
        )
        df_rk = df_rk.sort_values("Pct_FIDC")

        fig_rk = go.Figure()
        fig_rk.add_trace(go.Bar(
            x=df_rk["Pct_FIDC"].tolist(),
            y=df_rk["Nome_Curto"].tolist(),
            orientation="h",
            marker_color=df_rk["Cor"].tolist(),
            text=[f"{x*100:.1f}%" if pd.notna(x) else "" for x in df_rk["Pct_FIDC"]],
            textposition="outside",
            textfont=dict(color=PALETTE["text_light"], size=11),
            customdata=(df_rk["PL_Est_Cap"].fillna(0) / 1e6).tolist(),
            hovertemplate=(
                "<b>%{y}</b><br>% FIDC: <b>%{x:.1%}</b><br>"
                "PL: R$ %{customdata:.1f}M<extra></extra>"
            )
        ))
        _mx_rk = df_rk["Pct_FIDC"].max() if not df_rk.empty else 1.0
        fig_rk.update_layout(
            **_CHART,
            legend=_LEGEND_DEFAULT,
            xaxis_tickformat=".0%",
            xaxis_range=[0, _mx_rk * 1.25],
            height=max(350, len(df_rk) * 28),
            margin=dict(l=0, r=80, t=10, b=10),
        )
        fig_rk.update_yaxes(automargin=True)
        st.plotly_chart(fig_rk, use_container_width=True)

# ── Comparativo de Carteiras ──────────────────────────────────────────────────
with tab_comp:
    if peers.empty:
        st.info("Sem peers para comparar.")
    else:
        nomes_peers = peers["Nome_Fundo_CVM"].tolist()
        peers_sel = st.multiselect(
            "Selecione peers para comparar (máx. 5)",
            options=nomes_peers,
            default=nomes_peers[:min(3, len(nomes_peers))],
            max_selections=5,
            key="peers_comp",
        )

        if peers_sel:
            fundos_comp = [fundo_alvo] + peers_sel
            df_comp = df_pivot_mes[df_pivot_mes["Nome_Fundo_CVM"].isin(fundos_comp)].copy()
            df_comp["Nome_Curto"] = df_comp["Nome_Fundo_CVM"].map(shorten)

            if not df_comp.empty:
                grupo_c = GRUPO_COL if GRUPO_COL in df_comp.columns else "Tipo_Composicao"
                fig_comp = px.bar(
                    df_comp, x="Percentual", y="Nome_Curto",
                    color=grupo_c, barmode="stack",
                    color_discrete_sequence=_PALETTE,
                    labels={"Percentual": "% do PL", "Nome_Curto": ""},
                    custom_data=["PL_Conta"],
                    orientation="h",
                )
                fig_comp.update_traces(
                    hovertemplate=(
                        "<b>%{fullData.name}</b><br>"
                        "% PL: %{x:.1%}<br>PL: R$ %{customdata[0]:,.0f}<extra></extra>"
                    )
                )
                # Detectar escala real de Percentual (0-1 ou 0-100)
                _pct_max = df_comp["Percentual"].max(skipna=True)
                _x_range = [0, 1.05] if (_pct_max is not None and _pct_max <= 1.5) else [0, 105]
                fig_comp.update_xaxes(tickformat=".0%", range=_x_range)
                fig_comp.update_layout(
                    **_CHART, height=max(300, len(fundos_comp) * 50),
                    margin=dict(l=0, r=20, t=10, b=40),
                )
                fig_comp.update_layout(
                    legend=dict(font=dict(size=10, color=PALETTE["text"]),
                                orientation="h", x=0, y=-0.35),
                )
                fig_comp.update_yaxes(automargin=True)
                st.plotly_chart(fig_comp, use_container_width=True)

                pivot_tbl = (
                    df_comp
                    .pivot_table(
                        index=grupo_c, columns="Nome_Curto",
                        values="Percentual", aggfunc="sum", fill_value=0
                    )
                    .mul(100).round(1)
                )
                st.markdown('<div class="section-label">Tabela Comparativa (%)</div>',
                            unsafe_allow_html=True)
                st.dataframe(pivot_tbl, use_container_width=True)
