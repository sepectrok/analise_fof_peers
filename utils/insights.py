"""Insights & Outlier Detection — FIDC Analytics Platform"""

import numpy as np
import pandas as pd
from utils.data_loader import TAXA_COLS, TAXA_LABELS


def detect_outliers_iqr(series: pd.Series) -> pd.Series:
    """Return boolean mask of outliers (IQR × 1.5)."""
    q1, q3 = series.quantile(0.25), series.quantile(0.75)
    iqr = q3 - q1
    return (series < q1 - 1.5 * iqr) | (series > q3 + 1.5 * iqr)


def generate_insights(df: pd.DataFrame) -> list[dict]:
    """Generate automatic insights as list of dicts with keys:
    icon, title, text, type (info | success | warning | danger)."""
    insights = []

    # 1 — Segment with highest admin fee
    col = "taxa_administracao"
    if col in df.columns and df[col].notna().sum() >= 5:
        seg = df.groupby("foco_atuacao")[col].mean().dropna()
        mkt = df[col].mean()
        if not seg.empty and mkt > 0:
            top = seg.idxmax()
            diff = (seg[top] / mkt - 1) * 100
            insights.append({
                "icon": "📊",
                "title": "Segmento com Maior Taxa de Adm.",
                "text": (f"O segmento <b>{top}</b> possui taxa média de administração de "
                         f"<b>{seg[top]:.3f}% a.a.</b>, cerca de "
                         f"<b>{abs(diff):.0f}%</b> {'acima' if diff > 0 else 'abaixo'} "
                         f"da média do mercado ({mkt:.3f}%)."),
                "type": "warning" if diff > 25 else "info",
            })

    # 2 — Cheapest administrator (≥3 funds)
    if "taxa_administracao" in df.columns and "administrador" in df.columns:
        adm = (df.dropna(subset=["administrador", "taxa_administracao"])
               .groupby("administrador")["taxa_administracao"]
               .agg(["mean", "count"]))
        adm = adm[adm["count"] >= 3]
        if not adm.empty:
            best = adm["mean"].idxmin()
            insights.append({
                "icon": "🏆",
                "title": "Administrador com Menores Taxas",
                "text": (f"<b>{best}</b> apresenta a menor taxa média de administração "
                         f"entre administradores com 3+ fundos: "
                         f"<b>{adm.loc[best,'mean']:.3f}% a.a.</b>"),
                "type": "success",
            })

    # 3 — Dispersion of gestão fee
    if "taxa_gestao" in df.columns and df["taxa_gestao"].notna().sum() >= 5:
        s = df["taxa_gestao"].dropna()
        cv = s.std() / s.mean() * 100 if s.mean() > 0 else 0
        insights.append({
            "icon": "📉",
            "title": "Dispersão da Taxa de Gestão",
            "text": (f"Coeficiente de variação da taxa de gestão: <b>{cv:.0f}%</b>. "
                     f"{'Alta dispersão — estratégias de gestão muito heterogêneas.' if cv > 50 else 'Dispersão moderada entre os fundos analisados.'}"),
            "type": "warning" if cv > 50 else "info",
        })

    # 4 — Total outliers across all taxa cols
    total_outliers = 0
    for col in TAXA_COLS:
        if col in df.columns:
            s = df[col].dropna()
            if len(s) >= 10:
                total_outliers += detect_outliers_iqr(s).sum()
    if total_outliers > 0:
        insights.append({
            "icon": "⚠️",
            "title": "Outliers Identificados",
            "text": (f"<b>{total_outliers}</b> registros outliers detectados via método IQR × 1,5 "
                     f"nas taxas analisadas. Esses fundos merecem revisão detalhada."),
            "type": "warning",
        })

    # 5 — Funds without performance fee
    if "taxa_performance" in df.columns:
        n_sem = df["taxa_performance"].isna().sum()
        pct = n_sem / len(df) * 100
        insights.append({
            "icon": "💡",
            "title": "Taxa de Performance",
            "text": (f"<b>{pct:.0f}%</b> dos fundos ({n_sem}/{len(df)}) "
                     f"não cobram taxa de performance nos regulamentos."),
            "type": "info",
        })

    # 6 — Correlation PL range vs taxa (use valor_minimo proxy if available)
    if "taxa_administracao" in df.columns and "taxa_gestao" in df.columns:
        corr = df[["taxa_administracao", "taxa_gestao"]].corr().iloc[0, 1]
        if not np.isnan(corr):
            insights.append({
                "icon": "🔗",
                "title": "Correlação Adm. × Gestão",
                "text": (f"Correlação de <b>{corr:.2f}</b> entre taxas de administração e gestão. "
                         f"{'Fundos com maior taxa de adm. tendem a ter maior taxa de gestão.' if corr > 0.3 else 'Baixa correlação — precificações independentes.'}"),
                "type": "info",
            })

    return insights


def rank_percentile(df: pd.DataFrame, col: str, cnpj: str) -> float | None:
    """Return percentile rank (0–100) of a fund in a given taxa column."""
    s = df[col].dropna()
    if s.empty:
        return None
    fund_val = df.loc[df["cnpj_tratado"] == cnpj, col]
    if fund_val.empty or fund_val.isna().all():
        return None
    return float(np.mean(s <= fund_val.values[0])) * 100


def describe_taxa(series: pd.Series) -> dict:
    """Return descriptive statistics dict."""
    s = series.dropna()
    if s.empty:
        return {}
    return {
        "count":  len(s),
        "mean":   s.mean(),
        "median": s.median(),
        "std":    s.std(),
        "min":    s.min(),
        "p25":    s.quantile(0.25),
        "p75":    s.quantile(0.75),
        "max":    s.max(),
    }
