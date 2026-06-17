"""
Solis — Retornos & Risco (FoF Peers Dashboard)
Página de análise de retornos e risco com base em dados ANBIMA.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import streamlit as st

from components.sidebar import load_css
from components.charts import PALETTE, _base_layout
from utils.drive_loader import load_parquet
from utils.returns_calc import (
    calcular_retorno_diario,
    calcular_acumulados,
    calcular_retorno_mensal,
    calcular_cota_indexada,
    calcular_metricas_risco,
)

load_css()

# ─────────────────────────────────────────────────────────────────────────────
# CONSTANTES DE LAYOUT
# ─────────────────────────────────────────────────────────────────────────────
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
_LEGEND = dict(bgcolor="rgba(0,0,0,0)", bordercolor="rgba(0,0,0,0)")

# Cores para séries: fundo alvo sempre dourado, peers em azul/cinza
_COR_ALVO = PALETTE["amber"]
_COR_CDI  = "rgba(137,155,183,0.6)"
_CORES_PEERS = [
    PALETTE["blue"],
    PALETTE["orange"],
    PALETTE["green"],
    PALETTE["blue_lt"],
    "#9B59B6",
    "#1ABC9C",
]


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def shorten(name: str, max_len: int = 50) -> str:
    if not isinstance(name, str):
        return str(name)
    s = name.upper()
    for long, short in [
        ("FUNDO DE INVESTIMENTO EM COTAS DE FUNDOS DE INVESTIMENTO", "FIC FI"),
        ("FUNDO DE INVESTIMENTO EM COTAS DE FUNDO DE INVESTIMENTO",  "FIC FI"),
        ("FUNDO DE INVESTIMENTO EM COTAS", "FIC"),
        ("FUNDO DE INVESTIMENTO",          "FI"),
        ("EM DIREITOS CREDITÓRIOS - RESPONSABILIDADE LIMITADA", "FIDC RL"),
        ("EM DIREITOS CREDITÓRIOS", "FIDC"),
        ("CRÉDITO PRIVADO", "CP"),
        ("MULTIMERCADO",    "MM"),
        ("RENDA FIXA",      "RF"),
    ]:
        s = s.replace(long.upper(), short)
    return s[: max_len - 3] + "..." if len(s) > max_len else s


def fmt_pct(v, digits=2):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "—"
    return f"{v * 100:+.{digits}f}%"


def fmt_pct_pos(v, digits=2):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "—"
    return f"{v * 100:.{digits}f}%"


def fmt_x(v, digits=2):
    """Formata como múltiplo do CDI (ex: 1,23×)."""
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "—"
    return f"{v:.{digits}f}×"


def fmt_num(v, digits=2):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "—"
    return f"{v:.{digits}f}"


def _kpi_card(label: str, value: str, delta: str = "", color: str = PALETTE["amber"]) -> str:
    text_color = PALETTE["text"]
    delta_html = (
        f"<div style='font-size:0.72rem;color:{text_color};margin-top:2px'>{delta}</div>"
        if delta else ""
    )
    text_col = PALETTE["text"]
    return f"""
    <div style="
        background:rgba(26,58,82,0.55);
        border:1px solid rgba(255,195,106,0.15);
        border-radius:12px;
        padding:16px 20px;
        min-height:90px;
    ">
        <div style="font-size:0.68rem;text-transform:uppercase;letter-spacing:1px;
                    color:{text_col};margin-bottom:6px">{label}</div>
        <div style="font-size:1.55rem;font-weight:700;color:{color};
                    font-family:Figtree,sans-serif;line-height:1.1">{value}</div>
        {delta_html}
    </div>"""


# ─────────────────────────────────────────────────────────────────────────────
# CARREGAMENTO DE DADOS (com cache)
# ─────────────────────────────────────────────────────────────────────────────

@st.cache_data(ttl=3600, show_spinner=False)
def _load_historico() -> pd.DataFrame:
    lf = load_parquet("historico_anbima")
    df = lf.select(["ID_CNPJ_Fundo", "Codigo_Subclasse", "Data_Posicao", "PU_Cota", "PL_Total"]).collect().to_pandas()
    df["Data_Posicao"] = pd.to_datetime(df["Data_Posicao"], errors="coerce")
    df["PU_Cota"]      = pd.to_numeric(df["PU_Cota"],      errors="coerce")
    df["PL_Total"]     = pd.to_numeric(df["PL_Total"],     errors="coerce")
    return df


@st.cache_data(ttl=3600, show_spinner=False)
def _load_cdi() -> pd.DataFrame:
    lf = load_parquet("cdi")
    df = lf.collect().to_pandas()
    df["Data_Posicao"] = pd.to_datetime(df["Data_Posicao"], errors="coerce")
    for c in ("DI_aa", "DI_ad", "DI_aa_ftr", "DI_ad_ftr"):
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


@st.cache_data(ttl=3600, show_spinner=False)
def _load_peers_carteira() -> pd.DataFrame:
    lf = load_parquet("fundos_peers_carteira")
    return lf.select(["ID_CNPJ_Fundo", "Nome_Fundo_CVM"]).unique().collect().to_pandas()


@st.cache_data(ttl=1800, show_spinner=False)
def _calcular_tudo(
    cnpj_alvo: str,
    cnpjs_peers: tuple[str, ...],
    data_inicio_str: str,
    data_fim_str: str,
) -> dict:
    """Executa todos os cálculos; usa cache por combinação de parâmetros."""
    df_hist = _load_historico()
    df_cdi  = _load_cdi()

    cnpjs_todos = list({cnpj_alvo} | set(cnpjs_peers))

    # Filtro de período
    data_inicio = pd.to_datetime(data_inicio_str)
    data_fim    = pd.to_datetime(data_fim_str)

    # Retornos diários
    df_ret = calcular_retorno_diario(df_hist, df_cdi, cnpjs=cnpjs_todos)
    df_ret = df_ret[
        (df_ret["Data_Posicao"] >= data_inicio) &
        (df_ret["Data_Posicao"] <= data_fim)
    ].copy()

    if df_ret.empty:
        return {}

    df_acc     = calcular_acumulados(df_ret)
    df_mensal  = calcular_retorno_mensal(df_ret)
    df_idx     = calcular_cota_indexada(df_ret, df_cdi[
        (df_cdi["Data_Posicao"] >= data_inicio) &
        (df_cdi["Data_Posicao"] <= data_fim)
    ])
    df_risco   = calcular_metricas_risco(df_ret)

    return {
        "df_ret":    df_ret,
        "df_acc":    df_acc,
        "df_mensal": df_mensal,
        "df_idx":    df_idx,
        "df_risco":  df_risco,
    }


# ─────────────────────────────────────────────────────────────────────────────
# RECUPERAR CONTEXTO DA ABA DE PEERS
# ─────────────────────────────────────────────────────────────────────────────

fundo_alvo_ss   = st.session_state.get("fof_fundo_nome", None)  # persistido por Portfolio/Peers
cnpj_alvo_ss    = st.session_state.get("cnpj_alvo", None)
peers_filtrados = st.session_state.get("peers_filtrados", [])   # lista de dicts {cnpj, nome}


# ─────────────────────────────────────────────────────────────────────────────
# HEADER
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="inst-header">
    <div class="header-text" style="flex:1">
        <h1>Retornos & Risco</h1>
        <p>Análise de retornos históricos com base em dados ANBIMA · Comparativo de peers</p>
    </div>
</div>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# CARREGAMENTO BASE
# ─────────────────────────────────────────────────────────────────────────────
with st.spinner("Carregando base histórica ANBIMA…"):
    try:
        df_peers_carteira = _load_peers_carteira()
        dados_ok = True
    except Exception as e:
        st.error(f"❌ Erro ao carregar dados:\n\n{e}")
        dados_ok = False

if not dados_ok:
    st.stop()


# ─────────────────────────────────────────────────────────────────────────────
# SIDEBAR — FILTROS
# ─────────────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown('<div class="sidebar-section-title">Retornos & Risco</div>',
                unsafe_allow_html=True)

    # ── Fundo alvo ────────────────────────────────────────────────────────────
    fundos_disponiveis = sorted(df_peers_carteira["Nome_Fundo_CVM"].dropna().unique().tolist())

    idx_default = 0
    if fundo_alvo_ss and fundo_alvo_ss in fundos_disponiveis:
        idx_default = fundos_disponiveis.index(fundo_alvo_ss)

    fundo_alvo_sel = st.selectbox(
        "Fundo Analisado",
        options=fundos_disponiveis,
        index=idx_default,
        format_func=shorten,
        key="ret_fundo_alvo",
    )

    cnpj_alvo = df_peers_carteira.loc[
        df_peers_carteira["Nome_Fundo_CVM"] == fundo_alvo_sel, "ID_CNPJ_Fundo"
    ].iloc[0] if not df_peers_carteira.empty else None

    st.markdown("---")

    # ── Peers: herda da aba de Peers ou seleção manual ───────────────────────
    if peers_filtrados:
        peers_nome_options = [
            p["nome"] for p in peers_filtrados
            if p.get("nome") != fundo_alvo_sel and p.get("nome") in fundos_disponiveis
        ]
        peers_default = peers_nome_options[:3]
    else:
        peers_nome_options = [
            p for p in fundos_disponiveis if p != fundo_alvo_sel
        ]
        peers_default = []

    peers_sel_nomes = st.multiselect(
        "Peers para comparar",
        options=peers_nome_options,
        default=peers_default,
        max_selections=3,
        format_func=shorten,
        key="ret_peers",
        help="Você pode adicionar ou remover peers aqui.",
    )

    # Mapeia nomes → CNPJs
    cnpjs_peers = tuple(
        df_peers_carteira.loc[
            df_peers_carteira["Nome_Fundo_CVM"] == n, "ID_CNPJ_Fundo"
        ].iloc[0]
        for n in peers_sel_nomes
        if not df_peers_carteira.loc[df_peers_carteira["Nome_Fundo_CVM"] == n].empty
    )

    st.markdown("---")

    # ── Período de análise ────────────────────────────────────────────────────
    st.markdown("**Período de análise**")
    hoje = pd.Timestamp.today().normalize()
    data_inicio_input = st.date_input(
        "Data início",
        value=pd.Timestamp('2026-01-01'),
        key="ret_dt_inicio",
    )
    data_fim_input = st.date_input(
        "Data fim",
        value=hoje.date(),
        key="ret_dt_fim",
    )

    data_inicio_str = str(data_inicio_input)
    data_fim_str    = str(data_fim_input)

    st.markdown("---")
    calcular_btn = st.button("⚡ Calcular Retornos", use_container_width=True, type="primary")

# ─────────────────────────────────────────────────────────────────────────────
# CÁLCULOS PRINCIPAIS
# ─────────────────────────────────────────────────────────────────────────────
if cnpj_alvo is None:
    st.warning("Selecione um fundo analisado na sidebar.")
    st.stop()

# Dispara cálculo (botão ou mudança de parâmetros via session_state)
chave_calc = (cnpj_alvo, cnpjs_peers, data_inicio_str, data_fim_str)
if calcular_btn or "ret_resultado" not in st.session_state or st.session_state.get("ret_chave") != chave_calc:
    with st.spinner("Calculando retornos e métricas de risco…"):
        try:
            resultado = _calcular_tudo(cnpj_alvo, cnpjs_peers, data_inicio_str, data_fim_str)
            st.session_state["ret_resultado"] = resultado
            st.session_state["ret_chave"]     = chave_calc
        except Exception as e:
            st.error(f"❌ Erro no cálculo:\n\n{e}")
            st.stop()

resultado = st.session_state.get("ret_resultado", {})

if not resultado:
    st.warning("Nenhum dado de retorno disponível para os parâmetros selecionados. "
               "Verifique se o parquet `historico_anbima` foi carregado corretamente.")
    st.stop()

df_acc    = resultado["df_acc"]
df_mensal = resultado["df_mensal"]
df_idx    = resultado["df_idx"]
df_risco  = resultado["df_risco"]

# Linhas do fundo alvo
acc_alvo   = df_acc[df_acc["ID_CNPJ_Fundo"] == cnpj_alvo]
risco_alvo = df_risco[df_risco["ID_CNPJ_Fundo"] == cnpj_alvo]

# ── Mapa CNPJ → nome curto ────────────────────────────────────────────────────
nome_map: dict[str, str] = {"__CDI__": "CDI"}
nome_map[cnpj_alvo] = shorten(fundo_alvo_sel)
for n in peers_sel_nomes:
    row = df_peers_carteira[df_peers_carteira["Nome_Fundo_CVM"] == n]
    if not row.empty:
        nome_map[row.iloc[0]["ID_CNPJ_Fundo"]] = shorten(n)


# ─────────────────────────────────────────────────────────────────────────────
# SEÇÃO 1 — CARDS KPI
# ─────────────────────────────────────────────────────────────────────────────
st.markdown(
    '<div class="section-label">Retornos do Fundo Analisado</div>',
    unsafe_allow_html=True,
)

if not acc_alvo.empty:
    row = acc_alvo.iloc[0]
    kpis = [
        ("Retorno 12M",    fmt_pct_pos(row.get("Ret_FD_12M")),
         f"CDI: {fmt_pct_pos(row.get('Ret_DI_12M'))}"),
        ("% CDI — 12M",    fmt_x(row.get("Ret_FD_DI_pct_12M")),
         f"CDI+: {fmt_pct(row.get('Ret_FD_DI_mais_12M'))}"),
        ("Retorno 24M",    fmt_pct_pos(row.get("Ret_FD_24M")),
         f"CDI: {fmt_pct_pos(row.get('Ret_DI_24M'))}"),
        ("% CDI — 24M",    fmt_x(row.get("Ret_FD_DI_pct_24M")),
         f"CDI+: {fmt_pct(row.get('Ret_FD_DI_mais_24M'))}"),
        ("Retorno Inception", fmt_pct_pos(row.get("Ret_FD_Total")),
         f"desde {row.get('Data_Inicio').strftime('%d/%m/%Y') if pd.notna(row.get('Data_Inicio')) else '—'}"),
        ("Ret. Inception aa", fmt_pct_pos(row.get("Ret_FD_Total_aa")),
         f"CDI aa: {fmt_pct_pos(row.get('Ret_DI_Total_aa'))}"),
    ]

    cols = st.columns(len(kpis))
    for col, (label, val, delta) in zip(cols, kpis):
        with col:
            st.markdown(_kpi_card(label, val, delta), unsafe_allow_html=True)
else:
    st.info("Dados de acumulado não disponíveis para o fundo selecionado no período.")

st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# SEÇÃO 2 — GRÁFICO DE COTA INDEXADA
# ─────────────────────────────────────────────────────────────────────────────
st.markdown('<div class="section-label">Cota Acumulada</div>', unsafe_allow_html=True)

_ctrl_col1, _ctrl_col2 = st.columns([3, 5])
with _ctrl_col1:
    modo_cota = st.radio(
        "Visualização",
        ["Base 100", "% do CDI"],
        horizontal=True,
        label_visibility="collapsed",
        key="modo_cota_radio",
    )
with _ctrl_col2:
    _periodo_opts = ["Mês", "Semestre", "Ano", "Todo o período"]
    periodo_viz = st.radio(
        "Período",
        _periodo_opts,
        index=3,
        horizontal=True,
        label_visibility="collapsed",
        key="periodo_viz_radio",
    )

# Calcula data de corte com base no período selecionado
_data_max_idx = pd.to_datetime(data_fim_str)
if periodo_viz == "Mês":
    _data_corte = _data_max_idx - pd.DateOffset(months=1)
elif periodo_viz == "Semestre":
    _data_corte = _data_max_idx - pd.DateOffset(months=6)
elif periodo_viz == "Ano":
    _data_corte = _data_max_idx - pd.DateOffset(years=1)
else:
    _data_corte = pd.to_datetime(data_inicio_str)

if not df_idx.empty:
    # Filtra pelo período e rebaseia cada série para 100 na data de corte
    df_idx_viz = df_idx[df_idx["Data_Posicao"] >= _data_corte].copy()

    # Re-normaliza cada série individualmente: o primeiro ponto vira 100
    frames_rebased = []
    for _cnpj, _grp in df_idx_viz.groupby("ID_CNPJ_Fundo"):
        _grp = _grp.sort_values("Data_Posicao").copy()
        _base_val = _grp["Cota_Indexada"].iloc[0]
        if _base_val and _base_val != 0:
            _grp["Cota_Indexada"] = _grp["Cota_Indexada"] / _base_val * 100.0
        frames_rebased.append(_grp)
    df_idx_viz = pd.concat(frames_rebased, ignore_index=True) if frames_rebased else df_idx_viz

    # Ordem de exibição: CDI primeiro, depois alvo, depois peers
    cnpjs_plot = list(dict.fromkeys(
        ["__CDI__", cnpj_alvo] + list(cnpjs_peers)
    ))

    cdi_idx = df_idx_viz[df_idx_viz["ID_CNPJ_Fundo"] == "__CDI__"].drop_duplicates("Data_Posicao").set_index("Data_Posicao")["Cota_Indexada"]

    # Define y_title e y_tickfmt antes do loop (evita NameError quando CDI é o primeiro)
    if modo_cota == "% do CDI":
        y_title   = "Retorno em % do CDI"
        y_tickfmt = ".0f"
    else:
        y_title   = f"Cota (base 100 em {_data_corte.strftime('%d/%m/%Y')})"
        y_tickfmt = ".1f"

    fig_idx = go.Figure()
    for i, cnpj in enumerate(cnpjs_plot):
        serie = df_idx_viz[df_idx_viz["ID_CNPJ_Fundo"] == cnpj].sort_values("Data_Posicao").copy()
        if serie.empty:
            continue

        if modo_cota == "% do CDI":
            # Alinha o CDI às datas da série do fundo (reindex seguro)
            cdi_alinhado = cdi_idx.reindex(serie["Data_Posicao"].values, fill_value=np.nan)
            # Interpola lacunas para não propagar NaN
            cdi_alinhado = pd.Series(cdi_alinhado.values, index=serie["Data_Posicao"].values)
            cdi_alinhado = cdi_alinhado.interpolate(method="linear").ffill().bfill()

            ret_fd = (serie["Cota_Indexada"].values / 100.0) - 1.0
            ret_di = (cdi_alinhado.values / 100.0) - 1.0

            with np.errstate(divide="ignore", invalid="ignore"):
                pct_cdi = np.where(
                    np.abs(ret_di) < 1e-10,
                    100.0,
                    (ret_fd / ret_di) * 100.0,
                )
            serie["Y_plot"] = pct_cdi
            hover_fmt = "<b>%{hovertext}</b><br>%{x|%d/%m/%Y}<br>%{y:.1f}% do CDI<extra></extra>"
        else:
            serie["Y_plot"] = serie["Cota_Indexada"]
            hover_fmt = "<b>%{hovertext}</b><br>%{x|%d/%m/%Y}<br>Cota: %{y:.2f}<extra></extra>"

        nome   = nome_map.get(cnpj, cnpj)
        is_cdi = cnpj == "__CDI__"
        is_alvo = cnpj == cnpj_alvo

        cor = (
            _COR_CDI  if is_cdi  else
            _COR_ALVO if is_alvo else
            _CORES_PEERS[(i - 2) % len(_CORES_PEERS)]
        )
        width = 2.5 if is_alvo else (1.5 if is_cdi else 1.8)
        dash  = "dot" if is_cdi else "solid"

        fig_idx.add_trace(go.Scatter(
            x=serie["Data_Posicao"],
            y=serie["Y_plot"],
            name=nome,
            hovertext=[nome] * len(serie),
            line=dict(color=cor, width=width, dash=dash),
            hovertemplate=hover_fmt,
        ))

    fig_idx.update_layout(
        **_CHART,
        height=420,
        legend=dict(**_LEGEND, orientation="h", y=1.04, x=0, yanchor="bottom"),
        margin=dict(l=0, r=20, t=30, b=10),
    )
    fig_idx.update_yaxes(title_text=y_title, tickformat=y_tickfmt)
    st.plotly_chart(fig_idx, use_container_width=True)
else:
    st.info("Sem dados de cota indexada.")

st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# SEÇÃO 3 — TABELA COMPARATIVA DE RETORNOS
# ─────────────────────────────────────────────────────────────────────────────
st.markdown('<div class="section-label">Tabela Comparativa de Retornos</div>',
            unsafe_allow_html=True)

if not df_acc.empty:
    cnpjs_tabela = [cnpj_alvo] + list(cnpjs_peers)
    df_tbl = df_acc[df_acc["ID_CNPJ_Fundo"].isin(cnpjs_tabela)].copy()
    df_tbl["Fundo"] = df_tbl["ID_CNPJ_Fundo"].map(nome_map).fillna(df_tbl["ID_CNPJ_Fundo"])
    df_tbl = df_tbl.sort_values(
        "ID_CNPJ_Fundo",
        key=lambda s: s.map(lambda x: 0 if x == cnpj_alvo else 1)
    )

    # ── Calcula retorno acumulado no período visualizado (Mês/Semestre/Ano) ──
    _lbl_periodo = {
        "Mês": "1M", "Semestre": "6M", "Ano": "12M", "Todo o período": "Período"
    }.get(periodo_viz, "Período")

    _col_periodo = f"Ret_FD_{_lbl_periodo}_viz"
    _col_cdi_periodo = f"Ret_DI_{_lbl_periodo}_viz"
    _col_pct_cdi_periodo = f"Pct_CDI_{_lbl_periodo}_viz"

    def _acc_periodo(cnpj: str, data_corte: pd.Timestamp) -> tuple:
        """Retorna (ret_fd, ret_di, pct_cdi) acumulado desde data_corte até data_fim."""
        df_r_ = resultado["df_ret"]
        grp = df_r_[
            (df_r_["ID_CNPJ_Fundo"] == cnpj) &
            (df_r_["Data_Posicao"] >= data_corte)
        ]
        if grp.empty:
            return np.nan, np.nan, np.nan
        from utils.returns_calc import _prod_ftr
        ret_fd = _prod_ftr(grp["COTA_ad_ftr"]) - 1
        ret_di = _prod_ftr(grp["DI_ad_ftr"]) - 1
        pct_cdi = (ret_fd / ret_di) if ret_di != 0 else np.nan
        return ret_fd, ret_di, pct_cdi

    df_tbl[_col_periodo]       = df_tbl["ID_CNPJ_Fundo"].apply(lambda c: _acc_periodo(c, _data_corte)[0])
    df_tbl[_col_cdi_periodo]   = df_tbl["ID_CNPJ_Fundo"].apply(lambda c: _acc_periodo(c, _data_corte)[1])
    df_tbl[_col_pct_cdi_periodo] = df_tbl["ID_CNPJ_Fundo"].apply(lambda c: _acc_periodo(c, _data_corte)[2])

    col_cfg = {
        "Fundo":                     st.column_config.TextColumn("Fundo", width="large"),
        _col_periodo:                st.column_config.NumberColumn(f"Ret {_lbl_periodo}",      format="%.2f%%"),
        _col_cdi_periodo:            st.column_config.NumberColumn(f"CDI {_lbl_periodo}",      format="%.2f%%"),
        _col_pct_cdi_periodo:        st.column_config.NumberColumn(f"% CDI {_lbl_periodo}",    format="%.0f%%"),
        "Ret_FD_12M":                st.column_config.NumberColumn("12M",          format="%.2f%%"),
        "Ret_FD_DI_pct_12M":         st.column_config.NumberColumn("% CDI 12M",    format="%.0f%%"),
        "Ret_FD_DI_mais_12M":        st.column_config.NumberColumn("CDI+ 12M",     format="%.3f%%"),
        "Ret_FD_24M":                st.column_config.NumberColumn("24M",          format="%.2f%%"),
        "Ret_FD_DI_pct_24M":         st.column_config.NumberColumn("% CDI 24M",    format="%.0f%%"),
        "Ret_FD_Total":              st.column_config.NumberColumn("Desde o Início",     format="%.2f%%"),
        "Ret_FD_Total_aa":           st.column_config.NumberColumn("Desde o Início aa",  format="%.2f%%"),
        "Ret_FD_DI_pct_Total":       st.column_config.NumberColumn("% CDI Início", format="%.0f%%"),
        "Dias_total":                st.column_config.NumberColumn("Dias",          format="%d"),
    }

    # Multiplica percentuais por 100 para exibição formatada
    pct_cols = ["Ret_FD_12M", "Ret_DI_12M", "Ret_FD_DI_mais_12M",
                "Ret_FD_24M", "Ret_DI_24M", "Ret_FD_DI_mais_24M",
                "Ret_FD_Total", "Ret_DI_Total", "Ret_FD_Total_aa", "Ret_DI_Total_aa",
                "Ret_FD_DI_pct_12M", "Ret_FD_DI_pct_24M", "Ret_FD_DI_pct_Total",
                _col_periodo, _col_cdi_periodo, _col_pct_cdi_periodo]
    df_show = df_tbl.copy()
    for c in pct_cols:
        if c in df_show.columns:
            df_show[c] = df_show[c] * 100

    # Colunas do período escolhido primeiro, depois as fixas
    cols_show = [
        "Fundo",
        _col_periodo, _col_cdi_periodo, _col_pct_cdi_periodo,
        "Ret_FD_12M", "Ret_FD_DI_pct_12M", "Ret_FD_DI_mais_12M",
        "Ret_FD_24M", "Ret_FD_DI_pct_24M",
        "Ret_FD_Total", "Ret_FD_Total_aa", "Ret_FD_DI_pct_Total", "Dias_total",
    ]
    cols_show = [c for c in cols_show if c in df_show.columns]
    st.dataframe(df_show[cols_show], hide_index=True, use_container_width=True, column_config=col_cfg)

st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# SEÇÃO 4 — HEATMAP MENSAL
# ─────────────────────────────────────────────────────────────────────────────
st.markdown('<div class="section-label">Retornos Mensais</div>', unsafe_allow_html=True)

tab_heat_abs, tab_heat_cdi, tab_bar_mensal = st.tabs([
    "Retorno Absoluto (%)", "% do CDI", "Barras Mensais (Fundo vs CDI)"
])

if not df_mensal.empty:
    cnpjs_heat = [cnpj_alvo] + list(cnpjs_peers)
    df_h = df_mensal[df_mensal["ID_CNPJ_Fundo"].isin(cnpjs_heat)].copy()
    df_h["Fundo"] = df_h["ID_CNPJ_Fundo"].map(nome_map).fillna(df_h["ID_CNPJ_Fundo"])
    df_h["Mes_str"] = df_h["Mes"].astype(str)
    df_h = df_h.sort_values("Mes")

    def _build_grouped_bar(df_h: pd.DataFrame, val_col: str, title: str, is_pct_cdi: bool = False) -> go.Figure:
        fig = go.Figure()
        
        fundo_alvo_curto = nome_map.get(cnpj_alvo, cnpj_alvo)
        # Identificar fundos únicos e ordenar (alvo primeiro)
        fundos = [fundo_alvo_curto] + [f for f in df_h["Fundo"].unique() if f != fundo_alvo_curto]
        
        for i, f in enumerate(fundos):
            df_f = df_h[df_h["Fundo"] == f].sort_values("Mes")
            if df_f.empty: continue
            
            y_vals = df_f[val_col].fillna(0) * 100
            
            if not is_pct_cdi:
                text_fmt = [f"{v:+.2f}%" for v in y_vals]
                hovertemplate = "<b>%{x}</b><br>Fundo: <b>%{y:.2f}%</b><extra></extra>"
            else:
                text_fmt = [f"{v:.0f}%" for v in y_vals]
                hovertemplate = "<b>%{x}</b><br>Fundo: <b>%{y:.1f}% do CDI</b><extra></extra>"
            
            is_alvo = f == fundo_alvo_curto
            cor = _COR_ALVO if is_alvo else _CORES_PEERS[(i - 1) % len(_CORES_PEERS)]
            
            fig.add_trace(go.Bar(
                x=df_f["Mes_str"].tolist(),
                y=y_vals.tolist(),
                name=f,
                marker_color=cor,
                text=text_fmt,
                textposition="outside",
                textfont=dict(size=8, color=PALETTE["text"]),
                hovertemplate=hovertemplate,
            ))
            
        fig.update_layout(
            **_CHART,
            barmode="group",
            height=400,
            legend=dict(**_LEGEND, orientation="h", y=1.04, x=0, yanchor="bottom"),
            margin=dict(l=0, r=20, t=30, b=40),
        )
        fig.update_xaxes(tickangle=-45, tickfont=dict(size=9))
        if not is_pct_cdi:
            fig.update_yaxes(title_text=title, ticksuffix="%", zeroline=True, zerolinecolor="rgba(255,255,255,0.15)")
            
            # Adicionar linha do CDI
            df_cdi = df_h[["Mes", "Mes_str", "Ret_DI_am"]].drop_duplicates("Mes").sort_values("Mes")
            y_cdi = df_cdi["Ret_DI_am"].fillna(0) * 100
            fig.add_trace(go.Scatter(
                x=df_cdi["Mes_str"].tolist(),
                y=y_cdi.tolist(),
                name="CDI",
                mode="lines+markers",
                line=dict(color=_COR_CDI, width=1.8, dash="dot"),
                marker=dict(size=4, color=_COR_CDI),
                hovertemplate="<b>%{x}</b><br>CDI: <b>%{y:.2f}%</b><extra></extra>",
            ))
        else:
            fig.update_yaxes(title_text=title, ticksuffix="", zeroline=True, zerolinecolor="rgba(255,255,255,0.15)")
            
        return fig

    with tab_heat_abs:
        fig_h_abs = _build_grouped_bar(df_h, "Ret_FD_am", "Retorno Mensal (%)", is_pct_cdi=False)
        st.plotly_chart(fig_h_abs, use_container_width=True)

    with tab_heat_cdi:
        fig_h_cdi = _build_grouped_bar(df_h, "Ret_FD_DI_pct_am", "% CDI Mensal", is_pct_cdi=True)
        st.plotly_chart(fig_h_cdi, use_container_width=True)

    with tab_bar_mensal:
        # Retornos mensais do fundo alvo — barras coloridas por acima/abaixo do CDI
        df_alvo_m = df_mensal[df_mensal["ID_CNPJ_Fundo"] == cnpj_alvo].sort_values("Mes").copy()
        df_alvo_m["Mes_str"]   = df_alvo_m["Mes"].astype(str)
        df_alvo_m["FD_pct"]    = df_alvo_m["Ret_FD_am"].fillna(0) * 100
        df_alvo_m["DI_pct"]    = df_alvo_m["Ret_DI_am"].fillna(0) * 100
        df_alvo_m["Acima_CDI"] = df_alvo_m["Ret_FD_am"] > df_alvo_m["Ret_DI_am"]

        if not df_alvo_m.empty:
            cores_bar = [
                PALETTE["green"] if a else PALETTE["red"]
                for a in df_alvo_m["Acima_CDI"]
            ]
            fig_bar = go.Figure()
            fig_bar.add_trace(go.Bar(
                x=df_alvo_m["Mes_str"].tolist(),
                y=df_alvo_m["FD_pct"].tolist(),
                name=nome_map.get(cnpj_alvo, "Fundo"),
                marker_color=cores_bar,
                text=[f"{v:+.2f}%" for v in df_alvo_m["FD_pct"]],
                textposition="outside",
                textfont=dict(size=8, color=PALETTE["text"]),
                hovertemplate="<b>%{x}</b><br>Fundo: <b>%{y:.3f}%</b><extra></extra>",
            ))
            # CDI como linha de referência
            fig_bar.add_trace(go.Scatter(
                x=df_alvo_m["Mes_str"].tolist(),
                y=df_alvo_m["DI_pct"].tolist(),
                name="CDI",
                mode="lines+markers",
                line=dict(color=_COR_CDI, width=1.8, dash="dot"),
                marker=dict(size=4, color=_COR_CDI),
                hovertemplate="CDI: %{y:.3f}%<extra></extra>",
            ))
            fig_bar.update_layout(
                **_CHART, height=380,
                legend=dict(**_LEGEND, orientation="h", y=1.04, x=0, yanchor="bottom"),
                margin=dict(l=0, r=20, t=30, b=40),
            )
            fig_bar.update_xaxes(tickangle=-45, tickfont=dict(size=9))
            fig_bar.update_yaxes(title_text="Retorno (%)", ticksuffix="%",
                                 zeroline=True, zerolinecolor="rgba(255,255,255,0.15)")
            st.caption("🟢 Acima do CDI  🔴 Abaixo do CDI")
            st.plotly_chart(fig_bar, use_container_width=True)
        else:
            st.info("Sem dados mensais para o fundo selecionado.")
else:
    for tab in (tab_heat_abs, tab_heat_cdi, tab_bar_mensal):
        with tab:
            st.info("Sem dados mensais disponíveis.")

st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# SEÇÃO 5 — MÉTRICAS DE RISCO
# ─────────────────────────────────────────────────────────────────────────────
st.markdown('<div class="section-label">Métricas de Risco</div>', unsafe_allow_html=True)

if not df_risco.empty:
    cnpjs_risco = [cnpj_alvo] + list(cnpjs_peers)
    df_r = df_risco[df_risco["ID_CNPJ_Fundo"].isin(cnpjs_risco)].copy()
    df_r["Fundo"] = df_r["ID_CNPJ_Fundo"].map(nome_map).fillna(df_r["ID_CNPJ_Fundo"])

    tab_risco_kpi, tab_distrib, tab_sharpe_var, tab_risco_tbl = st.tabs([
        "Destaques",
        "Distribuição Mensal",
        "Risco x Retorno",
        "Tabela Completa",
    ])

    # ── Destaques ─────────────────────────────────────────────────────────────
    with tab_risco_kpi:
        if not risco_alvo.empty:
            row_r = risco_alvo.iloc[0]

            r_kpis = [
                ("Vol. Anual",       fmt_pct_pos(row_r.get("Vol_Anual")),       "desvio-padrão diário × √252"),
                ("Sharpe (12M)",     fmt_num(row_r.get("Sharpe")),              "(Ret 12M − CDI 12M) / Vol Anual"),
                ("Inf. Ratio",       fmt_num(row_r.get("Information_Ratio")),   "Alpha Anual / Tracking Error Anual"),
                ("Tracking Error",   fmt_pct_pos(row_r.get("Tracking_Error")),  "dp(excesso diário) × √252, anual"),
                ("VaR 1M (95%)",     fmt_pct_pos(row_r.get("VaR_1M")),         "perda esperada em 21 dias (param.)"),
                ("CVaR 1M (95%)",    fmt_pct_pos(row_r.get("CVaR_1M")),        "expected shortfall (param.)"),
                ("Pior Mês",
                 fmt_pct(row_r.get("Pior_Mes")),
                 str(row_r.get("Pior_Mes_Data", ""))),
                ("Meses acima CDI",
                 f"{row_r.get('Meses_Acima_CDI_Qtd', '—')} / {row_r.get('Total_Meses', '—')}",
                 fmt_pct_pos(row_r.get("Meses_Acima_CDI_Pct"))),
            ]
            c1, c2, c3, c4 = st.columns(4)
            for i, (label, val, delta) in enumerate(r_kpis):
                col = [c1, c2, c3, c4][i % 4]
                cor = PALETTE["red"] if label == "Pior Mês" else PALETTE["amber"]
                with col:
                    st.markdown(_kpi_card(label, val, delta, color=cor), unsafe_allow_html=True)

            # ── Painel de Fórmulas ───────────────────────────────────────────────────
            st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)
            with st.expander("📐 Metodologia das Métricas de Risco", expanded=False):
                st.markdown("""
<div style="font-family:Figtree,sans-serif; font-size:0.85rem; line-height:1.9; color:var(--text-secondary);">

<table style="width:100%; border-collapse:collapse;">
  <thead>
    <tr style="border-bottom:1px solid rgba(137,155,183,0.25);">
      <th style="padding:8px 12px; text-align:left; color:var(--accent-warm); font-size:0.72rem;
                 text-transform:uppercase; letter-spacing:1px; width:18%;">Métrica</th>
      <th style="padding:8px 12px; text-align:left; color:var(--accent-warm); font-size:0.72rem;
                 text-transform:uppercase; letter-spacing:1px; width:35%;">Fórmula</th>
      <th style="padding:8px 12px; text-align:left; color:var(--accent-warm); font-size:0.72rem;
                 text-transform:uppercase; letter-spacing:1px;">Descrição</th>
    </tr>
  </thead>
  <tbody>
    <tr style="border-bottom:1px solid rgba(137,155,183,0.1);">
      <td style="padding:10px 12px; font-weight:600; color:var(--text-hi);">Volatilidade<br>Anual</td>
      <td style="padding:10px 12px; font-family:'Courier New',monospace; color:#93c5fd; font-size:0.9rem;">
        Vol_anual = σ_d × &radic;252
      </td>
      <td style="padding:10px 12px;">
        <b>σ_d</b> é o desvio-padrão dos retornos diários da cota (COTA_ad), calculado com ddof=1 sobre todo o período.
        Multiplicado por &radic;252 para anualizar (convenção mercado brasileiro).
      </td>
    </tr>
    <tr style="border-bottom:1px solid rgba(137,155,183,0.1);">
      <td style="padding:10px 12px; font-weight:600; color:var(--text-hi);">Sharpe<br>(12M)</td>
      <td style="padding:10px 12px; font-family:'Courier New',monospace; color:#93c5fd; font-size:0.9rem;">
        Sharpe = (R_fd_12M &minus; R_di_12M) / Vol_anual
      </td>
      <td style="padding:10px 12px;">
        <b>R_fd_12M</b>: retorno acumulado do fundo nos últimos 12 meses (produto dos fatores diários).<br>
        <b>R_di_12M</b>: retorno acumulado do CDI no mesmo período.<br>
        <b>Vol_anual</b>: volatilidade anual de todo o histórico disponível.<br>
        Mede retorno excedente por unidade de risco total.
      </td>
    </tr>
    <tr style="border-bottom:1px solid rgba(137,155,183,0.1);">
      <td style="padding:10px 12px; font-weight:600; color:var(--text-hi);">Tracking<br>Error</td>
      <td style="padding:10px 12px; font-family:'Courier New',monospace; color:#93c5fd; font-size:0.9rem;">
        TE = σ(R_fd_d &minus; R_di_d) × &radic;252
      </td>
      <td style="padding:10px 12px;">
        Desvio-padrão (ddof=1) da série de excessos diários <b>(COTA_ad &minus; DI_ad)</b>,
        anualizado por &radic;252. Mede a disperso do retorno em relação ao benchmark (CDI).
        Um TE baixo indica que o fundo se move próximo ao CDI; alto indica desvios frequentes.
      </td>
    </tr>
    <tr style="border-bottom:1px solid rgba(137,155,183,0.1);">
      <td style="padding:10px 12px; font-weight:600; color:var(--text-hi);">Information<br>Ratio</td>
      <td style="padding:10px 12px; font-family:'Courier New',monospace; color:#93c5fd; font-size:0.9rem;">
        IR = (μ_exc_d × 252) / TE
      </td>
      <td style="padding:10px 12px;">
        <b>μ_exc_d</b>: média diária do excesso de retorno (COTA_ad &minus; DI_ad).<br>
        Multiplicado por 252 para obter o <b>alpha anualizado</b>.<br>
        Dividido pelo Tracking Error anualizado.<br>
        Mede a consistência da geração de alpha: IR &gt; 0,5 é geralmente considerado bom.
      </td>
    </tr>
    <tr style="border-bottom:1px solid rgba(137,155,183,0.1);">
      <td style="padding:10px 12px; font-weight:600; color:var(--text-hi);">VaR 1M<br>(95%)</td>
      <td style="padding:10px 12px; font-family:'Courier New',monospace; color:#93c5fd; font-size:0.9rem;">
        VaR = &minus;(μ_d × 21 + σ_d × &radic;21 × z<sub>0.95</sub>)
      </td>
      <td style="padding:10px 12px;">
        Método paramétrico normal. <b>z_0.95 ≈ 1,645</b> (quantil normal).<br>
        Estima a perda máxima esperada em 1 mês (21 dias úteis) com 95% de confiança,
        supondo distribuição normal dos retornos diários.
      </td>
    </tr>
    <tr>
      <td style="padding:10px 12px; font-weight:600; color:var(--text-hi);">CVaR 1M<br>(Expected Shortfall)</td>
      <td style="padding:10px 12px; font-family:'Courier New',monospace; color:#93c5fd; font-size:0.9rem;">
        CVaR = &minus;(μ_d × 21 + σ_d × &radic;21 × ES_z)
      </td>
      <td style="padding:10px 12px;">
        <b>ES_z = φ(z_0.95) / (1 &minus; 0,95)</b>, onde φ é a PDF normal padrão.<br>
        Média das perdas que superam o VaR. Mais conservador que o VaR — captura a
        "cauda" da distribuição de perdas.
      </td>
    </tr>
  </tbody>
</table>

<div style="margin-top:12px; padding:10px 14px; background:rgba(62,91,125,0.2);
            border-left:3px solid var(--accent-warm); border-radius:4px; font-size:0.78rem;">
  📌 <b>Nota sobre dados:</b> Todos os cálculos utilizam a série de PU_Cota diária reportada à ANBIMA.
  O CDI de referência é o DI Over (CETIP), expresso como fator diário <b>DI_ad_ftr</b>.
  O período base é definido pelo filtro de datas na sidebar.
</div>

</div>
                """, unsafe_allow_html=True)
        else:
            st.info("Sem métricas de risco para o fundo selecionado.")

    # ── Distribuição de Retornos Mensais ──────────────────────────────────────
    with tab_distrib:
        df_mensal_alvo = df_mensal[df_mensal["ID_CNPJ_Fundo"] == cnpj_alvo].copy()
        if df_mensal_alvo.empty:
            st.info("Sem dados mensais para o fundo selecionado.")
        else:
            df_mensal_alvo["FD_pct"]    = df_mensal_alvo["Ret_FD_am"].fillna(0) * 100
            df_mensal_alvo["DI_pct"]    = df_mensal_alvo["Ret_DI_am"].fillna(0) * 100
            df_mensal_alvo["Acima_CDI"] = df_mensal_alvo["Ret_FD_am"] > df_mensal_alvo["Ret_DI_am"]
            df_mensal_alvo["Mes_str"]   = df_mensal_alvo["Mes"].astype(str)
            df_mensal_alvo = df_mensal_alvo.sort_values("Mes")

            media_m = df_mensal_alvo["FD_pct"].mean()
            cdi_m   = df_mensal_alvo["DI_pct"].mean()
            std_m   = df_mensal_alvo["FD_pct"].std()
            n_total = len(df_mensal_alvo)
            n_pos   = (df_mensal_alvo["FD_pct"] >= 0).sum()
            n_acima = df_mensal_alvo["Acima_CDI"].sum()

            col_hist, col_stats = st.columns([7, 3])

            with col_hist:
                st.markdown('<div class="section-label">Histograma de Retornos Mensais</div>',
                            unsafe_allow_html=True)

                df_pos = df_mensal_alvo[df_mensal_alvo["FD_pct"] >= 0]
                df_neg = df_mensal_alvo[df_mensal_alvo["FD_pct"] < 0]

                fig_hist = go.Figure()
                if not df_pos.empty:
                    fig_hist.add_trace(go.Histogram(
                        x=df_pos["FD_pct"],
                        name="Meses positivos",
                        marker_color="rgba(16,185,129,0.65)",
                        marker_line=dict(color="rgba(16,185,129,0.9)", width=0.8),
                        xbins=dict(size=0.5),
                    ))
                if not df_neg.empty:
                    fig_hist.add_trace(go.Histogram(
                        x=df_neg["FD_pct"],
                        name="Meses negativos",
                        marker_color="rgba(239,68,68,0.65)",
                        marker_line=dict(color="rgba(239,68,68,0.9)", width=0.8),
                        xbins=dict(size=0.5),
                    ))

                for x_val, color_vl, label_vl in [
                    (0,       "rgba(255,255,255,0.35)", "Zero"),
                ]:
                    fig_hist.add_vline(
                        x=x_val, line_dash="dot", line_color=color_vl, line_width=1.5,
                        annotation_text=label_vl,
                        annotation_font=dict(color=color_vl, size=10),
                        annotation_position="top right" if x_val >= 0 else "top left",
                    )

                fig_hist.update_layout(
                    **_CHART, barmode="overlay",
                    height=340, margin=dict(l=0, r=20, t=30, b=10),
                    legend=dict(**_LEGEND, orientation="h", y=1.04, x=0, yanchor="bottom"),
                    bargap=0.05,
                )
                fig_hist.update_xaxes(title_text="Retorno Mensal (%)", ticksuffix="%")
                fig_hist.update_yaxes(title_text="Frequência (meses)")
                st.plotly_chart(fig_hist, use_container_width=True)

            with col_stats:
                st.markdown('<div class="section-label">Resumo</div>', unsafe_allow_html=True)
                for label, val, cor in [
                    ("Total de Meses",   str(n_total),                               PALETTE["text"]),
                    ("Meses Positivos",  f"{n_pos} ({n_pos/n_total*100:.0f}%)",     PALETTE["green"]),
                    ("Acima do CDI",     f"{n_acima} ({n_acima/n_total*100:.0f}%)", PALETTE["amber"]),
                    ("Média Mensal",     f"{media_m:+.2f}%",                         PALETTE["amber"]),
                    ("Desvio-Padrão",    f"{std_m:.2f}%",                            PALETTE["blue_lt"]),
                    ("Pior Mês",         f"{df_mensal_alvo['FD_pct'].min():+.2f}%", PALETTE["red"]),
                    ("Melhor Mês",       f"{df_mensal_alvo['FD_pct'].max():+.2f}%", PALETTE["green"]),
                ]:
                    st.markdown(_kpi_card(label, val, "", color=cor), unsafe_allow_html=True)
                    st.markdown("<div style='height:5px'></div>", unsafe_allow_html=True)

            # Barras mensais coloridas
            st.markdown('<div class="section-label" style="margin-top:18px">Retorno por Mês — Fundo vs CDI</div>',
                        unsafe_allow_html=True)

            cores_bar = [
                PALETTE["green"] if a else PALETTE["red"]
                for a in df_mensal_alvo["Acima_CDI"]
            ]
            fig_bars = go.Figure()
            fig_bars.add_trace(go.Bar(
                x=df_mensal_alvo["Mes_str"].tolist(),
                y=df_mensal_alvo["FD_pct"].tolist(),
                name=nome_map.get(cnpj_alvo, "Fundo"),
                marker_color=cores_bar,
                text=[f"{v:+.2f}%" for v in df_mensal_alvo["FD_pct"]],
                textposition="outside",
                textfont=dict(size=8, color=PALETTE["text"]),
                hovertemplate="<b>%{x}</b><br>Fundo: <b>%{y:.3f}%</b><extra></extra>",
            ))
            fig_bars.add_trace(go.Scatter(
                x=df_mensal_alvo["Mes_str"].tolist(),
                y=df_mensal_alvo["DI_pct"].tolist(),
                name="CDI",
                mode="lines+markers",
                line=dict(color=_COR_CDI, width=1.8, dash="dot"),
                marker=dict(size=4, color=_COR_CDI),
                hovertemplate="CDI: %{y:.3f}%<extra></extra>",
            ))
            fig_bars.update_layout(
                **_CHART, height=350,
                legend=dict(**_LEGEND, orientation="h", y=1.04, x=0, yanchor="bottom"),
                margin=dict(l=0, r=20, t=30, b=40),
            )
            fig_bars.update_xaxes(tickangle=-45, tickfont=dict(size=9))
            fig_bars.update_yaxes(title_text="Retorno (%)", ticksuffix="%",
                                  zeroline=True, zerolinecolor="rgba(255,255,255,0.15)")
            st.caption("🟢 Acima do CDI  🔴 Abaixo do CDI")
            st.plotly_chart(fig_bars, use_container_width=True)

    # ── Risco x Retorno (Dispersão) ──────────────────────────────────────────
    with tab_sharpe_var:
        if risco_alvo.empty:
            st.info("Sem métricas de risco disponíveis.")
        else:
            if len(cnpjs_peers) > 0 and len(df_r) > 1:
                st.markdown('<div class="section-label">Dispersão Risco x Retorno (Anualizado no Período)</div>',
                            unsafe_allow_html=True)
                
                df_sc = df_r.merge(df_acc[["ID_CNPJ_Fundo", "Ret_FD_Total_aa"]], on="ID_CNPJ_Fundo", how="left")
                df_sc = df_sc[["Fundo", "Vol_Anual", "Ret_FD_Total_aa"]].copy()
                df_sc = df_sc.dropna(subset=["Vol_Anual", "Ret_FD_Total_aa"])
                df_sc["Vol_pct"] = df_sc["Vol_Anual"] * 100
                df_sc["Ret_pct"] = df_sc["Ret_FD_Total_aa"] * 100
                df_sc["Nome_Curto"] = df_sc["Fundo"].map(shorten)

                # Mapa de cores: fundo alvo com _COR_ALVO, peers com _CORES_PEERS
                short_alvo = shorten(nome_map.get(cnpj_alvo, cnpj_alvo))
                color_map = {short_alvo: _COR_ALVO}
                
                peer_idx = 0
                for nome in df_sc["Nome_Curto"].unique():
                    if nome != short_alvo:
                        color_map[nome] = _CORES_PEERS[peer_idx % len(_CORES_PEERS)]
                        peer_idx += 1

                fig_sc = px.scatter(
                    df_sc, x="Vol_pct", y="Ret_pct",
                    color="Nome_Curto",
                    color_discrete_map=color_map,
                    size_max=12,
                    hover_name="Nome_Curto",
                    labels={"Vol_pct": "Volatilidade Anual (%)", "Ret_pct": "Retorno Anualizado (%)", "Nome_Curto": "Fundo"},
                )
                fig_sc.update_traces(
                    marker=dict(size=12, line=dict(width=1, color="rgba(255,255,255,0.4)")),
                    hovertemplate="<b>%{hovertext}</b><br>Volatilidade: %{x:.2f}%<br>Retorno: %{y:.2f}%<extra></extra>",
                )
                fig_sc.update_layout(
                    **_CHART, height=480,
                    legend=dict(**_LEGEND, title=""),
                    margin=dict(l=0, r=20, t=20, b=10)
                )
                st.plotly_chart(fig_sc, use_container_width=True)
            else:
                st.info("É necessário selecionar peers para exibir o gráfico de dispersão Risco x Retorno.")

    # ── Tabela Completa ───────────────────────────────────────────────────────
    with tab_risco_tbl:
        pct_risco_cols = ["Vol_Diaria", "Vol_Anual", "Ret_FD_12M", "Ret_DI_12M",
                          "Tracking_Error", "VaR_1M", "VaR_12M", "CVaR_1M", "CVaR_12M",
                          "Pior_Mes", "Melhor_Mes", "Menor_Retorno_Dia", "Melhor_Retorno_Dia",
                          "Meses_Positivos_Pct", "Meses_Acima_CDI_Pct"]
        df_r_show = df_r.copy()
        for c in pct_risco_cols:
            if c in df_r_show.columns:
                df_r_show[c] = df_r_show[c] * 100

        col_cfg_r = {
            "Fundo":                   st.column_config.TextColumn("Fundo", width="large"),
            "Vol_Diaria":              st.column_config.NumberColumn("Vol. Diária (%)",     format="%.4f%%"),
            "Vol_Anual":               st.column_config.NumberColumn("Vol. Anual (%)",      format="%.2f%%"),
            "Sharpe":                  st.column_config.NumberColumn("Sharpe",              format="%.3f"),
            "Modigliani":              st.column_config.NumberColumn("Modigliani (%)",      format="%.2f%%"),
            "Information_Ratio":       st.column_config.NumberColumn("Info. Ratio",         format="%.3f"),
            "Tracking_Error":          st.column_config.NumberColumn("Tracking Error (%)",  format="%.4f%%"),
            "VaR_1M":                  st.column_config.NumberColumn("VaR 1M (%)",          format="%.2f%%"),
            "VaR_12M":                 st.column_config.NumberColumn("VaR 12M (%)",         format="%.2f%%"),
            "CVaR_1M":                 st.column_config.NumberColumn("CVaR 1M (%)",         format="%.2f%%"),
            "CVaR_12M":                st.column_config.NumberColumn("CVaR 12M (%)",        format="%.2f%%"),
            "Pior_Mes":                st.column_config.NumberColumn("Pior Mês (%)",        format="%.2f%%"),
            "Pior_Mes_Data":           st.column_config.TextColumn("Pior Mês Data"),
            "Melhor_Mes":              st.column_config.NumberColumn("Melhor Mês (%)",      format="%.2f%%"),
            "Melhor_Mes_Data":         st.column_config.TextColumn("Melhor Mês Data"),
            "Total_Meses":             st.column_config.NumberColumn("Total Meses",         format="%d"),
            "Meses_Positivos_Qtd":     st.column_config.NumberColumn("Meses Pos.",          format="%d"),
            "Meses_Positivos_Pct":     st.column_config.NumberColumn("Meses Pos. (%)",      format="%.1f%%"),
            "Meses_Acima_CDI_Qtd":     st.column_config.NumberColumn("Acima CDI",           format="%d"),
            "Meses_Acima_CDI_Pct":     st.column_config.NumberColumn("Acima CDI (%)",       format="%.1f%%"),
        }
        cols_r = [
            "Fundo", "Vol_Diaria", "Vol_Anual", "Sharpe", "Information_Ratio",
            "Tracking_Error", "VaR_1M", "CVaR_1M", "VaR_12M", "CVaR_12M",
            "Pior_Mes", "Pior_Mes_Data", "Melhor_Mes", "Melhor_Mes_Data",
            "Total_Meses", "Meses_Positivos_Qtd", "Meses_Positivos_Pct",
            "Meses_Acima_CDI_Qtd", "Meses_Acima_CDI_Pct"
        ]
        cols_r = [c for c in cols_r if c in df_r_show.columns]
        st.dataframe(df_r_show[cols_r], hide_index=True,
                     use_container_width=True, column_config=col_cfg_r)

        csv_r = df_r_show[cols_r].to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
        st.download_button(
            "⬇️ Baixar métricas de risco (.csv)", data=csv_r,
            file_name=f"risco_{fundo_alvo_sel[:30]}.csv",
            mime="text/csv",
        )
else:
    st.info("Sem dados de risco disponíveis.")

st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# SEÇÃO 6 — RANKING DE PEERS (retorno 12M)
# ─────────────────────────────────────────────────────────────────────────────
if len(cnpjs_peers) > 0 and not df_acc.empty:
    st.markdown('<div class="section-label">Ranking de Peers — Retorno 12M</div>',
                unsafe_allow_html=True)

    cnpjs_rank = [cnpj_alvo] + list(cnpjs_peers)
    df_rank = df_acc[df_acc["ID_CNPJ_Fundo"].isin(cnpjs_rank)].copy()
    df_rank["Fundo"]  = df_rank["ID_CNPJ_Fundo"].map(nome_map).fillna(df_rank["ID_CNPJ_Fundo"])
    df_rank["Cor"]    = df_rank["ID_CNPJ_Fundo"].apply(
        lambda x: _COR_ALVO if x == cnpj_alvo else "rgba(62,91,125,0.5)"
    )
    df_rank = df_rank.sort_values("Ret_FD_12M", ascending=True)

    fig_rank = go.Figure(go.Bar(
        x=(df_rank["Ret_FD_12M"] * 100).tolist(),
        y=df_rank["Fundo"].tolist(),
        orientation="h",
        marker_color=df_rank["Cor"].tolist(),
        text=[f"{v*100:.2f}%" for v in df_rank["Ret_FD_12M"]],
        textposition="outside",
        textfont=dict(color=PALETTE["text_light"], size=11),
        hovertemplate=(
            "<b>%{y}</b><br>Retorno 12M: <b>%{x:.2f}%</b><extra></extra>"
        ),
    ))
    _mx = df_rank["Ret_FD_12M"].max() if not df_rank.empty else 0.1
    fig_rank.update_layout(
        **_CHART,
        height=max(300, len(df_rank) * 42 + 60),
        margin=dict(l=0, r=80, t=10, b=10),
    )
    fig_rank.update_xaxes(tickformat=".1f", title_text="Retorno 12M (%)",
                          range=[0, max(_mx * 1.25, 0.01)])
    fig_rank.update_yaxes(automargin=True)
    st.plotly_chart(fig_rank, use_container_width=True)
