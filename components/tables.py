"""Analytical Tables — FIDC Analytics Platform"""

import io
import numpy as np
import pandas as pd
import streamlit as st
from utils.data_loader import TAXA_COLS, TAXA_LABELS, CVNP_COLS, CVNP_LABELS, AGING_COLS, AGING_LABELS
from utils.formatters import fmt_pct


def _style_pct_cols(val):
    """Color-code percentage values for table display."""
    try:
        v = float(val)
        if v <= 0:
            return ""
        return ""
    except Exception:
        return ""


def render_analytical_table(df: pd.DataFrame, key: str = "tbl"):
    """Full analytical table with search, sort and export."""
    display_cols = ["nome_curto", "foco_atuacao", "administrador", "gestor"]
    if "Valor_PL" in df.columns: display_cols.append("Valor_PL")
    if "Valor_PL_Medio" in df.columns: display_cols.append("Valor_PL_Medio")
    display_cols += [c for c in TAXA_COLS if c in df.columns]
    if "taxa_inadimplencia" in df.columns: display_cols.append("taxa_inadimplencia")
    if "PDD" in df.columns: display_cols.append("PDD")
    if "DC" in df.columns: display_cols.append("DC")
    if "CLU" in df.columns: display_cols.append("CLU")
    if "SB" in df.columns: display_cols.append("SB")
    if "MZ" in df.columns: display_cols.append("MZ")
    if "SR" in df.columns: display_cols.append("SR")
    if "Sub_JR" in df.columns: display_cols.append("Sub_JR")
    if "Sub_JR_MZ" in df.columns: display_cols.append("Sub_JR_MZ")
    if "CVNP" in df.columns: display_cols.append("CVNP")
    if "Aging" in df.columns: display_cols.append("Aging")
    # Faixas de CVNP (aging)
    display_cols += [c for c in CVNP_COLS if c in df.columns]
    display_cols += [c for c in AGING_COLS if c in df.columns]

    df_disp = df[display_cols].copy()
    df_disp.rename(columns={
        "nome_curto":         "Fundo",
        "foco_atuacao":       "Foco",
        "administrador":      "Administrador",
        "gestor":             "Gestor",
        "Valor_PL":           "PL Atual",
        "Valor_PL_Medio":     "PL Médio",
        "taxa_inadimplencia": "Inadimplência (PDD/DC)",
        "PDD":                "PDD (R$)",
        "DC":                 "DC (R$)",
        "CLU":                "Cota Única (R$)",
        "SB":                 "Subordinada (R$)",
        "MZ":                 "Mezanino (R$)",
        "SR":                 "Sênior (R$)",
        "Sub_JR":             "Sub. Júnior (%)",
        "Sub_JR_MZ":          "Sub. Mez+Jr (%)",
        "CVNP":               "CVNP Total (R$)",
        "Aging":              "Aging Total (R$)",
        **{c: TAXA_LABELS.get(c, c) for c in TAXA_COLS},
        **{c: CVNP_LABELS.get(c, c) + " (R$)" for c in CVNP_COLS},
        **{c: AGING_LABELS.get(c, c) + " (R$)" for c in AGING_COLS},
    }, inplace=True)

    # Search
    search = st.text_input("🔍 Busca por nome do fundo, administrador ou gestor",
                           key=f"{key}_search", placeholder="Digite para filtrar...")
    if search:
        mask = df_disp.apply(lambda row: row.astype(str).str.contains(search, case=False).any(), axis=1)
        df_disp = df_disp[mask]

    st.markdown(f"<small style='color:var(--text-muted)'>{len(df_disp)} registros</small>",
                unsafe_allow_html=True)

    # Column config for pct formatting
    col_cfg = {
        "Fundo":         st.column_config.TextColumn(width="large"),
        "Foco":          st.column_config.TextColumn(width="medium"),
        "Administrador": st.column_config.TextColumn(width="medium"),
        "Gestor":        st.column_config.TextColumn(width="medium"),
    }
    if "PL Atual" in df_disp.columns:
        col_cfg["PL Atual"] = st.column_config.NumberColumn("PL Atual", format="R$ %d")
    if "PL Médio" in df_disp.columns:
        col_cfg["PL Médio"] = st.column_config.NumberColumn("PL Médio", format="R$ %d")
    for c in TAXA_COLS:
        lbl = TAXA_LABELS.get(c, c)
        if lbl in df_disp.columns:
            col_cfg[lbl] = st.column_config.NumberColumn(
                lbl, format="%.3f%%", width="small"
            )
    if "Inadimplência (PDD/DC)" in df_disp.columns:
        col_cfg["Inadimplência (PDD/DC)"] = st.column_config.NumberColumn(
            "Inadimplência (PDD/DC)", format="%.2f%%", width="small"
        )
    if "PDD (R$)" in df_disp.columns:
        col_cfg["PDD (R$)"] = st.column_config.NumberColumn("PDD (R$)", format="R$ %d", width="medium")
    if "DC (R$)" in df_disp.columns:
        col_cfg["DC (R$)"] = st.column_config.NumberColumn("DC (R$)", format="R$ %d", width="medium")
    if "Cota Única (R$)" in df_disp.columns:
        col_cfg["Cota Única (R$)"] = st.column_config.NumberColumn("Cota Única (R$)", format="R$ %d", width="medium")
    if "Subordinada (R$)" in df_disp.columns:
        col_cfg["Subordinada (R$)"] = st.column_config.NumberColumn("Subordinada (R$)", format="R$ %d", width="medium")
    if "Mezanino (R$)" in df_disp.columns:
        col_cfg["Mezanino (R$)"] = st.column_config.NumberColumn("Mezanino (R$)", format="R$ %d", width="medium")
    if "Sênior (R$)" in df_disp.columns:
        col_cfg["Sênior (R$)"] = st.column_config.NumberColumn("Sênior (R$)", format="R$ %d", width="medium")
    if "Sub. Júnior (%)" in df_disp.columns:
        col_cfg["Sub. Júnior (%)"] = st.column_config.NumberColumn("Sub. Júnior", format="%.2f%%", width="small")
    if "Sub. Mez+Jr (%)" in df_disp.columns:
        col_cfg["Sub. Mez+Jr (%)"] = st.column_config.NumberColumn("Sub. Mez+Jr", format="%.2f%%", width="small")
    if "CVNP Total (R$)" in df_disp.columns:
        col_cfg["CVNP Total (R$)"] = st.column_config.NumberColumn("CVNP Total", format="R$ %d", width="medium")
    if "Aging Total (R$)" in df_disp.columns:
        col_cfg["Aging Total (R$)"] = st.column_config.NumberColumn("Aging Total", format="R$ %d", width="medium")
    
    col_cfg["CVNP Total (R$)"] = st.column_config.NumberColumn("CVNP Total (R$)", format="R$ %,.0f", width="medium")
    col_cfg["Aging Total (R$)"] = st.column_config.NumberColumn("Aging Total (R$)", format="R$ %,.0f", width="medium")
    for c in CVNP_COLS:
        lbl = CVNP_LABELS.get(c, c) + " (R$)"
        if lbl in df_disp.columns:
            col_cfg[lbl] = st.column_config.NumberColumn(lbl, format="R$ %,.0f", width="medium")
    for c in AGING_COLS:
        lbl = AGING_LABELS.get(c, c) + " (R$)"
        if lbl in df_disp.columns:
            col_cfg[lbl] = st.column_config.NumberColumn(lbl, format="R$ %,.0f", width="medium")

    st.dataframe(df_disp, use_container_width=True, hide_index=True,
                 column_config=col_cfg, height=460)

    return df_disp


def render_entity_ranking(df_agg: pd.DataFrame, entity_col: str,
                           count_col: str = "n_fundos", key: str = "rank", taxa_col_to_show: str = None):
    """Ranking table for admins/gestors."""
    taxa_labels = {c: TAXA_LABELS.get(c, c).replace("Taxa de ", "") for c in TAXA_COLS}
    
    if taxa_col_to_show and taxa_col_to_show in df_agg.columns:
        present = [taxa_col_to_show]
    else:
        present = [c for c in TAXA_COLS if c in df_agg.columns]
        
    rename_map = {entity_col: "Entidade", count_col: "Nº Fundos"}
    rename_map.update({c: taxa_labels[c] for c in present})

    df_disp = df_agg.rename(columns=rename_map).copy()
    
    display_cols = ["Entidade", "Nº Fundos"] + [taxa_labels[c] for c in present]
    df_disp = df_disp[display_cols]

    col_cfg = {"Entidade": st.column_config.TextColumn(width="large"),
               "Nº Fundos": st.column_config.NumberColumn(width="small", format="%d")}
    for c in present:
        col_cfg[taxa_labels[c]] = st.column_config.NumberColumn(
            taxa_labels[c], format="%.3f%%", width="small"
        )

    st.dataframe(df_disp, use_container_width=True, hide_index=True,
                 column_config=col_cfg, height=400)


def export_buttons(df: pd.DataFrame, label: str = "dados_fidc"):
    """CSV and Excel download buttons."""
    c1, c2 = st.columns(2)

    csv_data = df.to_csv(index=False, sep=";", decimal=",", encoding="utf-8-sig")
    with c1:
        st.download_button(
            "⬇ Exportar CSV",
            data=csv_data.encode("utf-8-sig"),
            file_name=f"{label}.csv",
            mime="text/csv",
        )

    with c2:
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="FIDC Analytics")
        buf.seek(0)
        st.download_button(
            "⬇ Exportar Excel",
            data=buf.read(),
            file_name=f"{label}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
