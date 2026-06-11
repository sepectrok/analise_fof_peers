"""Metrics Cards — Solis Investimentos Platform — Design System v3.0
Paleta e gradientes fiéis ao site solisinvestimentos.com.br
"""

import numpy as np
import pandas as pd
import streamlit as st
from utils.data_loader import TAXA_COLS, TAXA_LABELS, CVNP_COLS, CVNP_LABELS, AGING_COLS, AGING_LABELS
from utils.formatters import fmt_pct, fmt_num


# ─── Gradiente de assinatura (banner do site) ─────────────────────────────────
_GRAD_TITLE = "linear-gradient(125deg, #E8EDF1 0%, #F89B66 59.55%, #FFC36A 97.95%)"
_GRAD_WARM  = "linear-gradient(135deg, #F89B66, #FFC36A)"
_GRAD_SOLIS = "linear-gradient(337deg, #3E5B7D 0%, #899BB7 50.33%, #F89B66 80.95%, #FFC36A 97.95%)"


def page_header(icon: str, title: str, subtitle: str = ""):
    st.markdown(f"""
    <div class="page-header">
        <span class="icon">{icon}</span>
        <div>
            <h1 style="background:{_GRAD_TITLE}; -webkit-background-clip:text;
                       -webkit-text-fill-color:transparent; background-clip:text;
                       display:inline-block; margin:0; padding:0;
                       font-size:1.9rem; font-weight:600; font-family:Figtree,sans-serif;">{title}</h1>
            {"" if not subtitle else f'<p style="margin:6px 0 0 0; font-size:0.82rem; color:#899BB7; font-weight:300;">{subtitle}</p>'}
        </div>
    </div>
    """, unsafe_allow_html=True)


def institutional_header(title: str, subtitle: str = "", logo_path: str = ""):
    import os
    import base64

    logo_html = ""
    # Tenta SVG vertical primeiro, depois PNG
    for candidate in [logo_path, "logo_solis_v.png", "SOLIS_BRANDMARK.png"]:
        if os.path.exists(candidate):
            with open(candidate, "rb") as f:
                b64 = base64.b64encode(f.read()).decode()
            mime = "image/svg+xml" if candidate.endswith(".svg") else "image/png"
            h = "72px" if candidate.endswith(".svg") else "52px"
            logo_html = (
                f'<img src="data:{mime};base64,{b64}" '
                f'style="height:{h}; width:auto; filter:brightness(1.05);" />'
            )
            break

    if not logo_html:
        logo_html = (
            '<span style="font-family:Figtree,sans-serif; font-weight:700; '
            f'font-size:1.3rem; background:{_GRAD_TITLE}; '
            '-webkit-background-clip:text; -webkit-text-fill-color:transparent; '
            'background-clip:text; display:inline-block;">SOLIS</span>'
        )

    st.markdown(f"""
    <div class="inst-header">
        <div>{logo_html}</div>
        <div class="header-text">
            <h1 style="background:{_GRAD_TITLE}; -webkit-background-clip:text;
                       -webkit-text-fill-color:transparent; background-clip:text;
                       display:inline-block; margin:0; padding:0;
                       font-size:1.8rem; font-weight:600; font-family:Figtree,sans-serif;">{title}</h1>
            <p style="margin:6px 0 0 0; font-size:0.85rem;
                      color:var(--text-secondary); font-weight:300;">{subtitle}</p>
        </div>
    </div>
    """, unsafe_allow_html=True)


def kpi_card(label: str, value: str, sub: str = "", delta: str = "",
             delta_up: bool | None = None, card_class: str = "") -> str:
    delta_class = "up" if delta_up else ("down" if delta_up is False else "")
    delta_html  = f'<div class="kpi-delta {delta_class}">{delta}</div>' if delta else ""
    sub_html    = f'<div class="kpi-sub">{sub}</div>' if sub else ""
    return f"""
    <div class="kpi-card {card_class}">
        <div class="kpi-label">{label}</div>
        <div class="kpi-value">{value}</div>
        {sub_html}
        {delta_html}
    </div>
    """


def render_executive_kpis(df_solis: pd.DataFrame, df_mercado: pd.DataFrame):
    """Render the top KPI cards comparing Solis vs Mercado."""
    n_solis   = len(df_solis)
    n_mercado = len(df_mercado)

    med_gestao_solis   = df_solis["taxa_gestao"].mean()   if "taxa_gestao"   in df_solis.columns   else np.nan
    med_gestao_mercado = df_mercado["taxa_gestao"].mean() if "taxa_gestao"   in df_mercado.columns else np.nan

    med_perf_solis   = df_solis["taxa_performance"].mean()   if "taxa_performance" in df_solis.columns   else np.nan
    med_perf_mercado = df_mercado["taxa_performance"].mean() if "taxa_performance" in df_mercado.columns else np.nan

    med_inad_solis = np.nan
    if "PDD" in df_solis.columns and "DC" in df_solis.columns:
        sum_dc = df_solis["DC"].sum()
        if sum_dc > 0:
            med_inad_solis = min(df_solis["PDD"].sum() / sum_dc * 100, 100.0)

    med_inad_mercado = np.nan
    if "PDD" in df_mercado.columns and "DC" in df_mercado.columns:
        sum_dc_mkt = df_mercado["DC"].sum()
        if sum_dc_mkt > 0:
            med_inad_mercado = min(df_mercado["PDD"].sum() / sum_dc_mkt * 100, 100.0)

    def _sub_pond(df_: pd.DataFrame):
        if not {"SB", "MZ", "SR"}.issubset(df_.columns):
            return np.nan, np.nan
        denom = df_["SB"].sum() + df_["MZ"].sum() + df_["SR"].sum()
        if denom == 0:
            return np.nan, np.nan
        return (
            df_["SB"].sum() / denom * 100,
            (df_["SB"].sum() + df_["MZ"].sum()) / denom * 100,
        )

    med_sub_jr_solis,   med_sub_jr_mz_solis   = _sub_pond(df_solis)
    med_sub_jr_mercado, med_sub_jr_mz_mercado = _sub_pond(df_mercado)

    pdd_solis  = df_solis["PDD"].sum()  if "PDD"  in df_solis.columns else 0
    cvnp_solis = df_solis["CVNP"].sum() if "CVNP" in df_solis.columns else 0
    aging_solis = df_solis["Aging"].sum() if "Aging" in df_solis.columns else 0
    def calc_delta(v1, v2):
        if pd.isna(v1) or pd.isna(v2) or v2 == 0:
            return None
        return v1 > v2

    aum_solis   = df_solis["Valor_PL"].sum()   if "Valor_PL" in df_solis.columns   else 0
    aum_mercado = df_mercado["Valor_PL"].sum() if "Valor_PL" in df_mercado.columns else 0
    pdd_med_solis    = df_solis["PDD"].mean()    if "PDD"  in df_solis.columns   else np.nan
    pdd_med_mercado  = df_mercado["PDD"].mean()  if "PDD"  in df_mercado.columns else np.nan
    def fmt_aum(val):
        if pd.isna(val): return "R$ 0,00"
        if val >= 1e9:   return f"R$ {val/1e9:.2f} Bi"
        if val >= 1e6:   return f"R$ {val/1e6:.2f} Mi"
        return f"R$ {val:,.2f}"

    # ── Linha 1 (4 cards) ────────────────────────────────────────────────────
    cards = [
        kpi_card("Fundos Geridos", str(n_solis), "Solis Investimentos",
                 delta=f"vs {n_mercado} no mercado", card_class="kpi-solis"),
        kpi_card("AuM — Patrimônio Líquido", fmt_aum(aum_solis), "Solis Investimentos",
                 delta=f"Mercado (ex-Solis): {fmt_aum(aum_mercado)}",
                 card_class="kpi-solis"),
        kpi_card("Taxa Média de Gestão", fmt_pct(med_gestao_solis), "% a.a. · Solis",
                 delta=f"Mercado: {fmt_pct(med_gestao_mercado)}",
                 delta_up=calc_delta(med_gestao_solis, med_gestao_mercado),
                 card_class="kpi-solis"),
        kpi_card("Taxa Média de Performance", fmt_pct(med_perf_solis), "% a.a. · Solis",
                 delta=f"Mercado: {fmt_pct(med_perf_mercado)}",
                 delta_up=calc_delta(med_perf_solis, med_perf_mercado),
                 card_class="kpi-solis"),
    ]

    # ── Linha 2 (4 cards) ────────────────────────────────────────────────────
    cards_row2 = [
        kpi_card("PDD Total", fmt_aum(pdd_solis), "Provisão Constituída · Solis",
                 card_class="kpi-solis"),
        kpi_card("Inadimplência Média (PDD/DC)", fmt_pct(med_inad_solis), "% · Solis",
                 delta=f"Mercado: {fmt_pct(med_inad_mercado)}",
                 delta_up=calc_delta(med_inad_solis, med_inad_mercado),
                 card_class="kpi-solis"),
        kpi_card("Subordinação Jr.", fmt_pct(med_sub_jr_solis), "% · Solis",
                 delta=f"Mercado: {fmt_pct(med_sub_jr_mercado)}",
                 delta_up=calc_delta(med_sub_jr_solis, med_sub_jr_mercado),
                 card_class="kpi-solis"),
        kpi_card("Subord. Jr + Mez", fmt_pct(med_sub_jr_mz_solis), "% · Solis",
                 delta=f"Mercado: {fmt_pct(med_sub_jr_mz_mercado)}",
                 delta_up=calc_delta(med_sub_jr_mz_solis, med_sub_jr_mz_mercado),
                 card_class="kpi-solis"),
    ]


    cvnp_med_solis   = df_solis["CVNP"].mean()   if "CVNP" in df_solis.columns   else np.nan
    cvnp_med_mercado = df_mercado["CVNP"].mean() if "CVNP" in df_mercado.columns else np.nan

    # ── Linha 3+4 (4 cards) ──────────────────────────────────────────────────
    cards_row34 = [
        kpi_card("Aging Total", fmt_aum(aging_solis), "Aging · Solis",
                 card_class="kpi-solis"),
        kpi_card("CVNP Total", fmt_aum(cvnp_solis), "Crédito Vencido não Pago · Solis",
                 card_class="kpi-solis"),
        kpi_card("PDD Médio / Fundo", fmt_aum(pdd_med_solis), "Média por fundo · Solis",
                 delta=f"Mercado: {fmt_aum(pdd_med_mercado)}", card_class="kpi-solis"),
        kpi_card("CVNP Médio / Fundo", fmt_aum(cvnp_med_solis), "Média por fundo · Solis",
                 delta=f"Mercado: {fmt_aum(cvnp_med_mercado)}", card_class="kpi-solis"),
    ]

    cols1 = st.columns(4)
    for i in range(4):
        with cols1[i]:
            st.markdown(cards[i], unsafe_allow_html=True)

    st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)

    cols2 = st.columns(4)
    for i, card in enumerate(cards_row2):
        with cols2[i]:
            st.markdown(card, unsafe_allow_html=True)

    st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)

    cols3 = st.columns(4)
    for i, card in enumerate(cards_row34):
        with cols3[i]:
            st.markdown(card, unsafe_allow_html=True)


def render_general_kpis(df: pd.DataFrame):
    """Render KPI cards for general market overview — accent amber (kpi-market)."""
    n_fundos = len(df)
    n_adm    = df["administrador"].nunique()
    n_ges    = df["gestor"].nunique()
    n_focos  = df["foco_atuacao"].nunique()

    adm_col  = df["taxa_administracao"] if "taxa_administracao" in df.columns else pd.Series(dtype=float)
    ges_col  = df["taxa_gestao"]        if "taxa_gestao"        in df.columns else pd.Series(dtype=float)
    inad_col = df["taxa_inadimplencia"] if "taxa_inadimplencia" in df.columns else pd.Series(dtype=float)

    med_adm  = adm_col.mean()
    med_ges  = ges_col.mean()

    med_inad = np.nan
    if "PDD" in df.columns and "DC" in df.columns:
        sum_dc = df["DC"].sum()
        if sum_dc > 0:
            med_inad = min(df["PDD"].sum() / sum_dc * 100, 100.0)

    med_pdd  = df["PDD"].mean()  if "PDD"  in df.columns else np.nan
    med_cvnp = df["CVNP"].mean() if "CVNP" in df.columns else np.nan
    med_aging = df["Aging"].mean() if "Aging" in df.columns else np.nan

    def _sub_pond_g(df_: pd.DataFrame):
        if not {"SB", "MZ", "SR"}.issubset(df_.columns):
            return np.nan, np.nan
        denom = df_["SB"].sum() + df_["MZ"].sum() + df_["SR"].sum()
        if denom == 0:
            return np.nan, np.nan
        return (
            df_["SB"].sum() / denom * 100,
            (df_["SB"].sum() + df_["MZ"].sum()) / denom * 100,
        )

    med_sub_jr, med_sub_jr_mz = _sub_pond_g(df)
    aum_total = df["Valor_PL"].sum() if "Valor_PL" in df.columns else 0

    def fmt_aum(val):
        if pd.isna(val): return "R$ 0,00"
        if val >= 1e9:   return f"R$ {val/1e9:.2f} Bi"
        if val >= 1e6:   return f"R$ {val/1e6:.2f} Mi"
        return f"R$ {val:,.2f}"

    cards = [
        kpi_card("AuM Mercado (PL Total)", fmt_aum(aum_total), "Patrimônio Líquido",  card_class="kpi-market"),
        kpi_card("FIDCs Analisados",       str(n_fundos),      f"{n_focos} segmentos", card_class="kpi-market"),
        kpi_card("Administradores",        str(n_adm),         "entidades únicas",     card_class="kpi-market"),
        kpi_card("Gestores",               str(n_ges),         "entidades únicas",     card_class="kpi-market"),
        kpi_card("Média Adm.",             fmt_pct(med_adm),   f"mediana: {fmt_pct(adm_col.median())}", card_class="kpi-market"),
        kpi_card("Média Gestão",           fmt_pct(med_ges),   f"mediana: {fmt_pct(ges_col.median())}", card_class="kpi-market"),
        kpi_card("PDD Médio / Fundo",       fmt_aum(med_pdd),       "Provisão — Média", card_class="kpi-market"),
        kpi_card("Inadimplência Méd. (PDD/DC)", fmt_pct(med_inad), f"mediana: {fmt_pct(inad_col.median())}", card_class="kpi-market"),
        kpi_card("Subordinação Jr.",        fmt_pct(med_sub_jr),    "Ponderada",        card_class="kpi-market"),
        kpi_card("Subord. Jr + Mez",        fmt_pct(med_sub_jr_mz), "Ponderada",        card_class="kpi-market"),
        kpi_card("CVNP Médio / Fundo",      fmt_aum(med_cvnp),      "Créd. Venc. — Média", card_class="kpi-market"),
        kpi_card("Aging Médio / Fundo",       fmt_aum(med_aging),     "Aging — Média", card_class="kpi-market"),
    ]

    cols1 = st.columns(4)
    for i in range(4):
        with cols1[i]:
            st.markdown(cards[i], unsafe_allow_html=True)

    st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)

    cols2 = st.columns(4)
    for i in range(4, 8):
        with cols2[i - 4]:
            st.markdown(cards[i], unsafe_allow_html=True)

    st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)

    cols3 = st.columns(4)
    for i in range(8, 12):
        with cols3[i - 8]:
            st.markdown(cards[i], unsafe_allow_html=True)


def insight_card(icon: str, title: str, text: str, card_type: str = "info") -> str:
    return f"""
    <div class="insight-card {card_type}">
        <span class="ic-icon">{icon}</span>
        <div>
            <div class="ic-title">{title}</div>
            <div class="ic-text">{text}</div>
        </div>
    </div>
    """


def stats_table(series: pd.Series, label: str = ""):
    """Display a clean stats table for a taxa series."""
    s = series.dropna()
    if s.empty:
        st.info("Sem dados suficientes.")
        return

    data = {
        "Estatística": ["Qtd. de Fundos", "Média", "Mediana", "Desvio Padrão",
                        "Mínimo", "P25", "P75", "Máximo"],
        "Valor": [
            f"{len(s):,}",
            fmt_pct(s.mean()),
            fmt_pct(s.median()),
            fmt_pct(s.std()),
            fmt_pct(s.min()),
            fmt_pct(s.quantile(0.25)),
            fmt_pct(s.quantile(0.75)),
            fmt_pct(s.max()),
        ],
    }
    st.dataframe(
        pd.DataFrame(data),
        use_container_width=True,
        hide_index=True,
        column_config={
            "Estatística": st.column_config.TextColumn(width="medium"),
            "Valor":       st.column_config.TextColumn(width="small"),
        },
    )
