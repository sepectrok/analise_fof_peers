"""Formatters — FIDC Analytics Platform"""

import numpy as np
import pandas as pd


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
