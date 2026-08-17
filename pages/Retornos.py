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
from components.charts import PALETTE
from components.returns_common import (
    shorten, fmt_pct, fmt_pct_pos, fmt_x, fmt_num,
    kpi_card as _kpi_card,
    CHART_LAYOUT as _CHART, LEGEND_LAYOUT as _LEGEND,
    COR_ALVO as _COR_ALVO, COR_CDI as _COR_CDI, CORES_PEERS as _CORES_PEERS,
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
def _calcular_tudo(
    cnpj_alvo: str,
    cnpjs_peers: tuple[str, ...],
    data_inicio_str: str,
    data_fim_str: str,
) -> dict:
    """
    Executa todos os cálculos; usa cache por combinação de parâmetros.

    12M/24M/YTD/Total e as métricas de risco (Vol, Sharpe, Tracking Error,
    VaR, CVaR) são calculados sobre o HISTÓRICO COMPLETO disponível de cada
    fundo até data_fim — essas janelas olham para trás a partir de data_fim,
    independentemente da "Data início" escolhida na sidebar. Essa data serve
    apenas para recortar o gráfico de cota indexada, a grade de retornos
    mensais e a coluna de retorno "do período" da tabela comparativa.

    Para o período selecionado, buscamos 5 dias de calendário extra antes de
    data_inicio para garantir ao menos 1 dia útil anterior, permitindo que
    calcular_retorno_diario compute COTA_ad_ftr = PU_t / PU_{t-1} corretamente
    no primeiro dia solicitado.
    """
    cnpjs_todos = list({cnpj_alvo} | set(cnpjs_peers))

    # Carrega histórico já filtrado para os fundos pedidos — o filtro por
    # CNPJ é empurrado para o Polars ANTES do collect(), então não
    # materializamos as ~17M linhas / ~2,5GB da base ANBIMA inteira em pandas
    # (isso estava causando estouro de memória no Streamlit Community Cloud).
    df_hist = _load_historico_cnpjs(tuple(sorted(cnpjs_todos)))
    df_cdi  = _load_cdi()

    data_inicio = pd.to_datetime(data_inicio_str)
    data_fim    = pd.to_datetime(data_fim_str)

    # ── Histórico completo (12M/24M/YTD/Total + métricas de risco) ──────────
    df_hist_completo = df_hist[df_hist["Data_Posicao"] <= data_fim].copy()
    df_ret_completo = calcular_retorno_diario(df_hist_completo, df_cdi, cnpjs=cnpjs_todos)

    df_acc   = calcular_acumulados(df_ret_completo)   if not df_ret_completo.empty else pd.DataFrame()
    df_risco = calcular_metricas_risco(df_ret_completo) if not df_ret_completo.empty else pd.DataFrame()

    # ── Período selecionado (cota indexada, retornos mensais, tabela) ───────
    data_inicio_ext = data_inicio - pd.Timedelta(days=5)
    df_hist_ext = df_hist[
        (df_hist["Data_Posicao"] >= data_inicio_ext) &
        (df_hist["Data_Posicao"] <= data_fim)
    ].copy()
    df_ret_ext = calcular_retorno_diario(df_hist_ext, df_cdi, cnpjs=cnpjs_todos)
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
        max_dates = _load_max_dates()
        cnpjs_com_hist = set(max_dates.index)
        dados_ok = True
    except Exception as e:
        st.error(f"Erro ao carregar dados:\n\n{e}")
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
    #df_peers_sem_hist = df_peers_carteira[~df_peers_carteira["ID_CNPJ_Fundo"].isin(cnpjs_com_hist)]
    #fundos_sem_hist = sorted(df_peers_sem_hist["Nome_Fundo_CVM"].dropna().unique().tolist())
    #
    #if fundos_sem_hist:
    #    with st.expander("Fundos sem Histórico ANBIMA", expanded=False):
    #        st.markdown("Estes fundos não possuem dados históricos para análise:")
    #        for f in fundos_sem_hist:
    #            st.markdown(f"- {shorten(f)}")

    df_peers_com_hist = df_peers_carteira[df_peers_carteira["ID_CNPJ_Fundo"].isin(cnpjs_com_hist)]
    fundos_disponiveis = sorted(df_peers_com_hist["Nome_Fundo_CVM"].dropna().unique().tolist())

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
    max_date_alvo = max_dates.get(cnpj_alvo) if cnpj_alvo else None

    # ── Reseta peers quando o fundo analisado muda ───────────────────────────
    _fundo_prev = st.session_state.get("ret_fundo_alvo_prev", None)
    if _fundo_prev != fundo_alvo_sel:
        # Fundo mudou: limpa seleção de peers para evitar contaminação cruzada
        st.session_state.pop("ret_peers", None)
        st.session_state["ret_fundo_alvo_prev"] = fundo_alvo_sel

    st.markdown("---")

    # ── Peers: herda da aba de Peers ou seleção manual ───────────────────────
    if peers_filtrados:
        peers_nome_options = [
            p["nome"] for p in peers_filtrados
            if p.get("nome") != fundo_alvo_sel and p.get("nome") in fundos_disponiveis
        ]
        peers_default = peers_nome_options[:5]
    else:
        peers_nome_options = [
            p for p in fundos_disponiveis if p != fundo_alvo_sel
        ]
        peers_default = []

    # Garante que os defaults de peers anteriores não vazem para o novo fundo
    _peers_key_val = st.session_state.get("ret_peers", None)
    _peers_default_safe = [
        p for p in (peers_default if _peers_key_val is None else _peers_key_val)
        if p in peers_nome_options
    ]

    st.caption("Peers sem histórico ANBIMA foram descartados automaticamente.")
    peers_sel_nomes = st.multiselect(
        "Peers para comparar",
        options=peers_nome_options,
        default=_peers_default_safe,
        max_selections=5,
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

    avisos_incompletos = []
    for peer_n, peer_c in zip(peers_sel_nomes, cnpjs_peers):
        md = max_dates.get(peer_c)
        if pd.isna(md):
            avisos_incompletos.append(f"- **{shorten(peer_n)}**: Sem histórico ANBIMA")
        elif max_date_alvo is not None and pd.notna(max_date_alvo) and md < max_date_alvo:
            avisos_incompletos.append(f"- **{shorten(peer_n)}**: Dados apenas até {md.strftime('%d/%m/%Y')} (alvo vai até {max_date_alvo.strftime('%d/%m/%Y')})")

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
# ─────────────────────────────────────────────────────────────────────────────
# CÁLCULOS PRINCIPAIS
# ─────────────────────────────────────────────────────────────────────────────
if cnpj_alvo is None:
    st.warning("Selecione um fundo analisado na sidebar.")
    st.stop()

# Dispara cálculo (botão ou mudança de parâmetros via session_state)
chave_calc = (cnpj_alvo, cnpjs_peers, data_inicio_str, data_fim_str)
if "ret_resultado" not in st.session_state or st.session_state.get("ret_chave") != chave_calc:
    with st.spinner("Calculando retornos e métricas de risco…"):
        try:
            resultado = _calcular_tudo(cnpj_alvo, cnpjs_peers, data_inicio_str, data_fim_str)
            st.session_state["ret_resultado"] = resultado
            st.session_state["ret_chave"]     = chave_calc
        except Exception as e:
            st.error(f"Erro no cálculo:\n\n{e}")
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


if avisos_incompletos:
    st.warning("**Aviso de Dados Incompletos:** Os seguintes fundos possuem base histórica defasada em relação ao fundo analisado. Seus retornos absolutos no mês mais recente aparecerão menores do que a realidade.\n\n" + "\n".join(avisos_incompletos))

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
        ("Retorno YTD",    fmt_pct_pos(row.get("Ret_FD_YTD")),
         f"CDI: {fmt_pct_pos(row.get('Ret_DI_YTD'))}"),
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
    # Re-normaliza cada série individualmente: tenta usar o dia anterior ao corte como base 100
    df_idx_viz, teve_antes_map = rebase_cota_indexada(df_idx, _data_corte)

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
        y_title   = "Cota (Base 100)"
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

            # Se o fundo tem histórico antes do corte, ambos (fundo e CDI) foram rebaseados para 100 no dia anterior ao corte.
            # Logo, a base de comparação para o CDI é 100.0.
            # Caso contrário, a base do CDI é o valor do CDI no primeiro ponto da série.
            teve_antes = teve_antes_map.get(cnpj, False)
            if teve_antes:
                cdi_base_val = 100.0
            else:
                cdi_base_val = cdi_alinhado.values[0] if len(cdi_alinhado) > 0 else 100.0

            ret_fd = (serie["Cota_Indexada"].values / 100.0) - 1.0
            if cdi_base_val and not pd.isna(cdi_base_val):
                ret_di = (cdi_alinhado.values / cdi_base_val) - 1.0
            else:
                ret_di = (cdi_alinhado.values / 100.0) - 1.0

            with np.errstate(divide="ignore", invalid="ignore"):
                pct_cdi = np.where(
                    np.abs(ret_di) < 1e-10,
                    np.nan,
                    (ret_fd / ret_di) * 100.0,
                )
            
            # Preenche NaNs (como no primeiro dia caso teve_antes seja False) com o valor do dia útil seguinte
            pct_cdi = pd.Series(pct_cdi).bfill().ffill().fillna(100.0).values

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
    # Usa sempre o histórico completo (df_ret_completo), não o período
    # selecionado na sidebar — assim "Ano" sempre reflete 12 meses reais,
    # mesmo que a "Data início" escolhida seja mais recente que isso.
    _lbl_periodo = {
        "Mês": "1M", "Semestre": "6M", "Ano": "12M", "Todo o período": "Período"
    }.get(periodo_viz, "Período")

    _col_periodo = f"Ret_FD_{_lbl_periodo}_viz"
    _col_cdi_periodo = f"Ret_DI_{_lbl_periodo}_viz"
    _col_pct_cdi_periodo = f"Pct_CDI_{_lbl_periodo}_viz"

    def _acc_periodo(cnpj: str, data_corte: pd.Timestamp) -> tuple:
        """Retorna (ret_fd, ret_di, pct_cdi) acumulado desde data_corte até data_fim."""
        df_r_ = resultado["df_ret_completo"]
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

    # ── Formata para exibição em padrão BR (vírgula decimal) ────────────────
    _lbl_periodo_col   = f"Ret {_lbl_periodo}"
    _lbl_cdi_periodo    = f"CDI {_lbl_periodo}"
    _lbl_pct_periodo    = f"% CDI {_lbl_periodo}"

    df_show = pd.DataFrame({"Fundo": df_tbl["Fundo"]})
    df_show[_lbl_periodo_col] = df_tbl[_col_periodo].apply(fmt_pct_pos)
    df_show[_lbl_cdi_periodo]  = df_tbl[_col_cdi_periodo].apply(fmt_pct_pos)
    df_show[_lbl_pct_periodo]  = df_tbl[_col_pct_cdi_periodo].apply(lambda v: fmt_pct_pos(v, digits=0))
    df_show["YTD"]             = df_tbl["Ret_FD_YTD"].apply(fmt_pct_pos)
    df_show["12M"]             = df_tbl["Ret_FD_12M"].apply(fmt_pct_pos)
    df_show["% CDI 12M"]       = df_tbl["Ret_FD_DI_pct_12M"].apply(lambda v: fmt_pct_pos(v, digits=0))
    df_show["CDI+ 12M"]        = df_tbl["Ret_FD_DI_mais_12M"].apply(lambda v: fmt_pct(v, digits=3))
    df_show["24M"]             = df_tbl["Ret_FD_24M"].apply(fmt_pct_pos)
    df_show["% CDI 24M"]       = df_tbl["Ret_FD_DI_pct_24M"].apply(lambda v: fmt_pct_pos(v, digits=0))
    df_show["Desde o Início"]    = df_tbl["Ret_FD_Total"].apply(fmt_pct_pos)
    df_show["Desde o Início aa"] = df_tbl["Ret_FD_Total_aa"].apply(fmt_pct_pos)
    df_show["% CDI Início"]      = df_tbl["Ret_FD_DI_pct_Total"].apply(lambda v: fmt_pct_pos(v, digits=0))
    df_show["Dias"]              = df_tbl["Dias_total"]

    col_cfg = {
        "Fundo": st.column_config.TextColumn("Fundo", width="large"),
        "Dias":  st.column_config.NumberColumn("Dias", format="%d"),
    }
    st.dataframe(df_show, hide_index=True, use_container_width=True, column_config=col_cfg)

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
  YTD/12M/24M e as métricas de risco desta seção usam sempre o histórico completo
  disponível do fundo até a data fim selecionada — o filtro de "Data início" da sidebar
  afeta apenas o gráfico de cota indexada, a grade de retornos mensais e a coluna
  "do período" da tabela comparativa.
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

                # Calcula bin size adaptativo baseado no range real
                _all_vals = df_mensal_alvo["FD_pct"].dropna()
                _data_range = _all_vals.max() - _all_vals.min()
                if _data_range < 0.1:
                    # Dados muito concentrados: usa bins menores (ex: FIDCs com retorno estável)
                    _bin_size = max(_data_range / 10, 0.01)
                elif _data_range < 1.0:
                    _bin_size = _data_range / 8
                else:
                    # Dados com boa dispersão: usa Sturges rule
                    _n_bins = max(int(np.ceil(np.log2(len(_all_vals)) + 1)), 6)
                    _bin_size = _data_range / _n_bins

                df_pos = df_mensal_alvo[df_mensal_alvo["FD_pct"] >= 0]
                df_neg = df_mensal_alvo[df_mensal_alvo["FD_pct"] < 0]

                fig_hist = go.Figure()
                # Traça histograma completo com coloração condicional via marcadores individuais
                fig_hist.add_trace(go.Histogram(
                    x=df_mensal_alvo["FD_pct"],
                    name="Retornos Mensais",
                    marker_color=[
                        "rgba(16,185,129,0.72)" if v >= 0 else "rgba(239,68,68,0.72)"
                        for v in df_mensal_alvo["FD_pct"]
                    ],
                    marker_line=dict(color="rgba(255,255,255,0.15)", width=0.6),
                    xbins=dict(
                        start=_all_vals.min() - _bin_size,
                        end=_all_vals.max() + _bin_size,
                        size=_bin_size,
                    ),
                    showlegend=False,
                ))

                # Linha vertical: Média do Fundo
                fig_hist.add_vline(
                    x=media_m, line_dash="dash", line_color=PALETTE["amber"], line_width=2,
                    annotation_text=f"Média: {media_m:.3f}%",
                    annotation_font=dict(color=PALETTE["amber"], size=10),
                    annotation_position="top right",
                )
                # Linha vertical: Média CDI
                fig_hist.add_vline(
                    x=cdi_m, line_dash="dot", line_color=_COR_CDI, line_width=1.5,
                    annotation_text=f"CDI Médio: {cdi_m:.3f}%",
                    annotation_font=dict(color=_COR_CDI, size=10),
                    annotation_position="top left",
                )

                fig_hist.update_layout(
                    **_CHART, barmode="overlay",
                    height=340, margin=dict(l=0, r=20, t=45, b=10),
                    legend=dict(**_LEGEND, orientation="h", y=1.04, x=0, yanchor="bottom"),
                    bargap=0.08,
                )
                fig_hist.update_xaxes(title_text="Retorno Mensal (%)", ticksuffix="%")
                fig_hist.update_yaxes(title_text="Frequência (meses)")
                st.plotly_chart(fig_hist, use_container_width=True)

            with col_stats:
                st.markdown('<div class="section-label">Resumo</div>', unsafe_allow_html=True)
                for label, val, cor in [
                    ("Total de Meses",   str(n_total),                                        PALETTE["text"]),
                    ("Meses Positivos",  f"{n_pos} ({fmt_pct_pos(n_pos/n_total, 0)})",         PALETTE["green"]),
                    ("Acima do CDI",     f"{n_acima} ({fmt_pct_pos(n_acima/n_total, 0)})",     PALETTE["amber"]),
                    ("Média Mensal",     fmt_pct(media_m / 100),                               PALETTE["amber"]),
                    ("Desvio-Padrão",    fmt_pct_pos(std_m / 100),                             PALETTE["blue_lt"]),
                    ("Pior Mês",         fmt_pct(df_mensal_alvo['FD_pct'].min() / 100),        PALETTE["red"]),
                    ("Melhor Mês",       fmt_pct(df_mensal_alvo['FD_pct'].max() / 100),        PALETTE["green"]),
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
                fig_sc.update_xaxes(rangemode="normal", autorange=True)
                fig_sc.update_yaxes(rangemode="normal", autorange=True)
                st.plotly_chart(fig_sc, use_container_width=True)
            else:
                st.info("É necessário selecionar peers para exibir o gráfico de dispersão Risco x Retorno.")

    # ── Tabela Completa ───────────────────────────────────────────────────────
    with tab_risco_tbl:
        # ── CSV: mantém valores numéricos (ponto decimal) para compatibilidade ──
        pct_risco_cols = ["Vol_Diaria", "Vol_Anual", "Ret_FD_12M", "Ret_DI_12M",
                          "Tracking_Error", "VaR_1M", "VaR_12M", "CVaR_1M", "CVaR_12M",
                          "Pior_Mes", "Melhor_Mes", "Menor_Retorno_Dia", "Melhor_Retorno_Dia",
                          "Meses_Positivos_Pct", "Meses_Acima_CDI_Pct"]
        df_r_csv = df_r.copy()
        for c in pct_risco_cols:
            if c in df_r_csv.columns:
                df_r_csv[c] = df_r_csv[c] * 100

        cols_r = [
            "Fundo", "Vol_Diaria", "Vol_Anual", "Sharpe", "Information_Ratio",
            "Tracking_Error", "VaR_1M", "CVaR_1M", "VaR_12M", "CVaR_12M",
            "Pior_Mes", "Pior_Mes_Data", "Melhor_Mes", "Melhor_Mes_Data",
            "Total_Meses", "Meses_Positivos_Qtd", "Meses_Positivos_Pct",
            "Meses_Acima_CDI_Qtd", "Meses_Acima_CDI_Pct"
        ]
        cols_r = [c for c in cols_r if c in df_r_csv.columns]

        # ── Exibição em tela: padrão BR (vírgula decimal) ────────────────────
        df_r_disp = pd.DataFrame({"Fundo": df_r["Fundo"]})
        df_r_disp["Vol. Diária (%)"]    = df_r["Vol_Diaria"].apply(lambda v: fmt_pct_pos(v, digits=4))
        df_r_disp["Vol. Anual (%)"]     = df_r["Vol_Anual"].apply(fmt_pct_pos)
        df_r_disp["Sharpe"]             = df_r["Sharpe"].apply(fmt_num)
        df_r_disp["Modigliani (%)"]     = df_r["Modigliani"].apply(fmt_pct_pos)
        df_r_disp["Info. Ratio"]        = df_r["Information_Ratio"].apply(lambda v: fmt_num(v, digits=3))
        df_r_disp["Tracking Error (%)"] = df_r["Tracking_Error"].apply(lambda v: fmt_pct_pos(v, digits=4))
        df_r_disp["VaR 1M (%)"]         = df_r["VaR_1M"].apply(fmt_pct_pos)
        df_r_disp["VaR 12M (%)"]        = df_r["VaR_12M"].apply(fmt_pct_pos)
        df_r_disp["CVaR 1M (%)"]        = df_r["CVaR_1M"].apply(fmt_pct_pos)
        df_r_disp["CVaR 12M (%)"]       = df_r["CVaR_12M"].apply(fmt_pct_pos)
        df_r_disp["Pior Mês (%)"]       = df_r["Pior_Mes"].apply(fmt_pct_pos)
        df_r_disp["Pior Mês Data"]      = df_r["Pior_Mes_Data"]
        df_r_disp["Melhor Mês (%)"]     = df_r["Melhor_Mes"].apply(fmt_pct_pos)
        df_r_disp["Melhor Mês Data"]    = df_r["Melhor_Mes_Data"]
        df_r_disp["Total Meses"]        = df_r["Total_Meses"]
        df_r_disp["Meses Pos."]         = df_r["Meses_Positivos_Qtd"]
        df_r_disp["Meses Pos. (%)"]     = df_r["Meses_Positivos_Pct"].apply(lambda v: fmt_pct_pos(v, digits=1))
        df_r_disp["Acima CDI"]          = df_r["Meses_Acima_CDI_Qtd"]
        df_r_disp["Acima CDI (%)"]      = df_r["Meses_Acima_CDI_Pct"].apply(lambda v: fmt_pct_pos(v, digits=1))

        col_cfg_r = {"Fundo": st.column_config.TextColumn("Fundo", width="large")}
        st.dataframe(df_r_disp, hide_index=True,
                     use_container_width=True, column_config=col_cfg_r)

        csv_r = df_r_csv[cols_r].to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
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
    _mx = (df_rank["Ret_FD_12M"].max() * 100) if not df_rank.empty else 1.0
    _mn = (df_rank["Ret_FD_12M"].min() * 100) if not df_rank.empty else 0.0
    
    padding = (_mx - _mn) * 0.1 if _mx != _mn else 1.0
    range_x = [_mn - padding, _mx + padding]
    
    fig_rank.update_layout(
        **_CHART,
        height=max(300, len(df_rank) * 42 + 60),
        margin=dict(l=0, r=80, t=10, b=10),
    )
    fig_rank.update_xaxes(tickformat=".1f", title_text="Retorno 12M (%)", range=range_x)
    fig_rank.update_yaxes(automargin=True)
    st.plotly_chart(fig_rank, use_container_width=True)

st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# SEÇÃO 7 — EXPORTAR RELATÓRIO PDF DE PEERS
# ─────────────────────────────────────────────────────────────────────────────
st.markdown('<div class="section-label">Exportar Relatório Comparativo</div>',
            unsafe_allow_html=True)

_pdf_col1, _pdf_col2 = st.columns([5, 2])
with _pdf_col1:
    _n_peers = len(cnpjs_peers)
    if _n_peers == 0:
        st.info(
            "Selecione ao menos um peer na sidebar para gerar o relatório comparativo. "
            "Você pode exportar o relatório solo do fundo em **Portfólio do Fundo → Retornos do Fundo**.",
            icon="ℹ️",
        )
    else:
        st.info(
            f"Gera um PDF completo de estudo comparativo do fundo analisado com "
            f"**{_n_peers} peer{'s' if _n_peers > 1 else ''}** selecionado{'s' if _n_peers > 1 else ''}. "
            f"Inclui: capa, retornos acumulados, retornos mensais, métricas de risco e ranking.",
            icon="📄",
        )

with _pdf_col2:
    _btn_disabled = len(cnpjs_peers) == 0
    _btn_pdf = st.button(
        "📄 Gerar PDF de Peers",
        key="ret_btn_pdf",
        disabled=_btn_disabled,
        use_container_width=True,
    )

if _btn_pdf and not _btn_disabled:
    with st.spinner("Gerando relatório PDF de peers…"):
        try:
            from utils.pdf_peers import gerar_pdf_peers
            pdf_bytes = gerar_pdf_peers(
                resultado=resultado,
                cnpj_alvo=cnpj_alvo,
                cnpjs_peers=list(cnpjs_peers),
                nome_map=nome_map,
                data_inicio=data_inicio_str,
                data_fim=data_fim_str,
            )
            nome_arquivo = (
                f"peers_{fundo_alvo_sel[:30].replace(' ', '_')}"
                f"_{data_inicio_str}_{data_fim_str}.pdf"
            )
            st.download_button(
                label="⬇️ Baixar Relatório PDF",
                data=pdf_bytes,
                file_name=nome_arquivo,
                mime="application/pdf",
                key="ret_download_pdf",
            )
            st.success("✅ Relatório gerado com sucesso!")
        except Exception as e:
            st.error(f"Erro ao gerar PDF:\n\n{e}")

