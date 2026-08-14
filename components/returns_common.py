"""
returns_common.py — Solis Investimentos
Elementos compartilhados entre as páginas de Retornos & Risco (comparativo com
peers) e Retornos do Fundo (solo): tema de gráfico, cartão de KPI, formatação
BR e loaders de dados cacheados. Extraído para eliminar a duplicação quase
integral que existia entre pages/Retornos.py e pages/RetornosFundo.py.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import polars as pl
import streamlit as st

from components.charts import PALETTE
from utils.drive_loader import load_parquet
from utils.formatters import shorten

__all__ = [
    "shorten",
    "fmt_pct", "fmt_pct_pos", "fmt_x", "fmt_num",
    "kpi_card",
    "CHART_LAYOUT", "LEGEND_LAYOUT", "COR_ALVO", "COR_CDI", "CORES_PEERS",
    "load_max_dates", "load_historico_cnpjs", "load_cdi", "load_peers_carteira",
    "rebase_cota_indexada",
]

_HISTORICO_COLS = ["ID_CNPJ_Fundo", "Codigo_Subclasse", "Data_Posicao", "PU_Cota", "PL_Total"]

# ─────────────────────────────────────────────────────────────────────────────
# TEMA DE GRÁFICO (Plotly)
# ─────────────────────────────────────────────────────────────────────────────
CHART_LAYOUT = dict(
    template="plotly_dark",
    separators=",.",  # padrão BR: vírgula decimal, ponto de milhar (afeta ticks/hover nativos do Plotly)
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
LEGEND_LAYOUT = dict(bgcolor="rgba(0,0,0,0)", bordercolor="rgba(0,0,0,0)")

# Cores para séries: fundo alvo sempre dourado, peers em azul/cinza
COR_ALVO = PALETTE["amber"]
COR_CDI  = "rgba(137,155,183,0.6)"
CORES_PEERS = [
    PALETTE["blue"],
    PALETTE["orange"],
    PALETTE["green"],
    PALETTE["blue_lt"],
    "#9B59B6",
    "#1ABC9C",
]


# ─────────────────────────────────────────────────────────────────────────────
# FORMATAÇÃO (padrão BR — vírgula decimal)
# ─────────────────────────────────────────────────────────────────────────────

def fmt_pct(v, digits: int = 2) -> str:
    """Percentual com sinal, vírgula decimal (ex: '+1,23%', '-0,50%')."""
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "—"
    return f"{v * 100:+.{digits}f}".replace(".", ",") + "%"


def fmt_pct_pos(v, digits: int = 2) -> str:
    """Percentual sem sinal, vírgula decimal (ex: '1,23%')."""
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "—"
    return f"{v * 100:.{digits}f}".replace(".", ",") + "%"


def fmt_x(v, digits: int = 2) -> str:
    """Formata como múltiplo do CDI, vírgula decimal (ex: '1,23×')."""
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "—"
    return f"{v:.{digits}f}".replace(".", ",") + "×"


def fmt_num(v, digits: int = 2) -> str:
    """Número simples, vírgula decimal (ex: '1,23')."""
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "—"
    return f"{v:.{digits}f}".replace(".", ",")


def kpi_card(label: str, value: str, delta: str = "",
             color: str = PALETTE["amber"], width: str = "100%") -> str:
    text_color = PALETTE["text"]
    delta_html = (
        f"<div style='font-size:0.72rem;color:{text_color};margin-top:2px'>{delta}</div>"
        if delta else ""
    )
    return f"""
    <div style="
        background:rgba(26,58,82,0.55);
        border:1px solid rgba(255,195,106,0.15);
        border-radius:12px;
        padding:16px 20px;
        min-height:90px;
        width:{width};
    ">
        <div style="font-size:0.68rem;text-transform:uppercase;letter-spacing:1px;
                    color:{text_color};margin-bottom:6px">{label}</div>
        <div style="font-size:1.55rem;font-weight:700;color:{color};
                    font-family:Figtree,sans-serif;line-height:1.1">{value}</div>
        {delta_html}
    </div>"""


# ─────────────────────────────────────────────────────────────────────────────
# CARREGAMENTO DE DADOS (com cache compartilhado entre as duas páginas)
# ─────────────────────────────────────────────────────────────────────────────

@st.cache_data(ttl=3600, show_spinner=False)
def load_max_dates() -> pd.Series:
    """
    Última data disponível por fundo (índice = ID_CNPJ_Fundo).

    O parquet `historico_anbima` tem ~17M linhas / ~560MB (histórico completo,
    sem filtro de data — necessário para 12M/24M/YTD). Carregar tudo em pandas
    só para descobrir "quais fundos têm histórico e até quando" já consumiu
    ~2,5GB de RAM sozinho, estourando o limite do Streamlit Community Cloud.
    Aqui filtramos para 2 colunas e agregamos (max) ANTES do collect(), então
    só o resultado (1 linha por fundo) é materializado em pandas.
    """
    # Esta é a única consulta que ainda varre as ~17M linhas inteiras (para achar
    # o max por fundo); engine="streaming" processa em lotes e reduz o pico de
    # RAM observado em ~2,5x (~1,6GB → ~620MB) em teste com a base completa.
    lf = load_parquet("historico_anbima")
    df = (
        lf.select(["ID_CNPJ_Fundo", "Data_Posicao"])
          .group_by("ID_CNPJ_Fundo")
          .agg(pl.col("Data_Posicao").max())
          .collect(engine="streaming")
          .to_pandas()
    )
    df["Data_Posicao"] = pd.to_datetime(df["Data_Posicao"], errors="coerce")
    return df.set_index("ID_CNPJ_Fundo")["Data_Posicao"]


@st.cache_data(ttl=3600, show_spinner=False)
def load_historico_cnpjs(cnpjs: tuple[str, ...]) -> pd.DataFrame:
    """
    Carrega o histórico ANBIMA apenas para os CNPJs informados.

    O filtro `is_in(cnpjs)` é aplicado no plano lazy do Polars ANTES do
    `.collect()` (predicate pushdown), então apenas as linhas dos fundos
    pedidos (tipicamente o fundo alvo + até 3 peers) chegam a virar pandas —
    de ~17M linhas / ~2,5GB para tipicamente algumas milhares de linhas /
    poucos MB. `cnpjs` precisa ser uma tupla (hashável) para o cache do
    Streamlit funcionar corretamente.
    """
    lf = load_parquet("historico_anbima")
    df = (
        lf.select(_HISTORICO_COLS)
          .filter(pl.col("ID_CNPJ_Fundo").is_in(list(cnpjs)))
          .collect()
          .to_pandas()
    )
    df["Data_Posicao"] = pd.to_datetime(df["Data_Posicao"], errors="coerce")
    df["PU_Cota"]      = pd.to_numeric(df["PU_Cota"],      errors="coerce")
    df["PL_Total"]     = pd.to_numeric(df["PL_Total"],     errors="coerce")
    return df


@st.cache_data(ttl=3600, show_spinner=False)
def load_cdi() -> pd.DataFrame:
    lf = load_parquet("cdi")
    df = lf.collect().to_pandas()
    df["Data_Posicao"] = pd.to_datetime(df["Data_Posicao"], errors="coerce")
    for c in ("DI_aa", "DI_ad", "DI_aa_ftr", "DI_ad_ftr"):
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


@st.cache_data(ttl=3600, show_spinner=False)
def load_peers_carteira() -> pd.DataFrame:
    lf = load_parquet("fundos_peers_carteira")
    return lf.select(["ID_CNPJ_Fundo", "Nome_Fundo_CVM"]).unique().collect().to_pandas()


# ─────────────────────────────────────────────────────────────────────────────
# COTA INDEXADA — REBASE PARA O PERÍODO DE VISUALIZAÇÃO
# ─────────────────────────────────────────────────────────────────────────────

def rebase_cota_indexada(
    df_idx: pd.DataFrame,
    data_corte: pd.Timestamp,
) -> tuple[pd.DataFrame, dict]:
    """
    Re-normaliza cada série de cota indexada para base 100 no último dia
    disponível antes de `data_corte` (ou no primeiro ponto >= `data_corte`,
    se não houver dado anterior), e recorta para o período visível.

    Retorna (df_idx_viz, teve_antes_map), onde `teve_antes_map` indica, por
    ID_CNPJ_Fundo, se havia dado anterior ao corte disponível para o rebase
    (usado para decidir a base de comparação do CDI no modo "% do CDI").
    """
    frames_rebased = []
    teve_antes_map: dict = {}

    for cnpj, grp in df_idx.groupby("ID_CNPJ_Fundo"):
        grp = grp.sort_values("Data_Posicao").copy()

        grp_antes = grp[grp["Data_Posicao"] < data_corte]
        if not grp_antes.empty:
            base_val = grp_antes["Cota_Indexada"].iloc[-1]
            teve_antes_map[cnpj] = True
        else:
            grp_depois = grp[grp["Data_Posicao"] >= data_corte]
            base_val = grp_depois["Cota_Indexada"].iloc[0] if not grp_depois.empty else 1.0
            teve_antes_map[cnpj] = False

        grp_viz = grp[grp["Data_Posicao"] >= data_corte].copy()
        if not grp_viz.empty:
            if base_val and base_val != 0:
                grp_viz["Cota_Indexada"] = grp_viz["Cota_Indexada"] / base_val * 100.0
            frames_rebased.append(grp_viz)

    df_idx_viz = pd.concat(frames_rebased, ignore_index=True) if frames_rebased else pd.DataFrame()
    return df_idx_viz, teve_antes_map
