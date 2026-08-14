"""Formatters — FIDC Analytics Platform"""

import numpy as np
import pandas as pd


def shorten(name: str, max_len: int = 50) -> str:
    """Abrevia nomes de fundos (FIC FI, FIDC, FIDC RL, CP, MM, RF) para exibição."""
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


def fmt_pct(val, decimals: int = 3) -> str:
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return "—"
    return f"{float(val):.{decimals}f}%"


def fmt_num(val, decimals: int = 0) -> str:
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return "—"
    return f"{float(val):,.{decimals}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def fmt_delta_pp(val: float, ref: float) -> tuple[str, bool]:
    """Return (formatted string, is_positive)."""
    if pd.isna(val) or pd.isna(ref):
        return "—", None
    delta = val - ref
    sign = "▲" if delta > 0 else "▼"
    return f"{sign} {abs(delta):.3f} p.p.", delta > 0


def fmt_percentile(rank: float) -> str:
    if pd.isna(rank):
        return "—"
    return f"{rank:.0f}º percentil"


def pct_to_display(df: pd.DataFrame, col: str) -> pd.Series:
    """Format a column as percentage strings for display."""
    return df[col].apply(fmt_pct)
