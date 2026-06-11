"""
Data Loader — FIDC Analytics Platform
Carrega e transforma os dados de regulamentos analisados em df_fidc consolidado.
"""

import os
import re
import numpy as np
import pandas as pd
import streamlit as st

# ─── Paths ────────────────────────────────────────────────────────────────────
BASE_DIR              = os.path.dirname(os.path.dirname(__file__))
DATA_FILE             = os.path.join(BASE_DIR, "regulamentos_analisados.xlsx")
RESP_FILE             = os.path.join(BASE_DIR, "responsaveis_fundo.xlsx")
PL_FILE               = os.path.join(BASE_DIR, "base_pl_fundos.xlsx")
INADIMPLENCIA_FILE    = os.path.join(BASE_DIR, "CVM_Carteira_202603 1.xlsx")

# ─── Mapeamento de tipos de taxa ───────────────────────────────────────────────
TAXA_MAP = [
    ("administra",   "taxa_administracao"),
    ("gestao",       "taxa_gestao"),
    ("gestã",        "taxa_gestao"),
    ("custodia",     "taxa_custodia"),
    ("custódia",     "taxa_custodia"),
    ("performance",  "taxa_performance"),
    ("desempenho",   "taxa_performance"),
    ("distribui",    "taxa_distribuicao"),
    ("servicing",    "taxa_servicing"),
    ("servicer",     "taxa_servicing"),
]

TAXA_COLS = [
    "taxa_administracao",
    "taxa_gestao",
    "taxa_custodia",
    "taxa_performance",
    "taxa_distribuicao",
]

TAXA_LABELS = {
    "taxa_administracao": "Taxa de Administração",
    "taxa_gestao":        "Taxa de Gestão",
    "taxa_custodia":      "Taxa de Custódia",
    "taxa_performance":   "Taxa de Performance",
    "taxa_distribuicao":  "Taxa de Distribuição",
    "taxa_servicing":     "Taxa de Servicing",
}

# Faixas de cnpj de crédito vencido não pago (CVNP)
CVNP_COLS = [
    "CVNP_1_a_30",
    "CVNP_31_a_60",
    "CVNP_61_a_90",
    "CVNP_91_a_120",
    "CVNP_121_a_150",
    "CVNP_151_a_180",
    "CVNP_181_a_360",
    "CVNP_360_mais",

]

CVNP_LABELS = {
    "CVNP_1_a_30":    "CVNP_1-30 dias",
    "CVNP_31_a_60":   "CVNP_31-60 dias",
    "CVNP_61_a_90":   "CVNP_61-90 dias",
    "CVNP_91_a_120":  "CVNP_91-120 dias",
    "CVNP_121_a_150": "CVNP_121-150 dias",
    "CVNP_151_a_180": "CVNP_151-180 dias",
    "CVNP_181_a_360": "CVNP_181-360 dias",
    "CVNP_360_mais":  "CVNP_360+ dias",
}

AGING_COLS = [
    "Aging_1_a_30",
    "Aging_31_a_60",
    "Aging_61_a_90",
    "Aging_91_a_120",
    "Aging_121_a_150",
    "Aging_151_a_180",
    "Aging_181_a_360",
    "Aging_360_mais",

]

AGING_LABELS = {
    "Aging_1_a_30":    "AGING_1-30 dias",
    "Aging_31_a_60":   "AGING_31-60 dias",
    "Aging_61_a_90":   "AGING_61-90 dias",
    "Aging_91_a_120":  "AGING_91-120 dias",
    "Aging_121_a_150": "AGING_121-150 dias",
    "Aging_151_a_180": "AGING_151-180 dias",
    "Aging_181_a_360": "AGING_181-360 dias",
    "Aging_360_mais":  "AGING_360+ dias",
}
# ─── Helpers ───────────────────────────────────────────────────────────────────

def _ascii_lower(s: str) -> str:
    """Lowercase + remove common accents for matching."""
    s = s.lower()
    for a, b in [("ã", "a"), ("á", "a"), ("â", "a"), ("à", "a"),
                 ("ó", "o"), ("ô", "o"), ("ú", "u"), ("é", "e"),
                 ("ê", "e"), ("í", "i"), ("ç", "c"), ("õ", "o")]:
        s = s.replace(a, b)
    return s


def parse_taxa_pct(valor) -> float:
    """Parse raw taxa string → float (% a.a.). Ignores R$ values."""
    if pd.isna(valor):
        return np.nan
    s = str(valor).strip()
    if "%" not in s:
        return np.nan
    # Remove suffixes
    s = re.sub(r"%\s*a\.?\s*a\.?", "", s, flags=re.IGNORECASE)
    s = re.sub(r"%\s*ao\s*ano",    "", s, flags=re.IGNORECASE)
    s = re.sub(r"%\s*a\.?\s*m\.?", "", s, flags=re.IGNORECASE)
    s = s.replace("%", "").strip()
    # Handle ranges "0,10 a 0,50" → mean
    if re.search(r"\s+a\s+", s, re.IGNORECASE):
        parts = re.split(r"\s+a\s+", s, flags=re.IGNORECASE)
        try:
            return float(np.mean([float(p.replace(",", ".").strip()) for p in parts]))
        except Exception:
            return np.nan
    try:
        return float(s.replace(",", "."))
    except Exception:
        return np.nan


def normalize_tipo_taxa(tipo) -> str | None:
    """Normalize tipo_taxa string → standard column name."""
    if pd.isna(tipo):
        return None
    t = _ascii_lower(str(tipo))
    for keyword, col in TAXA_MAP:
        kw = _ascii_lower(keyword)
        if kw in t:
            return col
    return None


# ─── Data Loading ──────────────────────────────────────────────────────────────

@st.cache_data(ttl=3600, show_spinner=False)
def load_raw_data() -> pd.DataFrame:
    return pd.read_excel(DATA_FILE)


def load_responsaveis() -> pd.DataFrame:
    """
    Carrega a tabela auxiliar de responsáveis por fundo.
    Normaliza o CNPJ para string de 14 dígitos (zfill) para garantir join correto.
    """
    df_resp = pd.read_excel(RESP_FILE)
    df_resp["cnpj_str"] = (
        df_resp["ID_CNPJ_Fundo"]
        .astype(str).str.strip().str.zfill(14)
    )
    # Deduplicar: um CNPJ pode ter múltiplas linhas — manter a primeira
    return df_resp.drop_duplicates("cnpj_str").set_index("cnpj_str")

def load_inadimplencia() -> pd.DataFrame:
    """
    Carrega a base de carteira CVM e calcula duas métricas de inadimplência:
      - taxa_inadimplencia    (PDD / DC)       × 100 — concentração da PDD sobre DC em atraso
      - taxa_inadimplencia_pl (PDD / Carteira) × 100 — peso da PDD sobre o PL total do fundo
    Fundos com DC = 0 ou Carteira <= 0 recebem NaN.
    """
    df_inad = pd.read_excel(INADIMPLENCIA_FILE)
    df_inad["cnpj_str"] = (
        pd.to_numeric(df_inad["ID_CNPJ_Fundo"], errors="coerce")
        .dropna()
        .astype(int).astype(str).str.strip().str.zfill(14)
    )
    df_inad = df_inad[df_inad["cnpj_str"].notna()]
    # Metodologia 1: PDD / DC (direitos creditórios em atraso)
    df_inad["taxa_inadimplencia"] = np.where(
        df_inad["DC"] > 0,
        (df_inad["PDD"] / df_inad["DC"] * 100).clip(upper=100),
        np.nan,
    )
    # Metodologia 2: PDD / PL (carteira total do fundo)
    df_inad["taxa_inadimplencia_pl"] = np.where(
        df_inad["PL_CVM"] > 0,
        (df_inad["PDD"] / df_inad["PL_CVM"] * 100).clip(upper=100),
        np.nan,
    )
    df_inad['Valor_PL'] = df_inad['PL_CVM']

    # Cotas de tranche (valores em R$) — base para calcular subordinação
    # clip(lower=0): cotas negativas são erro de dados da CVM (ex: fundo com PL negativo
    # que lança SR negativo). Tratamos como 0 para não distorcer o denominador.
    for col in ["SB", "MZ", "SR","CLU"]:
        df_inad[col] = pd.to_numeric(df_inad[col], errors="coerce").fillna(0).clip(lower=0)

    # Subordinação calculada pela fórmula (não usa a coluna pré-calculada do Excel)
    #   Sub_JR    = SB / (SB + MZ + SR)
    #   Sub_JR_MZ = (SB + MZ) / (SB + MZ + SR)
    _denom = df_inad["SB"] + df_inad["MZ"] + df_inad["SR"]
    df_inad["Sub_JR"]    = np.where(_denom > 0, df_inad["SB"]                      / _denom * 100, np.nan)
    df_inad["Sub_JR_MZ"] = np.where(_denom > 0, (df_inad["SB"] + df_inad["MZ"]) / _denom * 100, np.nan)


    # Garantir que colunas CVNP são numéricas
    cols_cvnp_presentes = [c for c in ["CVNP"] + CVNP_COLS if c in df_inad.columns]
    for c in cols_cvnp_presentes:
        df_inad[c] = pd.to_numeric(df_inad[c], errors="coerce").fillna(0)

    # Garantir que colunas Aging são numéricas
    cols_aging_presentes = [c for c in ["Aging"] + AGING_COLS if c in df_inad.columns]
    for c in cols_aging_presentes:
        df_inad[c] = pd.to_numeric(df_inad[c], errors="coerce").fillna(0)

    # Tratamentod da data
    df_inad["Data_Posicao"] = pd.to_datetime(df_inad["Data_Posicao"], errors="coerce")

    cols_base = ["Data_Posicao", "cnpj_str", "taxa_inadimplencia", "taxa_inadimplencia_pl",
                 "PDD", "DC", "PL_CVM", "Valor_PL", "Situacao", "Check_PL",
                 "Sub_JR", "Sub_JR_MZ",
                 "SB", "MZ", "SR","CLU"]      # tranches brutas para agregação ponderada
    cols_final = cols_base + cols_cvnp_presentes + cols_aging_presentes
    return df_inad[[c for c in cols_final if c in df_inad.columns]]


# ─── Subordinação ponderada por volume de tranche ─────────────────────────────

def calc_subordinacao_ponderada(df: pd.DataFrame) -> dict:
    """
    Calcula Sub_JR e Sub_JR_MZ ponderados pelo volume financeiro das tranches.

    Fórmula:
        Sub_JR    = Σ(SB)       / Σ(SB + MZ + SR)  × 100
        Sub_JR_MZ = Σ(SB + MZ) / Σ(SB + MZ + SR)  × 100

    Requer colunas 'SB', 'MZ', 'SR' no DataFrame (valores em R$).
    Retorna NaN quando denominador é zero ou colunas ausentes.
    """
    needed = {"SB", "MZ", "SR"}
    if not needed.issubset(df.columns):
        return {"Sub_JR": np.nan, "Sub_JR_MZ": np.nan}
    denom = df["SB"].sum() + df["MZ"].sum() + df["SR"].sum()
    if denom == 0:
        return {"Sub_JR": np.nan, "Sub_JR_MZ": np.nan}
    return {
        "Sub_JR":    df["SB"].sum() / denom * 100,
        "Sub_JR_MZ": (df["SB"].sum() + df["MZ"].sum()) / denom * 100,
    }


def add_subordinacao_ponderada(df_agg: pd.DataFrame,
                               df_raw: pd.DataFrame,
                               groupby_col: str) -> pd.DataFrame:
    """
    Adiciona colunas Sub_JR e Sub_JR_MZ ponderadas a um DataFrame já agregado.

    Parâmetros
    ----------
    df_agg      : DataFrame agregado (uma linha por grupo)
    df_raw      : DataFrame com linhas individuais de fundos (contém SB, MZ, SR)
    groupby_col : coluna de agrupamento (ex: 'gestor', 'administrador', 'foco_atuacao')

    Retorna df_agg com colunas Sub_JR e Sub_JR_MZ calculadas corretamente.
    """
    needed = {"SB", "MZ", "SR", groupby_col}
    if not needed.issubset(df_raw.columns):
        df_agg = df_agg.copy()
        df_agg["Sub_JR"]    = np.nan
        df_agg["Sub_JR_MZ"] = np.nan
        return df_agg

    sub_sums = df_raw.groupby(groupby_col)[["SB", "MZ", "SR"]].sum()
    denom = sub_sums["SB"] + sub_sums["MZ"] + sub_sums["SR"]
    sub_sums["Sub_JR"]    = np.where(denom > 0, sub_sums["SB"]                        / denom * 100, np.nan)
    sub_sums["Sub_JR_MZ"] = np.where(denom > 0, (sub_sums["SB"] + sub_sums["MZ"]) / denom * 100, np.nan)

    df_agg = df_agg.copy()
    df_agg["Sub_JR"]    = df_agg[groupby_col].map(sub_sums["Sub_JR"])
    df_agg["Sub_JR_MZ"] = df_agg[groupby_col].map(sub_sums["Sub_JR_MZ"])
    return df_agg


@st.cache_data(ttl=3600, show_spinner=False)
def build_df_fidc() -> pd.DataFrame:
    """
    Build the consolidated df_fidc DataFrame:
    - One row per FIDC (cnpj_tratado)
    - Columns: taxa_administracao, taxa_gestao, taxa_custodia,
               taxa_performance, taxa_distribuicao  (avg of tiers)
    - Plus: nome_fundo, foco_atuacao, data_regulamento,
            administrador, gestor, nome_curto
    """
    df = load_raw_data()

    # Parse & normalize
    df["_taxa_val"] = df["taxa_pct"].apply(parse_taxa_pct)
    df["_tipo_norm"] = df["tipo_taxa"].apply(normalize_tipo_taxa)

    # Filter valid rows
    df_v = df[df["_taxa_val"].notna() & df["_tipo_norm"].notna()].copy()

    # Clamp extreme outliers per tipo: performance can be 10-30%, others capped at 10%
    NON_PERF = ["taxa_administracao", "taxa_gestao", "taxa_custodia",
                "taxa_distribuicao", "taxa_servicing"]
    
    # User Request: remove taxa_performance == 0% or taxa_gestao/taxa_administracao > 5%
    mask_perf_zero = (df_v["_tipo_norm"] == "taxa_performance") & (df_v["_taxa_val"] == 0)
    mask_gest_adm_high = (df_v["_tipo_norm"].isin(["taxa_gestao", "taxa_administracao"])) & (df_v["_taxa_val"] > 5)
    
    df_v = df_v[~mask_perf_zero].copy()
    df_v = df_v[~mask_gest_adm_high].copy()

    mask_perf  = df_v["_tipo_norm"] == "taxa_performance"
    mask_other = df_v["_tipo_norm"].isin(NON_PERF)
    df_v = df_v[~( mask_other & (df_v["_taxa_val"] > 10) )].copy()
    df_v = df_v[~( mask_perf  & (df_v["_taxa_val"] > 50) )].copy()

    # Aggregate tiered rates → mean per fund per tipo
    agg = (
        df_v.groupby(["cnpj_tratado", "_tipo_norm"])["_taxa_val"]
        .mean()
        .reset_index()
    )

    # Pivot → wide
    wide = agg.pivot_table(
        index="cnpj_tratado",
        columns="_tipo_norm",
        values="_taxa_val",
        aggfunc="mean",
    ).reset_index()

    # Metadata: first occurrence per CNPJ
    meta_cols = ["cnpj_tratado", "nome_fundo", "Foco_Atuacao", "data_regulamento"]
    meta = (
        df[meta_cols]
        .drop_duplicates("cnpj_tratado")
        .set_index("cnpj_tratado")
    )
    meta['nome_fundo'] = meta['nome_fundo'].str.upper().str.replace(r"FUNDO DE INVESTIMENTO EM DIREITOS CREDITÓRIOS \(\"FIDC\"\)", "", regex=True)
    # Join
    df_fidc = wide.set_index("cnpj_tratado").join(meta).reset_index()
    df_fidc.rename(columns={"Foco_Atuacao": "foco_atuacao"}, inplace=True)

    # ── Administrador / Gestor — tabela auxiliar responsaveis_fundo.xlsx ────────
    # Normaliza CNPJ do fundo para string de 14 dígitos e faz join com a tabela
    # oficial, que contém administrador e gestor corretos por CNPJ.
    df_resp = load_responsaveis()
    df_fidc["_cnpj_str"] = (
        df_fidc["cnpj_tratado"].astype(str).str.strip().str.zfill(14)
    )
    df_fidc["administrador"] = df_fidc["_cnpj_str"].map(
        df_resp["Administrador_Razao_Social"].str.upper()
    )
    df_fidc["gestor"] = df_fidc["_cnpj_str"].map(
        df_resp["Gestor_Razao_Social"].str.upper()
    )
    df_fidc.drop(columns=["_cnpj_str"], inplace=True)
    
    # Usuário solicitou remoção dos fundos que não foram encontrados na tabela de responsáveis (sem fallback)
    df_fidc.dropna(subset=["administrador", "gestor"], how="all", inplace=True)

    # Ensure all TAXA_COLS exist
    for col in TAXA_COLS:
        if col not in df_fidc.columns:
            df_fidc[col] = np.nan

    # Preservar taxas originais (sem imputação) para análise comparativa
    # NaN = fundo sem taxa explícita no regulamento
    if "taxa_gestao" in df_fidc.columns:
        df_fidc["taxa_gestao_raw"] = df_fidc["taxa_gestao"].copy()
    else:
        df_fidc["taxa_gestao_raw"] = np.nan

    if "taxa_administracao" in df_fidc.columns:
        df_fidc["taxa_administracao_raw"] = df_fidc["taxa_administracao"].copy()
    else:
        df_fidc["taxa_administracao_raw"] = np.nan

    # Imputação de taxas faltantes pela média da respectiva entidade
    if "taxa_gestao" in df_fidc.columns and "gestor" in df_fidc.columns:
        df_fidc["taxa_gestao"] = df_fidc.groupby("gestor")["taxa_gestao"].transform(lambda x: x.fillna(x.mean()))

    if "taxa_administracao" in df_fidc.columns and "administrador" in df_fidc.columns:
        df_fidc["taxa_administracao"] = df_fidc.groupby("administrador")["taxa_administracao"].transform(lambda x: x.fillna(x.mean()))

    # Clean-ups
    df_fidc["nome_fundo"]   = df_fidc["nome_fundo"].fillna("Fundo sem nome")
    df_fidc["foco_atuacao"] = df_fidc["foco_atuacao"].fillna("Não informado")
    
    # Normalizar foco de atuação (maiúsculas/minúsculas)
    def normalizar_foco(x):
        s = str(x).strip().lower()
        if s.startswith("não se aplica") or s.startswith("nao se aplica"): return "Não se aplica"
        if s == "multicarteira outros": return "Multicarteira Outros"
        if "agro" in s and "multicarteira" in s: return "Multicarteira Agro, Indústria e Comércio"
        if s == "sem classificacao anbima" or s == "sem classificação anbima": return "Sem Classificação ANBIMA"
        return str(x).strip()
    
    df_fidc["foco_atuacao"] = df_fidc["foco_atuacao"].apply(normalizar_foco)
    df_fidc["data_regulamento"] = pd.to_datetime(
        df_fidc["data_regulamento"], format="%d/%m/%Y", errors="coerce"
    )
    df_fidc["nome_curto"] = df_fidc["nome_fundo"].apply(
        lambda x: str(x)[:55] + "…" if len(str(x)) > 55 else str(x)
    )
    
    df_fidc["cnpj_str"] = df_fidc["cnpj_tratado"].astype(str).str.strip().str.zfill(14)
    # ── Inadimplência (PDD / DC) e PL ──────────────────────────────────────────────────
    df_inad = load_inadimplencia()
    df_fidc = pd.merge(df_fidc, df_inad, on="cnpj_str", how="inner")
    df_fidc.drop(columns=["cnpj_str"], inplace=True)

    return df_fidc


# ─── Filter helpers ────────────────────────────────────────────────────────────

def apply_filters(df: pd.DataFrame,
                  focos: list | None = None,
                  administradores: list | None = None,
                  gestores: list | None = None) -> pd.DataFrame:
    f = df.copy()
    if focos:
        f = f[f["foco_atuacao"].isin(focos)]
    if administradores:
        f = f[f["administrador"].isin(administradores)]
    if gestores:
        f = f[f["gestor"].isin(gestores)]
    return f


def get_available_taxas(df: pd.DataFrame) -> list[str]:
    return [c for c in TAXA_COLS if c in df.columns and df[c].notna().sum() >= 5]
