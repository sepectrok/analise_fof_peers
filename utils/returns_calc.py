"""
returns_calc.py — Solis Investimentos
Cálculo de retornos e métricas de risco a partir de dados ANBIMA.
Tradução fiel da lógica do script R (codigo_retorno_r.txt).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import norm


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS INTERNOS
# ─────────────────────────────────────────────────────────────────────────────

def _prod_ftr(s: pd.Series) -> float:
    """Produto dos fatores diários, tratando NaN como 1 (sem variação)."""
    return s.fillna(1.0).prod()


def _anualizar_vol(vol_diaria: float, base: int = 252) -> float:
    return vol_diaria * np.sqrt(base)


def _var_param(media: float, vol: float, dias: int, ic: float = 0.95) -> float:
    z = norm.ppf(ic)
    return -(media * dias + vol * np.sqrt(dias) * z)


def _cvar_param(media: float, vol: float, dias: int, ic: float = 0.95) -> float:
    z = norm.ppf(ic)
    es_z = norm.pdf(z) / (1 - ic)
    return -(media * dias + vol * np.sqrt(dias) * es_z)


# ─────────────────────────────────────────────────────────────────────────────
# 1. RETORNO DIÁRIO
# ─────────────────────────────────────────────────────────────────────────────

def calcular_retorno_diario(
    df_historico: pd.DataFrame,
    df_cdi: pd.DataFrame,
    cnpjs: list[str] | None = None,
) -> pd.DataFrame:
    """
    Calcula retornos diários para cada fundo (ID_CNPJ_Fundo × Codigo_Subclasse).

    Colunas esperadas em df_historico:
        ID_CNPJ_Fundo, Codigo_Subclasse, Data_Posicao, PU_Cota, PL_Total

    Colunas esperadas em df_cdi:
        Data_Posicao, DI_aa, DI_ad, DI_aa_ftr, DI_ad_ftr

    Parameters
    ----------
    df_historico : pd.DataFrame
    df_cdi       : pd.DataFrame
    cnpjs        : lista de CNPJs a filtrar (None = todos)

    Returns
    -------
    pd.DataFrame com colunas adicionais de retorno diário.
    """
    df = df_historico.copy()

    # Garantir tipos
    df["Data_Posicao"] = pd.to_datetime(df["Data_Posicao"], errors="coerce")
    df["PU_Cota"]      = pd.to_numeric(df["PU_Cota"],      errors="coerce")
    df["PL_Total"]     = pd.to_numeric(df["PL_Total"],     errors="coerce")

    cdi = df_cdi.copy()
    cdi["Data_Posicao"] = pd.to_datetime(cdi["Data_Posicao"], errors="coerce")
    for c in ("DI_aa", "DI_ad", "DI_aa_ftr", "DI_ad_ftr"):
        cdi[c] = pd.to_numeric(cdi[c], errors="coerce")

    if cnpjs is not None:
        df = df[df["ID_CNPJ_Fundo"].isin(cnpjs)].copy()

    df = df[["ID_CNPJ_Fundo", "Codigo_Subclasse", "Data_Posicao", "PU_Cota", "PL_Total"]].copy()

    # Ordenar e calcular fator de cota diário dentro de cada série
    df = df.sort_values(["ID_CNPJ_Fundo", "Codigo_Subclasse", "Data_Posicao"])
    df["COTA_ad_ftr"] = df.groupby(["ID_CNPJ_Fundo", "Codigo_Subclasse"])["PU_Cota"].transform(
        lambda s: s / s.shift(1)
    )
    df["COTA_ad"]     = df["COTA_ad_ftr"] - 1
    df["COTA_aa_ftr"] = df["COTA_ad_ftr"] ** 252
    df["COTA_aa"]     = df["COTA_aa_ftr"] - 1

    # Join com CDI
    df = df.merge(cdi, on="Data_Posicao", how="left")

    # Remove primeiro dia de cada série quando COTA_ad_ftr é NaN
    # (fundo sem histórico anterior — equivale ao filtro `Inicio` do R)
    primeiro_dia = df.groupby(["ID_CNPJ_Fundo", "Codigo_Subclasse"])["Data_Posicao"].transform("min")
    mask_inicio  = (df["Data_Posicao"] == primeiro_dia) & df["COTA_ad_ftr"].isna()
    df = df[~mask_inicio].copy()

    return df


# ─────────────────────────────────────────────────────────────────────────────
# 2. ACUMULADOS
# ─────────────────────────────────────────────────────────────────────────────

def calcular_acumulados(df_retorno: pd.DataFrame) -> pd.DataFrame:
    """
    Calcula retornos acumulados por período para cada fundo.

    Retorna um DataFrame com uma linha por (ID_CNPJ_Fundo, Codigo_Subclasse)
    contendo:
        - Ret_FD_12M, Ret_DI_12M, Ret_FD_DI_pct_12M
        - Ret_FD_24M, Ret_DI_24M, Ret_FD_DI_pct_24M
        - Ret_FD_Total, Ret_DI_Total, Ret_FD_DI_pct_Total
        - Ret_FD_Total_aa, Ret_DI_Total_aa
        - Dias_total, Data_Inicio, Data_Fim
        - Ret_FD_DI_mais_12M, Ret_FD_DI_mais_24M, Ret_FD_DI_mais_Total
    """
    results = []

    for (cnpj, sub), grp in df_retorno.groupby(["ID_CNPJ_Fundo", "Codigo_Subclasse"]):
        grp = grp.sort_values("Data_Posicao")

        data_max = grp["Data_Posicao"].max()
        data_min = grp["Data_Posicao"].min()
        dias_total = len(grp)

        # Janelas
        inicio_12m = data_max - pd.DateOffset(months=12)
        inicio_24m = data_max - pd.DateOffset(months=24)

        grp_12m = grp[grp["Data_Posicao"] >= inicio_12m]
        grp_24m = grp[grp["Data_Posicao"] >= inicio_24m]

        def _acc(g, col_ftr):
            return _prod_ftr(g[col_ftr]) - 1

        ret_fd_12m  = _acc(grp_12m, "COTA_ad_ftr")
        ret_di_12m  = _acc(grp_12m, "DI_ad_ftr")
        ret_fd_24m  = _acc(grp_24m, "COTA_ad_ftr")
        ret_di_24m  = _acc(grp_24m, "DI_ad_ftr")
        ret_fd_tot  = _acc(grp,     "COTA_ad_ftr")
        ret_di_tot  = _acc(grp,     "DI_ad_ftr")

        def _pct(fd, di):
            return (fd / di) if di != 0 else np.nan

        def _mais(fd, di):
            return ((1 + fd) / (1 + di) - 1) if di != -1 else np.nan

        # Acumulados mensais (último valor de cada mês)
        grp_m = grp.copy()
        grp_m["Mes"] = grp_m["Data_Posicao"].dt.to_period("M")
        # Mantém apenas o último dia de cada mês para calcular retornos mensais consolidados
        mensais = (
            grp_m.groupby("Mes", group_keys=False)
            .apply(lambda g: pd.Series({
                "Ret_FD_am": _prod_ftr(g["COTA_ad_ftr"]) - 1,
                "Ret_DI_am": _prod_ftr(g["DI_ad_ftr"]) - 1,
                "Mes_Data":  g["Data_Posicao"].max(),
            }))
            .reset_index()
        )

        # Retorno anualizado total
        ret_fd_tot_aa = (1 + ret_fd_tot) ** (252 / dias_total) - 1 if dias_total > 0 else np.nan
        ret_di_tot_aa = (1 + ret_di_tot) ** (252 / dias_total) - 1 if dias_total > 0 else np.nan

        results.append({
            "ID_CNPJ_Fundo":       cnpj,
            "Codigo_Subclasse":    sub,
            "Data_Inicio":         data_min,
            "Data_Fim":            data_max,
            "Dias_total":          dias_total,
            # 12M
            "Ret_FD_12M":                   ret_fd_12m,
            "Ret_DI_12M":                   ret_di_12m,
            "Ret_FD_DI_pct_12M":            _pct(ret_fd_12m, ret_di_12m),
            "Ret_FD_DI_mais_12M":           _mais(ret_fd_12m, ret_di_12m),
            "Dias_12M":                     len(grp_12m),
            # 24M
            "Ret_FD_24M":                   ret_fd_24m,
            "Ret_DI_24M":                   ret_di_24m,
            "Ret_FD_DI_pct_24M":            _pct(ret_fd_24m, ret_di_24m),
            "Ret_FD_DI_mais_24M":           _mais(ret_fd_24m, ret_di_24m),
            "Dias_24M":                     len(grp_24m),
            # Inception
            "Ret_FD_Total":                 ret_fd_tot,
            "Ret_DI_Total":                 ret_di_tot,
            "Ret_FD_DI_pct_Total":          _pct(ret_fd_tot, ret_di_tot),
            "Ret_FD_DI_mais_Total":         _mais(ret_fd_tot, ret_di_tot),
            "Ret_FD_Total_aa":              ret_fd_tot_aa,
            "Ret_DI_Total_aa":              ret_di_tot_aa,
        })

    return pd.DataFrame(results)


# ─────────────────────────────────────────────────────────────────────────────
# 3. RETORNO MENSAL (matriz para heatmap)
# ─────────────────────────────────────────────────────────────────────────────

def calcular_retorno_mensal(df_retorno: pd.DataFrame) -> pd.DataFrame:
    """
    Retorna DataFrame com retorno mensal acumulado por fundo.
    Colunas: ID_CNPJ_Fundo, Codigo_Subclasse, Mes (Period[M]),
             Ret_FD_am, Ret_DI_am, Ret_FD_DI_pct_am.
    """
    df = df_retorno.copy()
    df["Mes"] = df["Data_Posicao"].dt.to_period("M")

    mensais = (
        df.groupby(["ID_CNPJ_Fundo", "Codigo_Subclasse", "Mes"])
        .apply(lambda g: pd.Series({
            "Ret_FD_am": _prod_ftr(g["COTA_ad_ftr"]) - 1,
            "Ret_DI_am": _prod_ftr(g["DI_ad_ftr"]) - 1,
        }), include_groups=False)
        .reset_index()
    )
    mensais["Ret_FD_DI_pct_am"] = mensais.apply(
        lambda r: (r["Ret_FD_am"] / r["Ret_DI_am"]) if r["Ret_DI_am"] != 0 else np.nan,
        axis=1,
    )
    return mensais


# ─────────────────────────────────────────────────────────────────────────────
# 4. COTA INDEXADA (base 100)
# ─────────────────────────────────────────────────────────────────────────────

def calcular_cota_indexada(
    df_retorno: pd.DataFrame,
    df_cdi: pd.DataFrame,
    base: float = 100.0,
) -> pd.DataFrame:
    """
    Retorna cota acumulada indexada a `base` na primeira data disponível,
    para cada fundo e para o CDI.

    Returns
    -------
    pd.DataFrame com colunas:
        Data_Posicao, ID_CNPJ_Fundo, Codigo_Subclasse, Cota_Indexada
    Mais uma série especial com ID_CNPJ_Fundo == '__CDI__'.
    """
    frames = []

    for (cnpj, sub), grp in df_retorno.groupby(["ID_CNPJ_Fundo", "Codigo_Subclasse"]):
        grp = grp.sort_values("Data_Posicao").copy()
        # Cota indexada: produto acumulado dos fatores, normalizado para `base`
        grp["Cota_Indexada"] = base * grp["COTA_ad_ftr"].fillna(1.0).cumprod()
        grp["ID_CNPJ_Fundo"]    = cnpj
        grp["Codigo_Subclasse"] = sub
        frames.append(grp[["Data_Posicao", "ID_CNPJ_Fundo", "Codigo_Subclasse", "Cota_Indexada"]])

    if not frames:
        return pd.DataFrame()

    df_idx = pd.concat(frames, ignore_index=True)

    # CDI acumulado sobre o mesmo período
    data_min = df_idx["Data_Posicao"].min()
    data_max = df_idx["Data_Posicao"].max()
    cdi_periodo = df_cdi[
        (df_cdi["Data_Posicao"] >= data_min) &
        (df_cdi["Data_Posicao"] <= data_max)
    ].sort_values("Data_Posicao").copy()

    if not cdi_periodo.empty:
        cdi_periodo["Cota_Indexada"]    = base * cdi_periodo["DI_ad_ftr"].fillna(1.0).cumprod()
        cdi_periodo["ID_CNPJ_Fundo"]    = "__CDI__"
        cdi_periodo["Codigo_Subclasse"] = "__CDI__"
        df_idx = pd.concat(
            [df_idx, cdi_periodo[["Data_Posicao", "ID_CNPJ_Fundo", "Codigo_Subclasse", "Cota_Indexada"]]],
            ignore_index=True,
        )

    return df_idx


# ─────────────────────────────────────────────────────────────────────────────
# 5. MÉTRICAS DE RISCO
# ─────────────────────────────────────────────────────────────────────────────

def calcular_metricas_risco(
    df_retorno: pd.DataFrame,
    ic: float = 0.95,
) -> pd.DataFrame:
    """
    Calcula métricas de risco para cada (ID_CNPJ_Fundo, Codigo_Subclasse).

    Métricas calculadas (espelhando o bloco R):
        Vol_Diaria, Vol_Anual
        Ret_FD_12M, Ret_DI_12M  (base do Sharpe)
        Sharpe, Modigliani
        Information_Ratio, Tracking_Error
        VaR_1M, VaR_12M, CVaR_1M, CVaR_12M
        Pior_Mes, Pior_Mes_Data, Melhor_Mes, Melhor_Mes_Data
        Menor_Retorno_Dia, Menor_Retorno_Dia_Data
        Melhor_Retorno_Dia, Melhor_Retorno_Dia_Data
        Total_Meses, Meses_Positivos_Qtd, Meses_Positivos_Pct
        Meses_Acima_CDI_Qtd, Meses_Acima_CDI_Pct
    """
    results = []

    for (cnpj, sub), grp in df_retorno.groupby(["ID_CNPJ_Fundo", "Codigo_Subclasse"]):
        grp = grp.sort_values("Data_Posicao").copy()
        grp["Ret_Exc_CDI_ad"] = grp["COTA_ad"] - grp["DI_ad"]

        data_max   = grp["Data_Posicao"].max()
        inicio_12m = data_max - pd.DateOffset(months=12)
        grp_12m    = grp[grp["Data_Posicao"] >= inicio_12m]

        # ── Volatilidade ──────────────────────────────────────────────────────
        vol_diaria  = grp["COTA_ad"].std(ddof=1)
        vol_anual   = _anualizar_vol(vol_diaria)
        media_diaria = grp["COTA_ad"].mean()

        # ── Retornos 12M (base do Sharpe) ─────────────────────────────────────
        ret_fd_12m = _prod_ftr(grp_12m["COTA_ad_ftr"]) - 1
        ret_di_12m = _prod_ftr(grp_12m["DI_ad_ftr"])   - 1

        # ── Sharpe ────────────────────────────────────────────────────────────
        sharpe = (ret_fd_12m - ret_di_12m) / vol_anual if vol_anual != 0 else np.nan

        # ── Modigliani ────────────────────────────────────────────────────────
        vol_di_anual = _anualizar_vol(grp["DI_ad"].std(ddof=1))
        modigliani   = sharpe * vol_di_anual + ret_di_12m if not np.isnan(sharpe) else np.nan

        # ── Information Ratio / Tracking Error ───────────────────────────────
        # Tracking Error = desvio-padrão diário do excesso, anualizado (×√252)
        tracking_error_diario  = grp["Ret_Exc_CDI_ad"].std(ddof=1)
        tracking_error         = tracking_error_diario * np.sqrt(252)  # anualizado
        # Alpha anualizado: média diária do excesso × 252
        alpha_anualizado       = grp["Ret_Exc_CDI_ad"].mean() * 252
        information_ratio      = (alpha_anualizado / tracking_error
                                  if tracking_error != 0 else np.nan)

        # ── VaR / CVaR ───────────────────────────────────────────────────────
        var_1m   = _var_param(media_diaria, vol_diaria,  21,  ic)
        var_12m  = _var_param(media_diaria, vol_diaria,  252, ic)
        cvar_1m  = _cvar_param(media_diaria, vol_diaria, 21,  ic)
        cvar_12m = _cvar_param(media_diaria, vol_diaria, 252, ic)

        # ── Retornos mensais ──────────────────────────────────────────────────
        grp["Mes_Data"] = grp["Data_Posicao"].dt.to_period("M")
        mensais = (
            grp.groupby("Mes_Data")
            .apply(lambda g: pd.Series({
                "Ret_FD_am": _prod_ftr(g["COTA_ad_ftr"]) - 1,
                "Ret_DI_am": _prod_ftr(g["DI_ad_ftr"])   - 1,
            }), include_groups=False)
            .reset_index()
        )

        total_meses  = len(mensais)
        meses_pos    = (mensais["Ret_FD_am"] > 0).sum()
        meses_cdi    = (mensais["Ret_FD_am"] > mensais["Ret_DI_am"]).sum()

        if not mensais.empty:
            idx_pior    = mensais["Ret_FD_am"].idxmin()
            idx_melhor  = mensais["Ret_FD_am"].idxmax()
            pior_mes        = mensais.loc[idx_pior,   "Ret_FD_am"]
            pior_mes_data   = str(mensais.loc[idx_pior,   "Mes_Data"])
            melhor_mes      = mensais.loc[idx_melhor, "Ret_FD_am"]
            melhor_mes_data = str(mensais.loc[idx_melhor, "Mes_Data"])
        else:
            pior_mes = melhor_mes = np.nan
            pior_mes_data = melhor_mes_data = ""

        # ── Extremos diários ──────────────────────────────────────────────────
        grp_nonan = grp.dropna(subset=["COTA_ad"])
        if not grp_nonan.empty:
            idx_menor  = grp_nonan["COTA_ad"].idxmin()
            idx_melhor_d = grp_nonan["COTA_ad"].idxmax()
            menor_ret_dia      = grp_nonan.loc[idx_menor,    "COTA_ad"]
            menor_ret_dia_data = grp_nonan.loc[idx_menor,    "Data_Posicao"].strftime("%d/%m/%Y")
            melhor_ret_dia     = grp_nonan.loc[idx_melhor_d, "COTA_ad"]
            melhor_ret_dia_data = grp_nonan.loc[idx_melhor_d, "Data_Posicao"].strftime("%d/%m/%Y")
        else:
            menor_ret_dia = melhor_ret_dia = np.nan
            menor_ret_dia_data = melhor_ret_dia_data = ""

        results.append({
            "ID_CNPJ_Fundo":           cnpj,
            "Codigo_Subclasse":        sub,
            "Vol_Diaria":              vol_diaria,
            "Vol_Anual":               vol_anual,
            "Media_Diaria":            media_diaria,
            "Ret_FD_12M":              ret_fd_12m,
            "Ret_DI_12M":              ret_di_12m,
            "Sharpe":                  sharpe,
            "Modigliani":              modigliani,
            "Information_Ratio":       information_ratio,
            "Tracking_Error":          tracking_error,
            "VaR_1M":                  var_1m,
            "VaR_12M":                 var_12m,
            "CVaR_1M":                 cvar_1m,
            "CVaR_12M":                cvar_12m,
            "Pior_Mes":                pior_mes,
            "Pior_Mes_Data":           pior_mes_data,
            "Melhor_Mes":              melhor_mes,
            "Melhor_Mes_Data":         melhor_mes_data,
            "Menor_Retorno_Dia":       menor_ret_dia,
            "Menor_Retorno_Dia_Data":  menor_ret_dia_data,
            "Melhor_Retorno_Dia":      melhor_ret_dia,
            "Melhor_Retorno_Dia_Data": melhor_ret_dia_data,
            "Total_Meses":             total_meses,
            "Meses_Positivos_Qtd":     int(meses_pos),
            "Meses_Positivos_Pct":     meses_pos / total_meses if total_meses > 0 else np.nan,
            "Meses_Acima_CDI_Qtd":     int(meses_cdi),
            "Meses_Acima_CDI_Pct":     meses_cdi / total_meses if total_meses > 0 else np.nan,
        })

    return pd.DataFrame(results)
