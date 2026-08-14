"""
Solis — Retornos do Fundo (Portfólio > Sub-módulo)
Análise de retornos históricos do próprio fundo, sem comparação com peers.
"""
from __future__ import annotations

import io
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from components.sidebar import load_css
from components.charts import PALETTE
from components.returns_common import (
    shorten, fmt_pct, fmt_pct_pos, fmt_x, fmt_num,
    kpi_card as _kpi_card,
    CHART_LAYOUT as _CHART, LEGEND_LAYOUT as _LEGEND,
    COR_ALVO as _COR_ALVO, COR_CDI as _COR_CDI,
    load_max_dates as _load_max_dates,
    load_historico_cnpjs as _load_historico_cnpjs,
    load_cdi as _load_cdi,
    load_peers_carteira as _load_peers_carteira,
    rebase_cota_indexada,
)
from utils.returns_calc import (
    calcular_retorno_diario,
    calcular_acumulados,
    calcular_retorno_mensal,
    calcular_cota_indexada,
    calcular_metricas_risco,
)

load_css()


@st.cache_data(ttl=1800, show_spinner=False)
def _calcular_solo(
    cnpj_alvo: str,
    data_inicio_str: str,
    data_fim_str: str,
) -> dict:
    """
    Cálculo de retornos/risco apenas para o fundo alvo (sem peers).

    12M/24M/YTD/Total e as métricas de risco são calculados sobre o
    HISTÓRICO COMPLETO disponível do fundo até data_fim — veja a mesma nota
    em pages/Retornos.py::_calcular_tudo.
    """
    # Carrega histórico já filtrado para o fundo pedido — o filtro por CNPJ é
    # empurrado para o Polars ANTES do collect(), então não materializamos as
    # ~17M linhas / ~2,5GB da base ANBIMA inteira em pandas (isso estava
    # causando estouro de memória no Streamlit Community Cloud).
    df_hist = _load_historico_cnpjs((cnpj_alvo,))
    df_cdi  = _load_cdi()

    data_inicio = pd.to_datetime(data_inicio_str)
    data_fim    = pd.to_datetime(data_fim_str)

    # ── Histórico completo (12M/24M/YTD/Total + métricas de risco) ──────────
    df_hist_completo = df_hist[df_hist["Data_Posicao"] <= data_fim].copy()
    df_ret_completo = calcular_retorno_diario(df_hist_completo, df_cdi, cnpjs=[cnpj_alvo])

    df_acc   = calcular_acumulados(df_ret_completo)     if not df_ret_completo.empty else pd.DataFrame()
    df_risco = calcular_metricas_risco(df_ret_completo) if not df_ret_completo.empty else pd.DataFrame()

    # ── Período selecionado (cota indexada, retornos mensais) ───────────────
    data_inicio_ext = data_inicio - pd.Timedelta(days=5)
    df_hist_ext = df_hist[
        (df_hist["Data_Posicao"] >= data_inicio_ext) &
        (df_hist["Data_Posicao"] <= data_fim)
    ].copy()

    df_ret_ext = calcular_retorno_diario(df_hist_ext, df_cdi, cnpjs=[cnpj_alvo])
    df_ret = df_ret_ext[
        (df_ret_ext["Data_Posicao"] >= data_inicio) &
        (df_ret_ext["Data_Posicao"] <= data_fim)
    ].copy()

    if df_ret.empty and df_ret_completo.empty:
        return {}

    df_mensal = calcular_retorno_mensal(df_ret) if not df_ret.empty else pd.DataFrame()
    df_idx    = calcular_cota_indexada(df_ret, df_cdi[
        (df_cdi["Data_Posicao"] >= data_inicio) &
        (df_cdi["Data_Posicao"] <= data_fim)
    ]) if not df_ret.empty else pd.DataFrame()

    return {
        "df_ret":          df_ret,
        "df_ret_completo": df_ret_completo,
        "df_acc":          df_acc,
        "df_mensal":       df_mensal,
        "df_idx":          df_idx,
        "df_risco":        df_risco,
    }


# ─────────────────────────────────────────────────────────────────────────────
# HEADER
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="inst-header">
    <div class="header-text" style="flex:1">
        <h1>Retornos do Fundo</h1>
        <p>Análise histórica de retornos e risco · Dados ANBIMA · Fundo solo</p>
    </div>
</div>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# CARREGAMENTO BASE
# ─────────────────────────────────────────────────────────────────────────────
with st.spinner("Carregando base histórica ANBIMA…"):
    try:
        df_peers_carteira = _load_peers_carteira()
        max_dates = _load_max_dates()
        cnpjs_com_hist = set(max_dates.index)
        dados_ok = True
    except Exception as e:
        st.error(f"Erro ao carregar dados:\n\n{e}")
        dados_ok = False

if not dados_ok:
    st.stop()

# ─────────────────────────────────────────────────────────────────────────────
# SIDEBAR — FILTROS SOLO
# ─────────────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown('<div class="sidebar-section-title">Retornos do Fundo</div>',
                unsafe_allow_html=True)

    df_peers_com_hist = df_peers_carteira[df_peers_carteira["ID_CNPJ_Fundo"].isin(cnpjs_com_hist)]
    fundos_disponiveis = sorted(df_peers_com_hist["Nome_Fundo_CVM"].dropna().unique().tolist())

    # Tenta herdar fundo do Portfolio/Peers via session_state
    fundo_alvo_ss = st.session_state.get("fof_fundo_nome", None)
    idx_default   = 0
    if fundo_alvo_ss and fundo_alvo_ss in fundos_disponiveis:
        idx_default = fundos_disponiveis.index(fundo_alvo_ss)

    fundo_alvo_sel = st.selectbox(
        "Fundo Analisado",
        options=fundos_disponiveis,
        index=idx_default,
        format_func=shorten,
        key="rfundo_fundo_alvo",
    )

    cnpj_alvo = df_peers_carteira.loc[
        df_peers_carteira["Nome_Fundo_CVM"] == fundo_alvo_sel, "ID_CNPJ_Fundo"
    ].iloc[0] if not df_peers_carteira.empty else None

    st.markdown("---")
    st.markdown("**Período de análise**")
    hoje = pd.Timestamp.today().normalize()
    data_inicio_input = st.date_input(
        "Data início",
        value=pd.Timestamp("2026-01-01"),
        key="rfundo_dt_inicio",
    )
    data_fim_input = st.date_input(
        "Data fim",
        value=hoje.date(),
        key="rfundo_dt_fim",
    )

    data_inicio_str = str(data_inicio_input)
    data_fim_str    = str(data_fim_input)

# ─────────────────────────────────────────────────────────────────────────────
# CÁLCULOS
# ─────────────────────────────────────────────────────────────────────────────
if cnpj_alvo is None:
    st.warning("Selecione um fundo na sidebar.")
    st.stop()

chave_calc = (cnpj_alvo, data_inicio_str, data_fim_str)
if "rfundo_resultado" not in st.session_state or st.session_state.get("rfundo_chave") != chave_calc:
    with st.spinner("Calculando retornos e métricas de risco…"):
        try:
            resultado = _calcular_solo(cnpj_alvo, data_inicio_str, data_fim_str)
            st.session_state["rfundo_resultado"] = resultado
            st.session_state["rfundo_chave"]     = chave_calc
        except Exception as e:
            st.error(f"Erro no cálculo:\n\n{e}")
            st.stop()

resultado = st.session_state.get("rfundo_resultado", {})
if not resultado:
    st.warning("Nenhum dado de retorno disponível para os parâmetros selecionados.")
    st.stop()

df_acc    = resultado["df_acc"]
df_mensal = resultado["df_mensal"]
df_idx    = resultado["df_idx"]
df_risco  = resultado["df_risco"]

acc_alvo   = df_acc[df_acc["ID_CNPJ_Fundo"] == cnpj_alvo]
risco_alvo = df_risco[df_risco["ID_CNPJ_Fundo"] == cnpj_alvo]
nome_curto = shorten(fundo_alvo_sel)


# ─────────────────────────────────────────────────────────────────────────────
# SEÇÃO 1 — CARDS KPI
# ─────────────────────────────────────────────────────────────────────────────
st.markdown(
    f'<div class="section-label">{nome_curto}</div>',
    unsafe_allow_html=True,
)

if not acc_alvo.empty:
    row = acc_alvo.iloc[0]
    kpis = [
        ("Retorno YTD",      fmt_pct_pos(row.get("Ret_FD_YTD")),
         f"CDI: {fmt_pct_pos(row.get('Ret_DI_YTD'))}"),
        ("Retorno 12M",      fmt_pct_pos(row.get("Ret_FD_12M")),
         f"CDI: {fmt_pct_pos(row.get('Ret_DI_12M'))}"),
        ("% CDI — 12M",      fmt_x(row.get("Ret_FD_DI_pct_12M")),
         f"CDI+: {fmt_pct(row.get('Ret_FD_DI_mais_12M'))}"),
        ("Retorno 24M",      fmt_pct_pos(row.get("Ret_FD_24M")),
         f"CDI: {fmt_pct_pos(row.get('Ret_DI_24M'))}"),
        ("% CDI — 24M",      fmt_x(row.get("Ret_FD_DI_pct_24M")),
         f"CDI+: {fmt_pct(row.get('Ret_FD_DI_mais_24M'))}"),
        ("Desde o Início",   fmt_pct_pos(row.get("Ret_FD_Total")),
         f"desde {row.get('Data_Inicio').strftime('%d/%m/%Y') if pd.notna(row.get('Data_Inicio')) else '—'}"),
        ("Ret. Início aa",   fmt_pct_pos(row.get("Ret_FD_Total_aa")),
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
# SEÇÃO 2 — COTA INDEXADA vs CDI
# ─────────────────────────────────────────────────────────────────────────────
st.markdown('<div class="section-label">Cota Acumulada vs CDI</div>', unsafe_allow_html=True)

_ctrl_col1, _ctrl_col2 = st.columns([3, 5])
with _ctrl_col1:
    modo_cota = st.radio(
        "Visualização",
        ["Base 100", "% do CDI"],
        horizontal=True,
        label_visibility="collapsed",
        key="rfundo_modo_cota",
    )
with _ctrl_col2:
    _periodo_opts = ["Mês", "Semestre", "Ano", "Todo o período"]
    periodo_viz = st.radio(
        "Período",
        _periodo_opts,
        index=3,
        horizontal=True,
        label_visibility="collapsed",
        key="rfundo_periodo_viz",
    )

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
    df_idx_viz, _ = rebase_cota_indexada(df_idx, _data_corte)
    cdi_idx = df_idx_viz[df_idx_viz["ID_CNPJ_Fundo"] == "__CDI__"].drop_duplicates("Data_Posicao").set_index("Data_Posicao")["Cota_Indexada"]

    if modo_cota == "% do CDI":
        y_title, y_tickfmt = "Retorno em % do CDI", ".0f"
    else:
        y_title, y_tickfmt = "Cota (Base 100)", ".1f"

    fig_idx = go.Figure()
    for cnpj_plot, (hover_fmt_str, dash, cor, lw) in [
        (cnpj_alvo,  ("<b>%{hovertext}</b><br>%{x|%d/%m/%Y}<br>%{y:.2f}<extra></extra>",
                      "solid", _COR_ALVO, 2.5)),
        ("__CDI__",  ("<b>CDI</b><br>%{x|%d/%m/%Y}<br>%{y:.2f}<extra></extra>",
                      "dot", _COR_CDI, 1.5)),
    ]:
        serie = df_idx_viz[df_idx_viz["ID_CNPJ_Fundo"] == cnpj_plot].sort_values("Data_Posicao").copy()
        if serie.empty:
            continue

        if modo_cota == "% do CDI" and cnpj_plot != "__CDI__":
            cdi_alinhado = cdi_idx.reindex(serie["Data_Posicao"].values, fill_value=np.nan)
            cdi_alinhado = pd.Series(cdi_alinhado.values, index=serie["Data_Posicao"].values)
            cdi_alinhado = cdi_alinhado.interpolate(method="linear").ffill().bfill()
            ret_fd = (serie["Cota_Indexada"].values / 100.0) - 1.0
            ret_di = (cdi_alinhado.values / 100.0) - 1.0
            with np.errstate(divide="ignore", invalid="ignore"):
                pct_cdi = np.where(
                    np.abs(ret_di) < 1e-10, np.nan, (ret_fd / ret_di) * 100.0
                )
            serie["Y_plot"] = pd.Series(pct_cdi).bfill().ffill().fillna(100.0).values
            hover_fmt_str = "<b>%{hovertext}</b><br>%{x|%d/%m/%Y}<br>%{y:.1f}% do CDI<extra></extra>"
        elif modo_cota == "% do CDI" and cnpj_plot == "__CDI__":
            continue  # CDI vira linha de referência em 100%
        else:
            serie["Y_plot"] = serie["Cota_Indexada"]

        nome_plot = nome_curto if cnpj_plot == cnpj_alvo else "CDI"
        fig_idx.add_trace(go.Scatter(
            x=serie["Data_Posicao"],
            y=serie["Y_plot"],
            name=nome_plot,
            hovertext=[nome_plot] * len(serie),
            line=dict(color=cor, width=lw, dash=dash),
            hovertemplate=hover_fmt_str,
        ))

    if modo_cota == "% do CDI":
        fig_idx.add_hline(y=100, line_dash="dot", line_color=_COR_CDI, line_width=1,
                          annotation_text="CDI = 100%",
                          annotation_font=dict(color=_COR_CDI, size=9))

    fig_idx.update_layout(
        **_CHART,
        height=400,
        legend=dict(**_LEGEND, orientation="h", y=1.04, x=0, yanchor="bottom"),
        margin=dict(l=0, r=20, t=30, b=10),
    )
    fig_idx.update_yaxes(title_text=y_title, tickformat=y_tickfmt)
    st.plotly_chart(fig_idx, use_container_width=True)
else:
    st.info("Sem dados de cota indexada.")

st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# SEÇÃO 3 — RETORNOS MENSAIS
# ─────────────────────────────────────────────────────────────────────────────
st.markdown('<div class="section-label">Retornos Mensais</div>', unsafe_allow_html=True)

df_alvo_m = df_mensal[df_mensal["ID_CNPJ_Fundo"] == cnpj_alvo].sort_values("Mes").copy()

if not df_alvo_m.empty:
    df_alvo_m["Mes_str"]   = df_alvo_m["Mes"].astype(str)
    df_alvo_m["FD_pct"]    = df_alvo_m["Ret_FD_am"].fillna(0) * 100
    df_alvo_m["DI_pct"]    = df_alvo_m["Ret_DI_am"].fillna(0) * 100
    df_alvo_m["Acima_CDI"] = df_alvo_m["Ret_FD_am"] > df_alvo_m["Ret_DI_am"]

    cores_bar = [PALETTE["green"] if a else PALETTE["red"] for a in df_alvo_m["Acima_CDI"]]

    fig_mensal = go.Figure()
    fig_mensal.add_trace(go.Bar(
        x=df_alvo_m["Mes_str"].tolist(),
        y=df_alvo_m["FD_pct"].tolist(),
        name=nome_curto,
        marker_color=cores_bar,
        text=[f"{v:+.2f}%" for v in df_alvo_m["FD_pct"]],
        textposition="outside",
        textfont=dict(size=8, color=PALETTE["text"]),
        hovertemplate="<b>%{x}</b><br>Fundo: <b>%{y:.3f}%</b><extra></extra>",
    ))
    fig_mensal.add_trace(go.Scatter(
        x=df_alvo_m["Mes_str"].tolist(),
        y=df_alvo_m["DI_pct"].tolist(),
        name="CDI",
        mode="lines+markers",
        line=dict(color=_COR_CDI, width=1.8, dash="dot"),
        marker=dict(size=4, color=_COR_CDI),
        hovertemplate="CDI: %{y:.3f}%<extra></extra>",
    ))
    fig_mensal.update_layout(
        **_CHART, height=370,
        legend=dict(**_LEGEND, orientation="h", y=1.04, x=0, yanchor="bottom"),
        margin=dict(l=0, r=20, t=30, b=40),
    )
    fig_mensal.update_xaxes(tickangle=-45, tickfont=dict(size=9))
    fig_mensal.update_yaxes(title_text="Retorno (%)", ticksuffix="%",
                             zeroline=True, zerolinecolor="rgba(255,255,255,0.15)")
    st.caption("🟢 Acima do CDI  🔴 Abaixo do CDI")
    st.plotly_chart(fig_mensal, use_container_width=True)
else:
    st.info("Sem dados mensais para o fundo selecionado.")

st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# SEÇÃO 4 — DISTRIBUIÇÃO & ESTATÍSTICAS
# ─────────────────────────────────────────────────────────────────────────────
st.markdown('<div class="section-label">Distribuição de Retornos Mensais</div>', unsafe_allow_html=True)

if not df_alvo_m.empty:
    media_m = df_alvo_m["FD_pct"].mean()
    cdi_m   = df_alvo_m["DI_pct"].mean()
    std_m   = df_alvo_m["FD_pct"].std()
    n_total = len(df_alvo_m)
    n_pos   = (df_alvo_m["FD_pct"] >= 0).sum()
    n_acima = df_alvo_m["Acima_CDI"].sum()

    col_hist, col_stats = st.columns([7, 3])

    with col_hist:
        _all_vals   = df_alvo_m["FD_pct"].dropna()
        _data_range = _all_vals.max() - _all_vals.min()
        if _data_range < 0.1:
            _bin_size = max(_data_range / 10, 0.01)
        elif _data_range < 1.0:
            _bin_size = _data_range / 8
        else:
            _n_bins   = max(int(np.ceil(np.log2(len(_all_vals)) + 1)), 6)
            _bin_size = _data_range / _n_bins

        fig_hist = go.Figure()
        fig_hist.add_trace(go.Histogram(
            x=df_alvo_m["FD_pct"],
            name="Retornos Mensais",
            marker_color=[
                "rgba(16,185,129,0.72)" if v >= 0 else "rgba(239,68,68,0.72)"
                for v in df_alvo_m["FD_pct"]
            ],
            marker_line=dict(color="rgba(255,255,255,0.15)", width=0.6),
            xbins=dict(
                start=_all_vals.min() - _bin_size,
                end=_all_vals.max() + _bin_size,
                size=_bin_size,
            ),
            showlegend=False,
        ))
        fig_hist.add_vline(x=media_m, line_dash="dash", line_color=PALETTE["amber"], line_width=2,
                           annotation_text=f"Média: {media_m:.3f}%",
                           annotation_font=dict(color=PALETTE["amber"], size=10),
                           annotation_position="top right")
        fig_hist.add_vline(x=cdi_m, line_dash="dot", line_color=_COR_CDI, line_width=1.5,
                           annotation_text=f"CDI Médio: {cdi_m:.3f}%",
                           annotation_font=dict(color=_COR_CDI, size=10),
                           annotation_position="top left")
        fig_hist.update_layout(
            **_CHART, barmode="overlay",
            height=320, margin=dict(l=0, r=20, t=45, b=10),
            bargap=0.08,
        )
        fig_hist.update_xaxes(title_text="Retorno Mensal (%)", ticksuffix="%")
        fig_hist.update_yaxes(title_text="Frequência (meses)")
        st.plotly_chart(fig_hist, use_container_width=True)

    with col_stats:
        st.markdown('<div class="section-label">Resumo</div>', unsafe_allow_html=True)
        for label, val, cor in [
            ("Total de Meses",   str(n_total),                                    PALETTE["text"]),
            ("Meses Positivos",  f"{n_pos} ({fmt_pct_pos(n_pos/n_total, 0)})",     PALETTE["green"]),
            ("Acima do CDI",     f"{n_acima} ({fmt_pct_pos(n_acima/n_total, 0)})", PALETTE["amber"]),
            ("Média Mensal",     fmt_pct(media_m / 100),                          PALETTE["amber"]),
            ("Desvio-Padrão",    fmt_pct_pos(std_m / 100),                        PALETTE["blue_lt"]),
            ("Pior Mês",         fmt_pct(df_alvo_m['FD_pct'].min() / 100),        PALETTE["red"]),
            ("Melhor Mês",       fmt_pct(df_alvo_m['FD_pct'].max() / 100),        PALETTE["green"]),
        ]:
            st.markdown(_kpi_card(label, val, "", color=cor), unsafe_allow_html=True)
            st.markdown("<div style='height:5px'></div>", unsafe_allow_html=True)
else:
    st.info("Sem dados mensais disponíveis.")

st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# SEÇÃO 5 — MÉTRICAS DE RISCO
# ─────────────────────────────────────────────────────────────────────────────
st.markdown('<div class="section-label">Métricas de Risco</div>', unsafe_allow_html=True)

if not risco_alvo.empty:
    row_r = risco_alvo.iloc[0]
    tab_risco_kpi, tab_risco_tbl = st.tabs(["Destaques", "Tabela Completa"])

    with tab_risco_kpi:
        r_kpis = [
            ("Vol. Anual",       fmt_pct_pos(row_r.get("Vol_Anual")),       "σ_d × √252"),
            ("Sharpe (12M)",     fmt_num(row_r.get("Sharpe")),              "(Ret 12M − CDI) / Vol"),
            ("Inf. Ratio",       fmt_num(row_r.get("Information_Ratio")),   "Alpha Anual / TE"),
            ("Tracking Error",   fmt_pct_pos(row_r.get("Tracking_Error")),  "dp(excesso) × √252"),
            ("VaR 1M (95%)",     fmt_pct_pos(row_r.get("VaR_1M")),         "paramétrico, 21 dias"),
            ("CVaR 1M (95%)",    fmt_pct_pos(row_r.get("CVaR_1M")),        "expected shortfall"),
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

        st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)
        with st.expander("📐 Metodologia das Métricas de Risco", expanded=False):
            st.markdown("""
<div style="font-family:Figtree,sans-serif; font-size:0.85rem; line-height:1.9; color:var(--text-secondary);">

| Métrica | Fórmula | Descrição |
|---|---|---|
| **Vol. Anual** | σ_d × √252 | Desvio-padrão dos retornos diários × √252 |
| **Sharpe (12M)** | (R_fd_12M − R_di_12M) / Vol | Retorno excedente por unidade de risco |
| **Tracking Error** | σ(R_fd_d − R_di_d) × √252 | Dispersão do excesso diário anualizado |
| **Info. Ratio** | (μ_exc × 252) / TE | Consistência da geração de alpha |
| **VaR 1M (95%)** | −(μ_d×21 + σ_d×√21×1,645) | Perda máxima esperada em 1 mês (param.) |
| **CVaR 1M** | −(μ_d×21 + σ_d×√21×ES_z) | Expected shortfall paramétrico |

> Todos os cálculos usam PU_Cota diário reportado à ANBIMA. CDI de referência: DI Over (CETIP).
""", unsafe_allow_html=True)

    with tab_risco_tbl:
        # Exibição em tela: padrão BR (vírgula decimal)
        row_disp = risco_alvo.iloc[0]
        df_r_disp = pd.DataFrame([{
            "CNPJ":                row_disp.get("ID_CNPJ_Fundo"),
            "Vol. Diária (%)":     fmt_pct_pos(row_disp.get("Vol_Diaria"), digits=4),
            "Vol. Anual (%)":      fmt_pct_pos(row_disp.get("Vol_Anual")),
            "Sharpe":              fmt_num(row_disp.get("Sharpe")),
            "Info. Ratio":         fmt_num(row_disp.get("Information_Ratio"), digits=3),
            "Tracking Error (%)":  fmt_pct_pos(row_disp.get("Tracking_Error"), digits=4),
            "VaR 1M (%)":          fmt_pct_pos(row_disp.get("VaR_1M")),
            "CVaR 1M (%)":         fmt_pct_pos(row_disp.get("CVaR_1M")),
            "Pior Mês (%)":        fmt_pct_pos(row_disp.get("Pior_Mes")),
            "Data Pior Mês":       row_disp.get("Pior_Mes_Data"),
            "Melhor Mês (%)":      fmt_pct_pos(row_disp.get("Melhor_Mes")),
            "Total Meses":         row_disp.get("Total_Meses"),
            "Meses Pos.":          row_disp.get("Meses_Positivos_Qtd"),
            "Meses Pos. (%)":      fmt_pct_pos(row_disp.get("Meses_Positivos_Pct"), digits=1),
            "Acima CDI":           row_disp.get("Meses_Acima_CDI_Qtd"),
            "Acima CDI (%)":       fmt_pct_pos(row_disp.get("Meses_Acima_CDI_Pct"), digits=1),
        }])
        st.dataframe(df_r_disp, hide_index=True, use_container_width=True)
else:
    st.info("Sem dados de risco disponíveis para o período selecionado.")

st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# SEÇÃO 6 — EXPORTAR PDF SOLO
# ─────────────────────────────────────────────────────────────────────────────
st.markdown('<div class="section-label">Exportar Relatório</div>', unsafe_allow_html=True)

st.info(
    "Gera um PDF com os retornos e métricas de risco do fundo analisado, "
    "sem comparação com peers.",
    icon="📄",
)

if st.button("📄 Gerar PDF — Relatório do Fundo", key="rfundo_btn_pdf",
             use_container_width=False):
    with st.spinner("Gerando relatório PDF…"):
        try:
            from utils.pdf_peers import gerar_pdf_peers
            nome_map_solo = {cnpj_alvo: nome_curto, "__CDI__": "CDI"}
            pdf_bytes = gerar_pdf_peers(
                resultado=resultado,
                cnpj_alvo=cnpj_alvo,
                cnpjs_peers=[],
                nome_map=nome_map_solo,
                data_inicio=data_inicio_str,
                data_fim=data_fim_str,
            )
            nome_arquivo = f"retornos_{fundo_alvo_sel[:35].replace(' ', '_')}.pdf"
            st.download_button(
                label="⬇️ Baixar PDF",
                data=pdf_bytes,
                file_name=nome_arquivo,
                mime="application/pdf",
                key="rfundo_download_pdf",
            )
        except Exception as e:
            st.error(f"Erro ao gerar PDF:\n\n{e}")
