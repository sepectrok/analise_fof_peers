"""
pdf_export.py — Relatório PDF | Análise de FIDCs - Dados
Estrutura:
  Pág. 1 — Capa institucional
  Pág. 2 — Gráficos (Pizza + Top10 Gestores + Top10 Administradores)
  Pág. 3 — KPIs + Estatísticas por Taxa + Notas Metodológicas
"""
from __future__ import annotations

import io, os, tempfile
from datetime import datetime

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from fpdf import FPDF

from utils.data_loader import TAXA_COLS, TAXA_LABELS
from utils.formatters import fmt_pct

# ─── Paleta Solis v3.0 ───────────────────────────────────────────────────────
# Fiel ao site solisinvestimentos.com.br
C_BG   = (16,  36,  50)   # #102432 — azul marinho Solis
C_ACC  = (62,  91, 125)   # #3E5B7D — azul institucional
C_ACC2 = (137,155, 183)   # #899BB7 — azul acinzentado
C_HI   = (255, 255, 255)  # #FFFFFF — branco
C_MED  = (137, 155, 183)  # #899BB7 — texto secundário
C_ALT  = (26,  58,  82)   # #1A3A52 — card escuro
C_WHT  = (255, 255, 255)
C_DIV  = (42,  64,  96)   # #2A4060 — divisor
C_WARM = (255, 195, 106)  # #FFC36A — dourado Solis

MPL_COLORS = ["#3E5B7D","#FFC36A","#899BB7","#F89B66",
               "#E8EDF1","#10B981","#2A4060","#FFD4A0",
               "#1A3A52","#EF4444"]
BG_HEX = "#102432"


# ─── Matplotlib helpers ───────────────────────────────────────────────────────

def _mpl_defaults():
    plt.rcParams.update({
        "figure.facecolor": BG_HEX, "axes.facecolor": BG_HEX,
        "axes.edgecolor": "#2A4060", "axes.labelcolor": "#899BB7",
        "text.color": "#FFFFFF", "xtick.color": "#899BB7",
        "ytick.color": "#899BB7", "grid.color": "#2A4060",
        "grid.linewidth": 0.5, "font.family": "sans-serif", "font.size": 9,
    })


def _save(fig, w_in: float, h_in: float) -> tuple[str, float, float]:
    """Salva figura em PNG temporário. Retorna (path, w_in, h_in)."""
    tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    fig.savefig(tmp.name, dpi=150, facecolor=BG_HEX, edgecolor="none")
    plt.close(fig)
    return tmp.name, w_in, h_in


def _img_h_mm(w_mm: float, w_in: float, h_in: float) -> float:
    """Calcula altura em mm a partir da largura PDF e proporção da figura."""
    return w_mm * h_in / w_in


def build_chart_pizza(df: pd.DataFrame) -> tuple[str, float, float]:
    _mpl_defaults()
    counts = df["foco_atuacao"].value_counts().head(10)
    sizes  = counts.values
    labels = [str(l)[:30] for l in counts.index]

    FW, FH = 8.5, 5.0
    fig, ax = plt.subplots(figsize=(FW, FH))
    ax.set_facecolor(BG_HEX)

    wedges, _, autotexts = ax.pie(
        sizes, labels=None,
        colors=MPL_COLORS[:len(sizes)],
        autopct="%1.1f%%", startangle=140,
        pctdistance=0.75,
        wedgeprops=dict(linewidth=1.8, edgecolor=BG_HEX),
    )
    for at in autotexts:
        at.set_fontsize(8); at.set_color("#E8EDF4")

    patches = [mpatches.Patch(color=MPL_COLORS[i],
                              label=f"{labels[i]} ({int(sizes[i])})")
               for i in range(len(labels))]
    
    # Legend outside pie
    ax.legend(handles=patches, loc="center left", bbox_to_anchor=(1.0, 0.5),
              fontsize=8.5, frameon=False, labelcolor="#E8EDF4",
              handlelength=1.2, handletextpad=0.5)

    ax.set_title("Distribuição por Foco de Atuação",
                 color="#E8EDF4", fontsize=12, fontweight="bold", pad=12)
    fig.patch.set_facecolor(BG_HEX)
    fig.tight_layout()
    return _save(fig, FW, FH)


def build_chart_barh(df: pd.DataFrame, col: str, title: str) -> tuple[str, float, float]:
    _mpl_defaults()
    grp = (
        df.dropna(subset=[col])
        .groupby(col).agg(n=("cnpj_tratado", "count"))
        .reset_index().nlargest(10, "n").sort_values("n")
    )
    nomes  = [str(n)[:42] for n in grp[col]]
    values = grp["n"].tolist()

    FW, FH = 8.0, 4.0
    fig, ax = plt.subplots(figsize=(FW, FH))
    ax.set_facecolor(BG_HEX)
    colors = [MPL_COLORS[i % len(MPL_COLORS)] for i in range(len(nomes))]
    bars = ax.barh(nomes, values, color=colors, height=0.60,
                   edgecolor=BG_HEX, linewidth=0.8)

    for bar, val in zip(bars, values):
        ax.text(bar.get_width() + (max(values)*0.01), bar.get_y() + bar.get_height() / 2,
                f"{int(val)}", va="center", ha="left",
                color="#E8EDF4", fontsize=8.5, fontweight="bold")

    ax.set_xlabel("Nº de Fundos", color="#8B96A8", fontsize=9)
    ax.set_title(title, color="#E8EDF4", fontsize=11, fontweight="bold", pad=10)
    ax.set_xlim(0, max(values) * 1.15)
    ax.tick_params(axis="y", labelsize=8)
    ax.tick_params(axis="x", labelsize=8)
    ax.grid(axis="x", alpha=0.25, linestyle="--")
    ax.spines[["top", "right", "left"]].set_visible(False)
    fig.patch.set_facecolor(BG_HEX)
    fig.tight_layout()
    return _save(fig, FW, FH)


def build_chart_barh_taxa(df: pd.DataFrame, entity_col: str, taxa_col: str, title: str) -> tuple[str, float, float]:
    _mpl_defaults()
    grp = (
        df.dropna(subset=[entity_col, taxa_col])
        .groupby(entity_col).agg(val=(taxa_col, "mean"))
        .reset_index().nlargest(15, "val").sort_values("val", ascending=True)
    )
    nomes  = [str(n)[:42] for n in grp[entity_col]]
    values = grp["val"].tolist()

    FW = 8.0
    FH = max(4.0, len(nomes) * 0.22)
    fig, ax = plt.subplots(figsize=(FW, FH))
    ax.set_facecolor(BG_HEX)
    
    colors = [MPL_COLORS[0] if v < np.mean(values) else MPL_COLORS[2] for v in values]
    bars = ax.barh(nomes, values, color=colors, height=0.60,
                   edgecolor=BG_HEX, linewidth=0.8)

    for bar, val in zip(bars, values):
        ax.text(bar.get_width() + (max(values)*0.01), bar.get_y() + bar.get_height() / 2,
                f"{val:.3f}%", va="center", ha="left",
                color="#E8EDF4", fontsize=8.5, fontweight="bold")

    ax.set_xlabel("Taxa Média (% a.a.)", color="#8B96A8", fontsize=9)
    ax.set_title(title, color="#E8EDF4", fontsize=11, fontweight="bold", pad=10)
    ax.set_xlim(0, max(values) * 1.15)
    ax.tick_params(axis="y", labelsize=8)
    ax.tick_params(axis="x", labelsize=8)
    ax.grid(axis="x", alpha=0.25, linestyle="--")
    ax.spines[["top", "right", "left"]].set_visible(False)
    fig.patch.set_facecolor(BG_HEX)
    fig.tight_layout()
    return _save(fig, FW, FH)


# ─── Classe FPDF ─────────────────────────────────────────────────────────────

class FIDCReport(FPDF):
    def __init__(self, n_fundos: int, filters: dict):
        super().__init__(orientation="P", unit="mm", format="A4")
        self.set_auto_page_break(auto=True, margin=18)
        self.set_margins(18, 18, 18)
        try:
            self.add_font("Arial", "",  r"C:\Windows\Fonts\arial.ttf")
            self.add_font("Arial", "B", r"C:\Windows\Fonts\arialbd.ttf")
            self._ff = "Arial"
        except Exception:
            self._ff = "Helvetica"
        self.n_fundos = n_fundos
        self.filters  = filters

    def _f(self, style: str = "", size: float = 9):
        self.set_font(self._ff, style, size)

    def header(self):
        # Fundo azul marinho Solis em todas as páginas
        self.set_fill_color(*C_BG)
        self.rect(0, 0, 210, 297, "F")
        if self.page_no() == 1:
            return
        # Barra de cabeçalho com acento dourado
        self.set_fill_color(*C_ALT)
        self.rect(0, 0, 210, 11, "F")
        self.set_fill_color(*C_WARM)
        self.rect(0, 0, 210, 1.5, "F")  # linha dourada no topo
        self.set_y(3)
        self._f("B", 7.5)
        self.set_text_color(*C_WARM)
        self.cell(0, 5, "Análise de FIDCs — Dados  ·  Benchmarking Institucional de Taxas")
        self.set_y(13)

    def footer(self):
        self.set_y(-12)
        self.set_fill_color(*C_BG)
        self.rect(0, 285, 210, 12, "F")
        self._f("", 7)
        self.set_text_color(*C_MED)
        self.cell(0, 5,
            f"Fonte: Regulamentos CVM / FNET — Extração via LLM    |    "
            f"Página {self.page_no()}    |    "
            f"Gerado em {datetime.now().strftime('%d/%m/%Y %H:%M')}",
            align="C")

    def _divider(self):
        self.set_draw_color(*C_DIV)
        self.set_line_width(0.35)
        self.line(18, self.get_y() + 1, 192, self.get_y() + 1)
        self.ln(3)

    def _sec(self, txt: str):
        self.ln(3)
        self._f("B", 9.5)
        self.set_text_color(*C_ACC)
        self.cell(0, 6, txt.upper(), ln=True)
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
            self._f("", 6.5); self.set_text_color(*C_MED)
            self.cell(cw - 2 - pad*2, 4, label)
            self.set_xy(x + pad, ys + 7)
            self._f("B", 11); self.set_text_color(*C_HI)
            self.cell(cw - 2 - pad*2, 5.5, val)
            self.set_xy(x + pad, ys + 13)
            self._f("", 6); self.set_text_color(*C_MED)
            self.cell(cw - 2 - pad*2, 3.5, sub)
        self.set_y(ys + hb + 3)

    def _th(self, headers, widths):
        self.set_fill_color(*C_ACC)
        self.set_text_color(*C_WHT)
        self._f("B", 7.5)
        for h, w in zip(headers, widths):
            self.cell(w, 6, h, fill=True, align="C")
        self.ln()

    def _tr(self, vals, widths, alt: bool):
        self.set_fill_color(*(C_ALT if alt else C_BG))
        self.set_text_color(*C_HI)
        self._f("", 7.5)
        for v, w in zip(vals, widths):
            self.cell(w, 5.5, str(v), fill=True, align="C")
        self.ln()
        y = self.get_y()
        self.set_draw_color(*C_DIV)
        self.set_line_width(0.12)
        self.line(18, y, 192, y)


# ─── Seções ───────────────────────────────────────────────────────────────────

def _capa(pdf: FIDCReport):
    pdf.add_page()
    # Barra superior
    # Barra superior dourada (acento quente Solis)
    pdf.set_fill_color(*C_WARM)
    pdf.rect(0, 0, 210, 4, "F")
    # Título
    pdf.set_y(56)
    pdf._f("B", 30)
    pdf.set_text_color(*C_WARM)  # título em dourado
    pdf.cell(0, 16, "Análise de FIDCs — Dados", align="C", ln=True)
    pdf.ln(1)
    pdf._f("", 13)
    pdf.set_text_color(*C_MED)
    pdf.cell(0, 7, "Benchmarking Institucional de Taxas", align="C", ln=True)
    # Linha
    pdf.ln(7)
    pdf.set_draw_color(*C_ACC2)
    pdf.set_line_width(0.8)
    pdf.line(55, pdf.get_y(), 155, pdf.get_y())
    pdf.ln(9)
    pdf._f("B", 11)
    pdf.set_text_color(*C_HI)
    pdf.cell(0, 7, "Relatório de Benchmarking Institucional de Taxas", align="C", ln=True)
    pdf.ln(3)
    pdf._f("", 9.5)
    pdf.set_text_color(*C_MED)
    pdf.cell(0, 6, f"{pdf.n_fundos} fundos analisados  ·  Dados de regulamentos CVM / FNET",
             align="C", ln=True)
    # Caixa data
    pdf.ln(10)
    bx, bw, bh = 65, 80, 15
    by = pdf.get_y()
    pdf.set_fill_color(*C_ALT)
    pdf.set_draw_color(*C_ACC)
    pdf.set_line_width(0.3)
    pdf.rect(bx, by, bw, bh, "FD")
    pdf.set_xy(bx, by + 2)
    pdf._f("", 7.5); pdf.set_text_color(*C_MED)
    pdf.cell(bw, 4.5, "Data de Geração", align="C", ln=True)
    pdf.set_xy(bx, by + 7)
    pdf._f("B", 9); pdf.set_text_color(*C_HI)
    pdf.cell(bw, 6, datetime.now().strftime("%d/%m/%Y  %H:%M"), align="C", ln=True)
    # Filtros ativos
    f = pdf.filters
    linhas = []
    if f.get("focos"):           linhas.append(("Foco de Atuação",    ", ".join(f["focos"])))
    if f.get("administradores"): linhas.append(("Administradores",    ", ".join(f["administradores"])))
    if f.get("gestores"):        linhas.append(("Gestores",           ", ".join(f["gestores"])))
    if f.get("taxa_range"):
        lo, hi = f["taxa_range"]
        linhas.append(("Taxa Adm. (faixa)", f"{lo:.3f}% — {hi:.3f}%"))
    if linhas:
        pdf.set_y(by + bh + 10)
        pdf._f("B", 7.5); pdf.set_text_color(*C_ACC2)
        pdf.cell(0, 5, "FILTROS APLICADOS", align="C", ln=True)
        pdf.ln(1)
        for lbl, val in linhas:
            pdf._f("B", 8); pdf.set_text_color(*C_MED)
            pdf.cell(50, 5, f"  {lbl}:", align="R")
            pdf._f("", 8); pdf.set_text_color(*C_HI)
            pdf.multi_cell(0, 5, f"  {val}")
    # Rodapé capa
    pdf.set_y(278)
    pdf._f("", 7); pdf.set_text_color(*C_MED)
    pdf.cell(0, 4,
        "Extração automatizada via LLM (GPT-4o-mini)  ·  Uso interno  ·"
        "  Não constitui recomendação de investimento", align="C", ln=False)
    # Barra inferior dourada
    pdf.set_fill_color(*C_WARM)
    pdf.rect(0, 293, 210, 4, "F")


def _graficos(pdf: FIDCReport, df: pd.DataFrame):
    tmp_files = []
    try:
        IMG_W = 170.0  # mm

        # ── Pág. 2: Pizza ──────────────────────────────────────────────────────
        pdf.add_page()
        pdf.set_y(15)
        pdf._sec("Distribuição por Foco de Atuação")
        path, fw, fh = build_chart_pizza(df)
        tmp_files.append(path)
        h_mm = _img_h_mm(IMG_W, fw, fh)
        pdf.image(path, x=(210 - IMG_W) / 2, y=pdf.get_y(), w=IMG_W)
        
        # ── Pág. 3: Top 10 ────────────────────────────────────────────────────
        pdf.add_page()
        pdf.set_y(15)
        
        pdf._sec("Top 10 Gestores — por Nº de Fundos")
        path, fw, fh = build_chart_barh(df, "gestor",
                                        "Top 10 Gestores por Nº de Fundos")
        tmp_files.append(path)
        h_mm = _img_h_mm(IMG_W, fw, fh)
        pdf.image(path, x=(210 - IMG_W) / 2, y=pdf.get_y(), w=IMG_W)
        
        # ── Pág. 4: Ranking Administradores por Taxa ─────────────────────────
        pdf.add_page()
        pdf.set_y(15)
        
        pdf._sec("Ranking — Administradores por Taxa Média")
        path, fw, fh = build_chart_barh_taxa(df, "administrador", "taxa_administracao",
                                             "Taxa Média de Administração por Entidade")
        tmp_files.append(path)
        h_mm = _img_h_mm(IMG_W, fw, fh)
        pdf.image(path, x=(210 - IMG_W) / 2, y=pdf.get_y(), w=IMG_W)

        pdf.set_y(pdf.get_y() + h_mm + 5)
        
        pdf._sec("Ranking — Gestores por Taxa Média")
        path, fw, fh = build_chart_barh_taxa(df, "gestor", "taxa_gestao",
                                             "Taxa Média de Gestão por Entidade")
        tmp_files.append(path)
        h_mm = _img_h_mm(IMG_W, fw, fh)
        pdf.image(path, x=(210 - IMG_W) / 2, y=pdf.get_y(), w=IMG_W)

    finally:
        for f in tmp_files:
            try: os.unlink(f)
            except OSError: pass


def _dados(pdf: FIDCReport, df: pd.DataFrame):
    pdf.add_page()
    pdf.set_y(15)

    # KPIs
    pdf._sec("Indicadores Executivos")
    n_f = len(df)
    n_a = df["administrador"].nunique()
    n_g = df["gestor"].nunique()
    n_fo = df["foco_atuacao"].nunique()
    adm = df["taxa_administracao"] if "taxa_administracao" in df.columns else pd.Series(dtype=float)
    ges = df["taxa_gestao"]        if "taxa_gestao"        in df.columns else pd.Series(dtype=float)
    mx  = max([df[c].max() for c in TAXA_COLS
               if c in df.columns and df[c].notna().any()], default=np.nan)
    pdf._kpi_row([
        ("FIDCs Analisados",  str(n_f), f"{n_fo} segmentos"),
        ("Administradores",   str(n_a), "entidades únicas"),
        ("Gestores",          str(n_g), "entidades únicas"),
    ])
    pdf.ln(2)
    pdf._kpi_row([
        ("Média Taxa de Adm.",    fmt_pct(adm.mean()) if not adm.dropna().empty else "—", "% a.a."),
        ("Média Taxa de Gestão",  fmt_pct(ges.mean()) if not ges.dropna().empty else "—", "% a.a."),
        ("Maior Taxa Encontrada", fmt_pct(mx) if not np.isnan(mx) else "—", "% a.a."),
    ])
    pdf.ln(5)

    # Tabela estatísticas
    pdf._sec("Estatísticas Descritivas por Tipo de Taxa")
    hdrs = ["Taxa", "N", "Média", "Mediana", "Desv.Pad.", "Mín", "P25", "P75", "Máx"]
    wids = [44, 12, 16, 17, 18, 15, 15, 15, 22]
    pdf._th(hdrs, wids)
    alt = False
    for col in TAXA_COLS:
        if col not in df.columns: continue
        s = df[col].dropna()
        if s.empty: continue
        pdf._tr([
            TAXA_LABELS.get(col, col), str(len(s)),
            f"{s.mean():.4f}", f"{s.median():.4f}", f"{s.std():.4f}",
            f"{s.min():.4f}", f"{s.quantile(.25):.4f}",
            f"{s.quantile(.75):.4f}", f"{s.max():.4f}",
        ], wids, alt)
        alt = not alt
    pdf.ln(5)

    # Notas
    pdf._sec("Notas Metodológicas")
    notas = [
        "Taxas extraídas automaticamente de regulamentos CVM / FNET via LLM (GPT-4o-mini).",
        "Taxas em R$ foram descartadas; faixas escalonadas por PL foram agregadas pela média.",
        "Outliers removidos: taxas não-performance > 10% a.a. e performance > 50% a.a.",
        "Administrador e Gestor identificados pela tabela oficial de responsáveis (CVM)."
        #"Não constitui recomendação de investimento. Uso restrito a análise interna.",
    ]
    for i, n in enumerate(notas, 1):
        pdf._f("", 7.5); pdf.set_text_color(*C_MED)
        pdf.multi_cell(0, 5, f"{i}.  {n}")
        pdf.ln(0.5)


# ─── Pública ──────────────────────────────────────────────────────────────────

def gerar_pdf(df: pd.DataFrame, filters: dict) -> bytes:
    pdf = FIDCReport(n_fundos=len(df), filters=filters)
    pdf.set_title("Análise de FIDCs - Dados | Benchmarking de Taxas")
    pdf.set_author("FIDC Analytics Platform")
    _capa(pdf)       # Página 1
    _graficos(pdf, df)  # Página 2 — gráficos
    _dados(pdf, df)     # Página 3 — KPIs + estatísticas + notas
    buf = io.BytesIO()
    pdf.output(buf)
    return buf.getvalue()
