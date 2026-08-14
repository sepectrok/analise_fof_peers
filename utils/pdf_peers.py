"""
pdf_peers.py — Relatório PDF de Estudo Comparativo de Peers (FoF Dashboard)
Solis Investimentos

API compatível com fpdf 1.7.x (PyFPDF) — usa ln=True em vez de new_x/new_y.

Estrutura:
  Pág. 1 — Capa institucional (fundo, período, peers)
  Pág. 2 — Retornos Acumulados (tabela KPI + gráfico cota indexada)
  Pág. 3 — Retornos Mensais (barras + tabela comparativa)
  Pág. 4 — Métricas de Risco (KPI grid + tabela + dispersão)
  Pág. 5 — Ranking 12M + Notas Metodológicas
"""
from __future__ import annotations

import io
import os
import tempfile
from datetime import datetime
from typing import Optional

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from fpdf import FPDF

from utils.formatters import shorten as _shorten_base

# ─── Paleta Solis v3.0 ────────────────────────────────────────────────────────
C_BG   = (16,  36,  50)    # #102432 — azul marinho Solis
C_ACC  = (62,  91, 125)    # #3E5B7D — azul institucional
C_ACC2 = (137, 155, 183)   # #899BB7 — azul acinzentado
C_HI   = (255, 255, 255)   # branco
C_MED  = (137, 155, 183)   # texto secundário
C_ALT  = (26,  58,  82)    # #1A3A52 — card escuro
C_WHT  = (255, 255, 255)
C_DIV  = (42,  64,  96)    # #2A4060 — divisor
C_WARM = (255, 195, 106)   # #FFC36A — dourado Solis
C_GREEN= (16,  185, 129)
C_RED  = (239,  68,  68)

BG_HEX      = "#102432"
AMBER_HEX   = "#FFC36A"
BLUE_HEX    = "#3E5B7D"
GREEN_HEX   = "#10B981"
RED_HEX     = "#EF4444"
TEXT_HEX    = "#899BB7"
TEXT_HI_HEX = "#E8EDF1"

_COR_ALVO   = AMBER_HEX
_MPL_PEERS  = [BLUE_HEX, "#F89B66", GREEN_HEX, "#9B59B6", "#1ABC9C", "#E74C3C"]


# ─── Helpers de formatação ────────────────────────────────────────────────────

def _short(name: str, max_len: int = 38) -> str:
    return _shorten_base(name, max_len=max_len)


def _fmt_pct(v, digits=2, sign=False) -> str:
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "--"
    s = f"{v*100:.{digits}f}".replace(".", ",")
    return f"+{s}%" if (sign and v > 0) else f"{s}%"


def _fmt_x(v, digits=2) -> str:
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "--"
    return f"{v:.{digits}f}".replace(".", ",") + "x"


def _fmt_num(v, digits=2) -> str:
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "--"
    return f"{v:.{digits}f}".replace(".", ",")


# Tabela de substituicao de caracteres Unicode fora de Latin-1
_UNICODE_SUBS = {
    # Travessoes e hifens
    '\u2014': '-', '\u2013': '-', '\u2012': '-', '\u2011': '-',
    # Aspas tipograficas
    '\u201c': '"', '\u201d': '"', '\u2018': "'", '\u2019': "'",
    # Outros simbolos comuns
    '\u2026': '...', '\u00d7': 'x', '\u00f7': '/',
    '\u2192': '->', '\u2190': '<-', '\u2022': '*',
    '\u00b0': 'o', '\u00b2': '2', '\u00b3': '3',
    '\u221a': 'raiz', '\u03c3': 'sigma', '\u03bc': 'mu', '\u03b1': 'alpha',
    '\u00d7': 'x',
}

def _safe(s) -> str:
    """Converte qualquer valor para string segura em Latin-1 (fpdf 1.7.x)."""
    if s is None:
        return "--"
    text = str(s)
    # Substitui caracteres conhecidos
    for uni, asc in _UNICODE_SUBS.items():
        text = text.replace(uni, asc)
    # Forcefully encodes remaining non-Latin-1 chars
    text = text.encode('latin-1', errors='replace').decode('latin-1')
    return text

# ─── Matplotlib helpers ───────────────────────────────────────────────────────

def _mpl_defaults():
    plt.rcParams.update({
        "figure.facecolor":  BG_HEX,
        "axes.facecolor":    BG_HEX,
        "axes.edgecolor":    "#2A4060",
        "axes.labelcolor":   TEXT_HEX,
        "text.color":        TEXT_HI_HEX,
        "xtick.color":       TEXT_HEX,
        "ytick.color":       TEXT_HEX,
        "grid.color":        "#2A4060",
        "grid.linewidth":    0.5,
        "font.family":       "sans-serif",
        "font.size":         9,
    })


def _save_fig(fig, w_in: float, h_in: float) -> tuple[str, float, float]:
    tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    fig.savefig(tmp.name, dpi=150, facecolor=BG_HEX, edgecolor="none", bbox_inches="tight")
    plt.close(fig)
    return tmp.name, w_in, h_in


def _img_h_mm(w_mm: float, w_in: float, h_in: float) -> float:
    return w_mm * h_in / w_in


# ─── Gráficos matplotlib ──────────────────────────────────────────────────────

def _build_cota_chart(
    df_idx: pd.DataFrame,
    cnpj_alvo: str,
    cnpjs_peers: list[str],
    nome_map: dict[str, str],
) -> tuple[str, float, float]:
    _mpl_defaults()
    FW, FH = 9.5, 3.8
    fig, ax = plt.subplots(figsize=(FW, FH))

    ordem = [cnpj_alvo] + list(cnpjs_peers)
    for i, cnpj in enumerate(ordem):
        grp = df_idx[df_idx["ID_CNPJ_Fundo"] == cnpj].sort_values("Data_Posicao")
        if grp.empty:
            continue
        nome = nome_map.get(cnpj, cnpj)
        cor  = _COR_ALVO if cnpj == cnpj_alvo else _MPL_PEERS[(i - 1) % len(_MPL_PEERS)]
        lw   = 2.2 if cnpj == cnpj_alvo else 1.5
        ax.plot(grp["Data_Posicao"], grp["Cota_Indexada"], label=nome,
                color=cor, linewidth=lw)

    cdi = df_idx[df_idx["ID_CNPJ_Fundo"] == "__CDI__"].sort_values("Data_Posicao")
    if not cdi.empty:
        ax.plot(cdi["Data_Posicao"], cdi["Cota_Indexada"],
                label="CDI", color=TEXT_HEX, linewidth=1.2, linestyle="--", alpha=0.7)

    ax.set_title("Cota Acumulada — Base 100", color=AMBER_HEX,
                 fontsize=11, fontweight="bold", pad=10)
    ax.set_ylabel("Cota (Base 100)", fontsize=8)
    ax.legend(loc="upper left", fontsize=7, frameon=False, labelcolor=TEXT_HI_HEX,
              ncol=min(4, len(ordem) + 2))
    ax.grid(axis="y", alpha=0.25, linestyle="--")
    ax.tick_params(axis="x", labelsize=7.5, rotation=25)
    ax.tick_params(axis="y", labelsize=7.5)
    ax.spines[["top", "right"]].set_visible(False)
    fig.patch.set_facecolor(BG_HEX)
    fig.tight_layout()
    return _save_fig(fig, FW, FH)


def _build_barras_mensais(
    df_mensal: pd.DataFrame,
    cnpj_alvo: str,
    nome_map: dict[str, str],
) -> tuple[str, float, float]:
    _mpl_defaults()

    if df_mensal.empty or "ID_CNPJ_Fundo" not in df_mensal.columns:
        FW, FH = 9.5, 3.0
        fig, ax = plt.subplots(figsize=(FW, FH))
        ax.text(0.5, 0.5, "Sem dados mensais disponiveis", ha="center", va="center",
                color=TEXT_HEX, fontsize=10)
        fig.patch.set_facecolor(BG_HEX)
        return _save_fig(fig, FW, FH)

    grp = df_mensal[df_mensal["ID_CNPJ_Fundo"] == cnpj_alvo].sort_values("Mes").copy()

    if grp.empty:
        FW, FH = 9.5, 3.0
        fig, ax = plt.subplots(figsize=(FW, FH))
        ax.text(0.5, 0.5, "Sem dados mensais", ha="center", va="center",
                color=TEXT_HEX, fontsize=10)
        fig.patch.set_facecolor(BG_HEX)
        return _save_fig(fig, FW, FH)

    meses  = [str(m) for m in grp["Mes"]]
    fd_pct = (grp["Ret_FD_am"].fillna(0) * 100).tolist()
    di_pct = (grp["Ret_DI_am"].fillna(0) * 100).tolist()
    acima  = [f > d for f, d in zip(fd_pct, di_pct)]
    cores  = [GREEN_HEX if a else RED_HEX for a in acima]

    FW = max(9.0, len(meses) * 0.45)
    FH = 3.4
    fig, ax = plt.subplots(figsize=(FW, FH))
    bars = ax.bar(meses, fd_pct, color=cores, width=0.65, edgecolor=BG_HEX, linewidth=0.5)
    ax.plot(meses, di_pct, color=TEXT_HEX, linewidth=1.5, linestyle="--",
            marker="o", markersize=3, label="CDI", alpha=0.8)

    for bar, val in zip(bars, fd_pct):
        ypos = val + 0.008 if val >= 0 else val - 0.015
        ax.text(bar.get_x() + bar.get_width() / 2, ypos,
                f"{val:.2f}%", ha="center", va="bottom" if val >= 0 else "top",
                fontsize=6.5, color=TEXT_HI_HEX)

    nome_alvo = nome_map.get(cnpj_alvo, cnpj_alvo)
    ax.set_title(f"Retornos Mensais — {_short(nome_alvo, 55)}",
                 color=AMBER_HEX, fontsize=10, fontweight="bold", pad=10)
    ax.set_ylabel("Retorno (%)", fontsize=8)
    ax.axhline(0, color=TEXT_HEX, linewidth=0.6, alpha=0.5)
    ax.legend(fontsize=7.5, frameon=False, labelcolor=TEXT_HI_HEX)
    ax.tick_params(axis="x", labelsize=6.5, rotation=45)
    ax.tick_params(axis="y", labelsize=7.5)
    ax.grid(axis="y", alpha=0.2, linestyle="--")
    ax.spines[["top", "right"]].set_visible(False)
    fig.patch.set_facecolor(BG_HEX)
    fig.tight_layout()
    return _save_fig(fig, FW, FH)


def _build_dispersao(
    df_risco: pd.DataFrame,
    df_acc: pd.DataFrame,
    cnpj_alvo: str,
    nome_map: dict[str, str],
) -> tuple[str, float, float]:
    _mpl_defaults()
    FW, FH = 7.0, 4.5
    fig, ax = plt.subplots(figsize=(FW, FH))

    df_sc = df_risco.merge(
        df_acc[["ID_CNPJ_Fundo", "Ret_FD_Total_aa"]],
        on="ID_CNPJ_Fundo", how="left"
    ).dropna(subset=["Vol_Anual", "Ret_FD_Total_aa"])

    if df_sc.empty:
        ax.text(0.5, 0.5, "Dados insuficientes", ha="center", va="center",
                color=TEXT_HEX, fontsize=10)
        fig.patch.set_facecolor(BG_HEX)
        return _save_fig(fig, FW, FH)

    for i, row in df_sc.iterrows():
        cnpj    = row["ID_CNPJ_Fundo"]
        is_alvo = cnpj == cnpj_alvo
        cor     = _COR_ALVO if is_alvo else _MPL_PEERS[i % len(_MPL_PEERS)]
        sz      = 120 if is_alvo else 70
        ax.scatter(row["Vol_Anual"] * 100, row["Ret_FD_Total_aa"] * 100,
                   color=cor, s=sz, zorder=5,
                   edgecolors="white" if is_alvo else "none", linewidths=0.8)
        nome = _short(nome_map.get(cnpj, cnpj), 28)
        ax.annotate(nome,
                    xy=(row["Vol_Anual"] * 100, row["Ret_FD_Total_aa"] * 100),
                    xytext=(5, 4), textcoords="offset points",
                    fontsize=6.5, color=TEXT_HI_HEX if is_alvo else TEXT_HEX)

    ax.set_xlabel("Volatilidade Anual (%)", fontsize=8)
    ax.set_ylabel("Retorno Anualizado (%)", fontsize=8)
    ax.set_title("Risco x Retorno (Anualizado no Periodo)", color=AMBER_HEX,
                 fontsize=10, fontweight="bold", pad=10)
    ax.grid(alpha=0.2, linestyle="--")
    ax.spines[["top", "right"]].set_visible(False)
    fig.patch.set_facecolor(BG_HEX)
    fig.tight_layout()
    return _save_fig(fig, FW, FH)


def _build_ranking(
    df_acc: pd.DataFrame,
    cnpj_alvo: str,
    cnpjs_peers: list[str],
    nome_map: dict[str, str],
) -> tuple[str, float, float]:
    _mpl_defaults()
    cnpjs = [cnpj_alvo] + list(cnpjs_peers)
    df_rk = df_acc[df_acc["ID_CNPJ_Fundo"].isin(cnpjs)].copy()
    df_rk["Nome"] = df_rk["ID_CNPJ_Fundo"].map(nome_map).apply(
        lambda n: _short(n, 38)
    )
    df_rk = df_rk.dropna(subset=["Ret_FD_12M"]).sort_values("Ret_FD_12M")

    FW = 8.0
    FH = max(3.0, len(df_rk) * 0.55)
    fig, ax = plt.subplots(figsize=(FW, FH))
    cores = [_COR_ALVO if c == cnpj_alvo else BLUE_HEX for c in df_rk["ID_CNPJ_Fundo"]]
    bars  = ax.barh(df_rk["Nome"].tolist(), (df_rk["Ret_FD_12M"] * 100).tolist(),
                    color=cores, height=0.55, edgecolor=BG_HEX, linewidth=0.5)

    for bar, val in zip(bars, df_rk["Ret_FD_12M"] * 100):
        ax.text(bar.get_width() + 0.05, bar.get_y() + bar.get_height() / 2,
                f"{val:.2f}%", va="center", ha="left",
                color=TEXT_HI_HEX, fontsize=8, fontweight="bold")

    ax.set_xlabel("Retorno 12M (%)", fontsize=8)
    ax.set_title("Ranking — Retorno 12M", color=AMBER_HEX,
                 fontsize=10, fontweight="bold", pad=10)
    _mx = (df_rk["Ret_FD_12M"] * 100).max() if not df_rk.empty else 1.0
    ax.set_xlim(right=_mx * 1.25)
    ax.grid(axis="x", alpha=0.2, linestyle="--")
    ax.spines[["top", "right"]].set_visible(False)
    ax.tick_params(axis="y", labelsize=8)
    ax.tick_params(axis="x", labelsize=8)
    fig.patch.set_facecolor(BG_HEX)
    fig.tight_layout()
    return _save_fig(fig, FW, FH)


# ─── Classe FPDF (API compatível com fpdf 1.7.x) ─────────────────────────────

class PeersReport(FPDF):
    def __init__(self, nome_alvo: str, peers_nomes: list[str],
                 data_inicio: str, data_fim: str):
        super().__init__(orientation="P", unit="mm", format="A4")
        self.set_auto_page_break(auto=True, margin=18)
        self.set_margins(18, 18, 18)
        try:
            self.add_font("Arial", "",  r"C:\Windows\Fonts\arial.ttf")
            self.add_font("Arial", "B", r"C:\Windows\Fonts\arialbd.ttf")
            self._ff = "Arial"
        except Exception:
            self._ff = "Helvetica"
        self.nome_alvo   = nome_alvo
        self.peers_nomes = peers_nomes
        self.data_inicio = data_inicio
        self.data_fim    = data_fim

    def _f(self, style: str = "", size: float = 9):
        self.set_font(self._ff, style, size)

    def header(self):
        self.set_fill_color(*C_BG)
        self.rect(0, 0, 210, 297, "F")
        if self.page_no() == 1:
            return
        self.set_fill_color(*C_ALT)
        self.rect(0, 0, 210, 11, "F")
        self.set_fill_color(*C_WARM)
        self.rect(0, 0, 210, 1.5, "F")
        self.set_y(3)
        self._f("B", 7)
        self.set_text_color(*C_WARM)
        self.cell(0, 5, _safe("Estudo Comparativo de Peers  |  " + _short(self.nome_alvo, 55)))
        self.set_y(13)

    def footer(self):
        self.set_y(-12)
        self.set_fill_color(*C_BG)
        self.rect(0, 285, 210, 12, "F")
        self._f("", 7)
        self.set_text_color(*C_MED)
        self.cell(
            0, 5,
            f"Fonte: ANBIMA / CDA    |    Pagina {self.page_no()}"
            f"    |    Gerado em {datetime.now().strftime('%d/%m/%Y %H:%M')}",
            align="C",
        )

    def _divider(self):
        self.set_draw_color(*C_DIV)
        self.set_line_width(0.35)
        self.line(18, self.get_y() + 1, 192, self.get_y() + 1)
        self.ln(3)

    def _sec(self, txt: str):
        self.ln(3)
        self._f("B", 9.5)
        self.set_text_color(*C_ACC)
        self.cell(0, 6, _safe(txt.upper()), ln=True)
        self._divider()

    def _kpi_row(self, items: list[tuple[str, str, str]]):
        cw = (210 - 36) / len(items)
        pad, hb = 3, 17
        xs, ys = 18, self.get_y()
        for i, (label, val, sub) in enumerate(items):
            x = xs + i * cw
            self.set_fill_color(*C_ALT)
            self.set_draw_color(*C_ACC)
            self.set_line_width(0.25)
            self.rect(x, ys, cw - 2, hb, "FD")
            self.set_xy(x + pad, ys + 2)
            self._f("", 6.5)
            self.set_text_color(*C_MED)
            self.cell(cw - 2 - pad * 2, 4, _safe(label))
            self.set_xy(x + pad, ys + 7)
            self._f("B", 11)
            self.set_text_color(*C_HI)
            self.cell(cw - 2 - pad * 2, 5.5, _safe(val))
            self.set_xy(x + pad, ys + 13)
            self._f("", 6)
            self.set_text_color(*C_MED)
            self.cell(cw - 2 - pad * 2, 3.5, _safe(sub))
        self.set_y(ys + hb + 3)

    def _th(self, headers: list[str], widths: list[float]):
        self.set_fill_color(*C_ACC)
        self.set_text_color(*C_WHT)
        self._f("B", 7)
        for h, w in zip(headers, widths):
            self.cell(w, 6, _safe(h), fill=True, align="C")
        self.ln()

    def _tr(self, vals: list[str], widths: list[float], alt: bool,
            highlight_col: Optional[int] = None):
        self.set_fill_color(*(C_ALT if alt else C_BG))
        for j, (v, w) in enumerate(zip(vals, widths)):
            if j == highlight_col:
                self.set_text_color(*C_WARM)
                self._f("B", 7)
            else:
                self.set_text_color(*C_HI)
                self._f("", 7)
            self.cell(w, 5.5, _safe(v), fill=True, align="C")
        self.ln()
        y = self.get_y()
        self.set_draw_color(*C_DIV)
        self.set_line_width(0.12)
        self.line(18, y, 192, y)


# ─── Seções ───────────────────────────────────────────────────────────────────

def _capa(pdf: PeersReport):
    pdf.add_page()
    # Barra dourada no topo
    pdf.set_fill_color(*C_WARM)
    pdf.rect(0, 0, 210, 4, "F")

    # Cabecalho
    pdf.set_y(42)
    pdf._f("B", 9)
    pdf.set_text_color(*C_ACC2)
    pdf.cell(0, 6, "SOLIS INVESTIMENTOS", align="C", ln=True)
    pdf.ln(4)
    pdf._f("B", 26)
    pdf.set_text_color(*C_WARM)
    pdf.cell(0, 14, "Estudo Comparativo de Peers", align="C", ln=True)
    pdf.ln(2)
    pdf._f("", 12)
    pdf.set_text_color(*C_MED)
    pdf.cell(0, 7, "FoF - Analise de Retornos & Risco", align="C", ln=True)

    # Linha separadora
    pdf.ln(8)
    pdf.set_draw_color(*C_ACC2)
    pdf.set_line_width(0.8)
    pdf.line(45, pdf.get_y(), 165, pdf.get_y())
    pdf.ln(10)

    # Caixa — Fundo Analisado
    bx, bw, bh = 25, 160, 18
    by = pdf.get_y()
    pdf.set_fill_color(*C_ALT)
    pdf.set_draw_color(*C_WARM)
    pdf.set_line_width(0.4)
    pdf.rect(bx, by, bw, bh, "FD")
    pdf.set_xy(bx, by + 2)
    pdf._f("", 7)
    pdf.set_text_color(*C_MED)
    pdf.cell(bw, 4.5, "FUNDO ANALISADO", align="C", ln=True)
    pdf.set_x(bx)
    pdf._f("B", 10)
    pdf.set_text_color(*C_WARM)
    pdf.cell(bw, 7, _safe(_short(pdf.nome_alvo, 70)), align="C", ln=True)
    pdf.set_y(by + bh + 6)

    # Periodo
    bx2, bw2, bh2 = 55, 100, 15
    by2 = pdf.get_y()
    pdf.set_fill_color(*C_ALT)
    pdf.set_draw_color(*C_ACC)
    pdf.set_line_width(0.25)
    pdf.rect(bx2, by2, bw2, bh2, "FD")
    pdf.set_xy(bx2, by2 + 2)
    pdf._f("", 7)
    pdf.set_text_color(*C_MED)
    pdf.cell(bw2, 4, "PERIODO DE ANALISE", align="C", ln=True)
    pdf.set_x(bx2)
    pdf._f("B", 9)
    pdf.set_text_color(*C_HI)
    pdf.cell(bw2, 6, f"{pdf.data_inicio}  -  {pdf.data_fim}", align="C", ln=True)
    pdf.set_y(by2 + bh2 + 8)

    # Peers listados
    if pdf.peers_nomes:
        pdf._f("B", 8)
        pdf.set_text_color(*C_ACC2)
        pdf.cell(0, 5, "PEERS SELECIONADOS", align="C", ln=True)
        pdf.ln(2)
        for i, p in enumerate(pdf.peers_nomes, 1):
            pdf._f("", 8)
            pdf.set_text_color(*C_HI)
            pdf.cell(0, 5.5, _safe(f"  {i}.  {_short(p, 70)}"), align="C", ln=True)
    else:
        pdf._f("", 8)
        pdf.set_text_color(*C_MED)
        pdf.cell(0, 5, "(Sem peers selecionados - analise solo do fundo)", align="C", ln=True)

    # Rodape
    pdf.set_y(274)
    pdf._f("", 7)
    pdf.set_text_color(*C_MED)
    pdf.cell(0, 4,
             "Fonte: ANBIMA  |  Uso interno  |  Nao constitui recomendacao de investimento",
             align="C")
    pdf.set_fill_color(*C_WARM)
    pdf.rect(0, 293, 210, 4, "F")


def _retornos_acumulados(
    pdf: PeersReport,
    df_acc: pd.DataFrame,
    df_idx: pd.DataFrame,
    cnpj_alvo: str,
    cnpjs_peers: list[str],
    nome_map: dict[str, str],
    tmp_files: list[str],
):
    pdf.add_page()
    pdf.set_y(15)
    pdf._sec("Retornos Acumulados")

    cnpjs_tbl = [cnpj_alvo] + list(cnpjs_peers)
    df_t = df_acc[df_acc["ID_CNPJ_Fundo"].isin(cnpjs_tbl)].copy()
    df_t["Nome_Curto"] = df_t["ID_CNPJ_Fundo"].map(nome_map).apply(
        lambda n: _short(n, 32) if isinstance(n, str) else str(n)
    )
    df_t = df_t.sort_values(
        "ID_CNPJ_Fundo",
        key=lambda s: s.map(lambda x: 0 if x == cnpj_alvo else 1)
    )

    hdrs = ["Fundo", "YTD", "12M", "% CDI 12M", "24M", "% CDI 24M", "Desde Inicio", "Inicio aa", "Dias"]
    wids = [48, 15, 16, 19, 16, 19, 20, 16, 5]
    pdf._th(hdrs, wids)
    for idx_row, (_, row) in enumerate(df_t.iterrows()):
        is_alvo = row["ID_CNPJ_Fundo"] == cnpj_alvo
        dias_val = row.get("Dias_total")
        vals = [
            row.get("Nome_Curto", "--"),
            _fmt_pct(row.get("Ret_FD_YTD")),
            _fmt_pct(row.get("Ret_FD_12M")),
            _fmt_x(row.get("Ret_FD_DI_pct_12M")),
            _fmt_pct(row.get("Ret_FD_24M")),
            _fmt_x(row.get("Ret_FD_DI_pct_24M")),
            _fmt_pct(row.get("Ret_FD_Total")),
            _fmt_pct(row.get("Ret_FD_Total_aa")),
            str(int(dias_val)) if pd.notna(dias_val) else "--",
        ]
        pdf._tr(vals, wids, bool(idx_row % 2), highlight_col=0 if is_alvo else None)

    pdf.ln(5)

    # Grafico cota indexada
    pdf._sec("Cota Acumulada (Base 100)")
    if not df_idx.empty:
        path, fw, fh = _build_cota_chart(df_idx, cnpj_alvo, cnpjs_peers, nome_map)
        tmp_files.append(path)
        IMG_W = 170.0
        h_mm  = _img_h_mm(IMG_W, fw, fh)
        if pdf.get_y() + h_mm > 270:
            pdf.add_page()
            pdf.set_y(15)
        pdf.image(path, x=(210 - IMG_W) / 2, y=pdf.get_y(), w=IMG_W)
        pdf.set_y(pdf.get_y() + h_mm + 3)


def _retornos_mensais(
    pdf: PeersReport,
    df_mensal: pd.DataFrame,
    df_acc: pd.DataFrame,
    cnpj_alvo: str,
    cnpjs_peers: list[str],
    nome_map: dict[str, str],
    tmp_files: list[str],
):
    pdf.add_page()
    pdf.set_y(15)
    pdf._sec("Retornos Mensais")

    path, fw, fh = _build_barras_mensais(df_mensal, cnpj_alvo, nome_map)
    tmp_files.append(path)
    IMG_W = 170.0
    h_mm  = _img_h_mm(IMG_W, fw, fh)
    pdf.image(path, x=(210 - IMG_W) / 2, y=pdf.get_y(), w=IMG_W)
    pdf.set_y(pdf.get_y() + h_mm + 5)

    if df_mensal.empty:
        return

    cnpjs_m = [cnpj_alvo] + list(cnpjs_peers)
    df_m = df_mensal[df_mensal["ID_CNPJ_Fundo"].isin(cnpjs_m)].copy()
    df_m["Nome_Curto"] = df_m["ID_CNPJ_Fundo"].map(nome_map).apply(
        lambda n: _short(n, 20) if isinstance(n, str) else str(n)
    )

    df_pivot_m = df_m.pivot_table(
        index="Nome_Curto", columns="Mes", values="Ret_FD_am", aggfunc="first"
    )
    meses_sorted = sorted(df_pivot_m.columns)[-18:]
    df_pivot_m = df_pivot_m[meses_sorted]

    nome_alvo_curto = _short(nome_map.get(cnpj_alvo, cnpj_alvo), 20)
    rows_order = [nome_alvo_curto] + [r for r in df_pivot_m.index if r != nome_alvo_curto]
    df_pivot_m = df_pivot_m.reindex([r for r in rows_order if r in df_pivot_m.index])

    if pdf.get_y() + 30 > 260:
        pdf.add_page()
        pdf.set_y(15)

    pdf._sec("Retornos Mensais — Comparativo (ultimos 18M)")
    n_cols = len(meses_sorted)
    mes_labels = [str(m)[:7] for m in meses_sorted]
    fundo_w = 42
    col_w = round((174 - fundo_w) / max(n_cols, 1), 1)

    pdf._th(["Fundo"] + mes_labels, [fundo_w] + [col_w] * n_cols)
    for alt_row, (nome, row_data) in enumerate(df_pivot_m.iterrows()):
        is_alvo_row = (nome == nome_alvo_curto)
        vals = [nome] + [_fmt_pct(row_data.get(m), digits=2) for m in meses_sorted]
        pdf._tr(vals, [fundo_w] + [col_w] * n_cols, bool(alt_row % 2),
                highlight_col=0 if is_alvo_row else None)


def _metricas_risco(
    pdf: PeersReport,
    df_risco: pd.DataFrame,
    df_acc: pd.DataFrame,
    cnpj_alvo: str,
    cnpjs_peers: list[str],
    nome_map: dict[str, str],
    tmp_files: list[str],
):
    pdf.add_page()
    pdf.set_y(15)
    pdf._sec("Metricas de Risco")

    cnpjs_r = [cnpj_alvo] + list(cnpjs_peers)
    df_r = df_risco[df_risco["ID_CNPJ_Fundo"].isin(cnpjs_r)].copy()
    df_r["Nome_Curto"] = df_r["ID_CNPJ_Fundo"].map(nome_map).apply(
        lambda n: _short(n, 28) if isinstance(n, str) else str(n)
    )

    # KPIs do fundo alvo
    risco_alvo = df_r[df_r["ID_CNPJ_Fundo"] == cnpj_alvo]
    if not risco_alvo.empty:
        row_r = risco_alvo.iloc[0]
        pdf._kpi_row([
            ("Vol. Anual",     _fmt_pct(row_r.get("Vol_Anual")),           "sigma_d x raiz(252)"),
            ("Sharpe (12M)",   _fmt_num(row_r.get("Sharpe")),              "(R12M - CDI) / Vol"),
            ("Info. Ratio",    _fmt_num(row_r.get("Information_Ratio")),   "Alpha / TE"),
            ("Tracking Error", _fmt_pct(row_r.get("Tracking_Error")),      "sigma(exc) x raiz(252)"),
        ])
        pdf.ln(1)
        pdf._kpi_row([
            ("VaR 1M (95%)",   _fmt_pct(row_r.get("VaR_1M")),             "Param. Normal 21d"),
            ("CVaR 1M (95%)",  _fmt_pct(row_r.get("CVaR_1M")),            "Expected Shortfall"),
            ("Pior Mes",
             _fmt_pct(row_r.get("Pior_Mes"), sign=True),
             str(row_r.get("Pior_Mes_Data", "--"))),
            ("Meses Acima CDI",
             f"{row_r.get('Meses_Acima_CDI_Qtd', '--')}/{row_r.get('Total_Meses', '--')}",
             _fmt_pct(row_r.get("Meses_Acima_CDI_Pct"))),
        ])
        pdf.ln(4)

    # Tabela comparativa
    pdf._sec("Comparativo de Risco — Todos os Fundos")
    hdrs = ["Fundo", "Vol.Anual", "Sharpe", "Info.Ratio", "Track.Err", "VaR1M", "CVaR1M", "PiorMes"]
    wids = [48, 20, 17, 20, 20, 18, 18, 13]
    pdf._th(hdrs, wids)
    df_r_sorted = df_r.sort_values(
        "ID_CNPJ_Fundo",
        key=lambda s: s.map(lambda x: 0 if x == cnpj_alvo else 1)
    )
    for alt_r, (_, row) in enumerate(df_r_sorted.iterrows()):
        is_alvo_r = row["ID_CNPJ_Fundo"] == cnpj_alvo
        vals = [
            row.get("Nome_Curto", "--"),
            _fmt_pct(row.get("Vol_Anual")),
            _fmt_num(row.get("Sharpe")),
            _fmt_num(row.get("Information_Ratio")),
            _fmt_pct(row.get("Tracking_Error")),
            _fmt_pct(row.get("VaR_1M")),
            _fmt_pct(row.get("CVaR_1M")),
            _fmt_pct(row.get("Pior_Mes"), sign=True),
        ]
        pdf._tr(vals, wids, bool(alt_r % 2), highlight_col=0 if is_alvo_r else None)

    pdf.ln(5)

    # Grafico dispersao
    if len(cnpjs_peers) > 0:
        path, fw, fh = _build_dispersao(df_risco, df_acc, cnpj_alvo, nome_map)
        tmp_files.append(path)
        IMG_W = 150.0
        h_mm  = _img_h_mm(IMG_W, fw, fh)
        if pdf.get_y() + h_mm > 270:
            pdf.add_page()
            pdf.set_y(15)
        pdf.image(path, x=(210 - IMG_W) / 2, y=pdf.get_y(), w=IMG_W)
        pdf.set_y(pdf.get_y() + h_mm + 3)


def _ranking_e_notas(
    pdf: PeersReport,
    df_acc: pd.DataFrame,
    cnpj_alvo: str,
    cnpjs_peers: list[str],
    nome_map: dict[str, str],
    tmp_files: list[str],
):
    if len(cnpjs_peers) == 0:
        return

    pdf.add_page()
    pdf.set_y(15)
    pdf._sec("Ranking — Retorno 12M")

    path, fw, fh = _build_ranking(df_acc, cnpj_alvo, cnpjs_peers, nome_map)
    tmp_files.append(path)
    IMG_W = 160.0
    h_mm  = _img_h_mm(IMG_W, fw, fh)
    pdf.image(path, x=(210 - IMG_W) / 2, y=pdf.get_y(), w=IMG_W)
    pdf.set_y(pdf.get_y() + h_mm + 8)

    pdf._sec("Notas Metodologicas")
    notas = [
        "Retornos calculados com base na serie de PU_Cota diaria reportada a ANBIMA.",
        "CDI de referencia: DI Over (CETIP), expresso como fator diario DI_ad_ftr.",
        "Volatilidade Anual = sigma_d x raiz(252), desvio-padrao dos retornos diarios (ddof=1).",
        "Sharpe = (Ret_FD_12M - Ret_DI_12M) / Vol_Anual.",
        "Information Ratio = (media diaria do excesso x 252) / Tracking Error anual.",
        "VaR 1M (95%) parametrico: -(mu_d x 21 + sigma_d x raiz(21) x z_0,95), z aprox. 1,645.",
        "CVaR 1M = -(mu_d x 21 + sigma_d x raiz(21) x phi(z_0,95) / (1 - 0,95)).",
        "Nao constitui recomendacao de investimento. Uso restrito a analise interna.",
    ]
    for i, n in enumerate(notas, 1):
        pdf._f("", 7.5)
        pdf.set_text_color(*C_MED)
        pdf.multi_cell(0, 5, _safe(f"{i}.  {n}"))
        pdf.ln(0.5)


# ─── API Pública ──────────────────────────────────────────────────────────────

def gerar_pdf_peers(
    resultado: dict,
    cnpj_alvo: str,
    cnpjs_peers,
    nome_map: dict[str, str],
    data_inicio: str,
    data_fim: str,
) -> bytes:
    """
    Gera o relatorio PDF de estudo comparativo fundo x peers.

    Parametros
    ----------
    resultado   : dict retornado por _calcular_tudo() em Retornos.py
                  Chaves: df_ret, df_acc, df_mensal, df_idx, df_risco
    cnpj_alvo   : CNPJ do fundo analisado
    cnpjs_peers : lista/tuple de CNPJs dos peers selecionados
    nome_map    : dict {cnpj: nome_curto} (inclui "__CDI__": "CDI")
    data_inicio : string "YYYY-MM-DD"
    data_fim    : string "YYYY-MM-DD"

    Retorna
    -------
    bytes do PDF gerado
    """
    df_acc    = resultado.get("df_acc",    pd.DataFrame())
    df_mensal = resultado.get("df_mensal", pd.DataFrame())
    df_idx    = resultado.get("df_idx",    pd.DataFrame())
    df_risco  = resultado.get("df_risco",  pd.DataFrame())

    cnpjs_peers = list(cnpjs_peers)

    # Formata datas para exibicao
    try:
        dt_ini = datetime.strptime(data_inicio, "%Y-%m-%d").strftime("%d/%m/%Y")
        dt_fim = datetime.strptime(data_fim,    "%Y-%m-%d").strftime("%d/%m/%Y")
    except ValueError:
        dt_ini, dt_fim = data_inicio, data_fim

    nome_alvo   = nome_map.get(cnpj_alvo, cnpj_alvo)
    peers_nomes = [nome_map.get(c, c) for c in cnpjs_peers]

    pdf = PeersReport(
        nome_alvo=nome_alvo,
        peers_nomes=peers_nomes,
        data_inicio=dt_ini,
        data_fim=dt_fim,
    )

    tmp_files: list[str] = []
    try:
        _capa(pdf)
        _retornos_acumulados(pdf, df_acc, df_idx, cnpj_alvo, cnpjs_peers, nome_map, tmp_files)
        _retornos_mensais(pdf, df_mensal, df_acc, cnpj_alvo, cnpjs_peers, nome_map, tmp_files)
        _metricas_risco(pdf, df_risco, df_acc, cnpj_alvo, cnpjs_peers, nome_map, tmp_files)
        _ranking_e_notas(pdf, df_acc, cnpj_alvo, cnpjs_peers, nome_map, tmp_files)
    finally:
        for f in tmp_files:
            try:
                os.unlink(f)
            except OSError:
                pass

    raw = pdf.output(dest="S")
    if isinstance(raw, str):
        return raw.encode("latin-1")
    return bytes(raw)
