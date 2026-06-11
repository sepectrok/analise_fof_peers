"""Charts — Solis Investimentos Platform (Plotly) — Design System v3.0
Paleta fiel ao site solisinvestimentos.com.br
"""

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
from utils.data_loader import TAXA_LABELS, TAXA_COLS

# ─── Plotly Palette — Solis Institucional ────────────────────────────────────
PALETTE = {
    # Fundos
    "bg":          "#102432",
    "paper":       "#102432",
    "bg_card":     "#1A3A52",
    # Grid / linhas
    "grid":        "rgba(137,155,183,0.10)",
    # Texto
    "text":        "#899BB7",
    "text_hi":     "#FFFFFF",
    "text_light":  "#E8EDF1",
    # Cores Solis institucionais
    "blue":        "#3E5B7D",      # Azul Solis primário
    "blue_lt":     "#899BB7",      # Azul acinzentado
    "blue_dk":     "#2A4060",      # Azul escuro
    # Acento quente (dourado / amber)
    "amber":       "#FFC36A",      # Dourado Solis
    "orange":      "#F89B66",      # Laranja Solis
    "amber_lt":    "#FFD4A0",
    # Status
    "green":       "#10B981",
    "red":         "#EF4444",
    # Papel de cada série
    "solis":       "#FFC36A",      # Solis destacado em DOURADO
    "mercado":     "#899BB7",      # Mercado em azul acinzentado
    # Colorway sequencial
    "colors": [
        "#3E5B7D",   # azul Solis
        "#FFC36A",   # dourado
        "#899BB7",   # azul acinzentado
        "#F89B66",   # laranja
        "#E8EDF1",   # cinza claro
        "#10B981",   # verde
        "#2A4060",   # azul escuro
        "#FFD4A0",   # âmbar claro
    ],
}


def _base_layout(title: str = "", height: int = 420) -> dict:
    layout = dict(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor=PALETTE["bg"],
        font=dict(family="Figtree, Open Sans, sans-serif", size=12, color=PALETTE["text"]),
        height=height,
        margin=dict(l=16, r=24, t=44 if title else 20, b=36),
        legend=dict(
            bgcolor="rgba(0,0,0,0)",
            font=dict(size=12, color=PALETTE["text_hi"]),
            orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0,
        ),
        colorway=PALETTE["colors"],
        xaxis=dict(
            gridcolor=PALETTE["grid"], zerolinecolor=PALETTE["grid"],
            tickfont=dict(size=11, color=PALETTE["text"]),
            title_font=dict(size=12, color=PALETTE["text"]),
            linecolor="rgba(0,0,0,0)", showline=False,
        ),
        yaxis=dict(
            gridcolor=PALETTE["grid"], zerolinecolor=PALETTE["grid"],
            tickfont=dict(size=11, color=PALETTE["text"]),
            title_font=dict(size=12, color=PALETTE["text"]),
            linecolor="rgba(0,0,0,0)", showline=False,
        ),
        hoverlabel=dict(
            bgcolor="#1A3A52",
            bordercolor="rgba(137,155,183,0.25)",
            font=dict(family="Figtree, sans-serif", size=12, color=PALETTE["text_hi"]),
        ),
    )
    if title:
        layout["title"] = dict(
            text=title,
            font=dict(family="Figtree, sans-serif", size=15, color=PALETTE["text_hi"]),
            x=0.01, xanchor="left", y=0.98,
        )
    return layout


def histogram_taxa(df: pd.DataFrame, col: str, height: int = 400,
                   df_solis: pd.DataFrame = None) -> go.Figure:
    """Elegant histogram with stat markers. Accepts optional df_solis for Solis mean line."""
    label = TAXA_LABELS.get(col, col)
    s = df[col].dropna()
    if s.empty:
        return go.Figure()

    fig = go.Figure()
    fig.add_trace(go.Histogram(
        x=s, nbinsx=35, name="Distribuição",
        marker=dict(
            color=PALETTE["blue"],
            opacity=0.75,
            line=dict(color=PALETTE["bg"], width=0.8)
        ),
    ))

    stat_lines = [
        (s.mean(),   PALETTE["amber"],  "Média Geral",  14),
        (s.median(), PALETTE["green"],  "Mediana",      -18),
    ]

    # Linha da média Solis (se fornecido)
    if df_solis is not None and not df_solis.empty and col in df_solis.columns:
        s_solis = df_solis[col].dropna()
        if not s_solis.empty:
            stat_lines.append((s_solis.mean(), "rgba(96,165,250,1.0)", "Média Solis", 46))

    for val, color, label_v, yshift_val in stat_lines:
        fig.add_vline(x=val, line=dict(color=color, dash="dot", width=1.5),
                      annotation=dict(
                          text=f"{label_v}: {val:.3f}%",
                          font=dict(size=12, color=color),
                          showarrow=False, yshift=yshift_val,
                      ))

    layout = _base_layout(f"Distribuição — {label}", height)
    layout["bargap"] = 0.08
    fig.update_layout(**layout)

    max_val = s.quantile(0.98)
    if pd.notna(max_val) and max_val > 0:
        fig.update_xaxes(title_text=f"{label} (% a.a.)", range=[0, max_val * 1.1])
    else:
        fig.update_xaxes(title_text=f"{label} (% a.a.)")

    fig.update_yaxes(title_text="Fundos")
    return fig


def boxplot_by_group(df: pd.DataFrame, col: str, group_col: str, height: int = 420) -> go.Figure:
    """Boxplot grouped by a categorical column."""
    label = TAXA_LABELS.get(col, col)
    df_v = df[[col, group_col]].dropna()
    if df_v.empty:
        return go.Figure()

    fig = px.box(df_v, x=group_col, y=col,
                 color_discrete_sequence=[PALETTE["blue"]],
                 points="outliers",
                 labels={col: f"{label} (% a.a.)", group_col: ""},
                 template=None)
    fig.update_traces(
        marker=dict(size=3, opacity=0.5, color=PALETTE["amber"]),
        line_color=PALETTE["blue"],
        fillcolor="rgba(62,91,125,0.18)",
    )
    fig.update_layout(**_base_layout(f"Boxplot — {label}", height))
    fig.update_xaxes(tickangle=-30, tickfont=dict(size=9))
    return fig


def violin_taxa(df: pd.DataFrame, col: str, height: int = 360) -> go.Figure:
    label = TAXA_LABELS.get(col, col)
    s = df[col].dropna()
    if s.empty:
        return go.Figure()
    fig = go.Figure(go.Violin(
        y=s, name=label, box_visible=True, meanline_visible=True,
        fillcolor="rgba(62,91,125,0.18)", line_color=PALETTE["blue"],
        points="outliers", marker=dict(color=PALETTE["amber"], size=3, opacity=0.5),
    ))
    fig.update_layout(**_base_layout(f"Violin — {label}", height))
    fig.update_yaxes(title_text=f"{label} (% a.a.)")
    return fig


def scatter_two_taxas(df: pd.DataFrame, col_x: str, col_y: str,
                       color_col: str = "foco_atuacao", height: int = 420) -> go.Figure:
    df_v = df[[col_x, col_y, color_col, "nome_curto"]].dropna(subset=[col_x, col_y])
    if df_v.empty:
        return go.Figure()
    fig = px.scatter(df_v, x=col_x, y=col_y, color=color_col,
                     hover_name="nome_curto",
                     labels={col_x: TAXA_LABELS.get(col_x, col_x),
                             col_y: TAXA_LABELS.get(col_y, col_y)},
                     color_discrete_sequence=PALETTE["colors"])
    fig.update_traces(marker=dict(size=7, opacity=0.75, line=dict(width=0.5, color=PALETTE["bg"])))
    fig.update_layout(**_base_layout(
        f"{TAXA_LABELS.get(col_x,col_x)} × {TAXA_LABELS.get(col_y,col_y)}", height))
    return fig


def heatmap_corr(df: pd.DataFrame, height: int = 420) -> go.Figure:
    cols = [c for c in TAXA_COLS if c in df.columns and df[c].notna().sum() >= 5]
    if len(cols) < 2:
        return go.Figure()
    corr = df[cols].corr()
    labels = [TAXA_LABELS.get(c, c).replace("Taxa de ", "").replace("Taxa Máx. de ", "") for c in cols]
    fig = go.Figure(go.Heatmap(
        z=corr.values, x=labels, y=labels,
        colorscale=[
            [0,   PALETTE["blue"]],
            [0.5, PALETTE["bg"]],
            [1,   PALETTE["amber"]],
        ],
        zmid=0, text=np.round(corr.values, 2), texttemplate="%{text}",
        textfont=dict(size=10, color=PALETTE["text_hi"]),
        colorbar=dict(thickness=10, tickfont=dict(size=9)),
    ))
    fig.update_layout(**_base_layout("Correlação entre Taxas", height))
    return fig


def radar_fund(df: pd.DataFrame, cnpjs: list, height: int = 420) -> go.Figure:
    """Radar chart for one or more funds."""
    cols = [c for c in TAXA_COLS if c in df.columns]
    labels = [TAXA_LABELS.get(c, c).replace("Taxa de ", "") for c in cols]

    # Guard: sem colunas de taxa disponíveis, retorna figura vazia
    if not cols:
        return go.Figure()

    fig = go.Figure()
    for i, cnpj in enumerate(cnpjs):
        row = df[df["cnpj_tratado"] == cnpj]
        if row.empty:
            continue
        vals = [row[c].values[0] if c in row.columns else np.nan for c in cols]
        vals_clean = [v if not np.isnan(v) else 0 for v in vals]
        nome = row["nome_curto"].values[0] if "nome_curto" in row.columns else cnpj
        color = PALETTE["colors"][i % len(PALETTE["colors"])]

        # Parse hex to rgb
        r = int(color[1:3], 16)
        g = int(color[3:5], 16)
        b = int(color[5:7], 16)

        fig.add_trace(go.Scatterpolar(
            r=vals_clean + [vals_clean[0]],
            theta=labels + [labels[0]],
            fill="toself",
            name=nome[:40],
            line=dict(color=color, width=2),
            fillcolor=f"rgba({r},{g},{b},0.12)",
            hovertemplate="%{theta}: %{r:.3f}%<extra>%{fullData.name}</extra>",
        ))

    fig.update_layout(
        **_base_layout("Radar de Taxas", height),
        polar=dict(
            bgcolor=PALETTE["bg_card"],
            radialaxis=dict(
                visible=True, gridcolor=PALETTE["grid"],
                tickfont=dict(size=8, color=PALETTE["text"]),
                ticksuffix="%",
            ),
            angularaxis=dict(
                gridcolor=PALETTE["grid"],
                tickfont=dict(size=9, color=PALETTE["text_hi"]),
            ),
        ),
    )
    return fig


def bar_ranking(df_agg: pd.DataFrame, val_col: str, name_col: str,
                title: str = "", top_n: int = 15, height: int = None, is_percent: bool = True,
                highlight_name: str = "Solis", is_currency: bool = False) -> go.Figure:
    """Premium horizontal bar chart ranking — Solis highlighted in amber."""
    df_sorted = df_agg.dropna(subset=[val_col]).nlargest(top_n, val_col).iloc[::-1]
    n = len(df_sorted)
    if height is None:
        height = max(400, n * 32 + 80)

    colors = []
    for name in df_sorted[name_col]:
        if highlight_name.lower() in str(name).lower():
            colors.append(PALETTE["amber"])        # Solis em dourado
        else:
            colors.append("rgba(62,91,125,0.35)")  # Outros em azul translúcido

    def fmt_val(v):
        if pd.isna(v): return ""
        if is_percent:  return f"{v:.3f}%"
        if is_currency:
            if v >= 1e9: return f"R$ {v/1e9:.2f}B"
            if v >= 1e6: return f"R$ {v/1e6:.2f}M"
            return f"R$ {v:,.0f}"
        return str(int(v))

    fig = go.Figure(go.Bar(
        x=df_sorted[val_col],
        y=df_sorted[name_col],
        orientation="h",
        marker=dict(
            color=colors,
            line=dict(color="rgba(0,0,0,0)", width=0),
            opacity=0.9,
        ),
        text=[fmt_val(v) for v in df_sorted[val_col]],
        textposition="outside",
        textfont=dict(size=11, color=PALETTE["text"]),
    ))
    _layout = _base_layout(title, height)
    for _k in ("margin", "font", "legend", "bargap", "colorway"):
        _layout.pop(_k, None)
    _layout["bargap"] = 0.4
    fig.update_layout(
        **_layout,
        margin=dict(l=220, r=80, t=50 if title else 20, b=36),
        font=dict(family="Figtree, sans-serif", size=12, color=PALETTE["text"]),
    )
    fig.update_xaxes(
        title_text="% a.a." if is_percent else "",
        title_font=dict(size=12, color=PALETTE["text"]),
        showgrid=False,
        tickfont=dict(size=11),
    )
    fig.update_yaxes(tickfont=dict(size=11), automargin=True)
    return fig


def bar_ranking_desc(df_agg: pd.DataFrame, val_col: str, name_col: str,
                     title: str = "", top_n: int = 15, height: int = 420) -> go.Figure:
    """Horizontal bar chart — descending."""
    df_sorted = df_agg.dropna(subset=[val_col]).nlargest(top_n, val_col)
    return bar_ranking(df_sorted, val_col, name_col, title, top_n, height)


def donut_foco(df: pd.DataFrame, height: int = 380) -> go.Figure:
    counts = df["foco_atuacao"].value_counts().head(10)
    fig = go.Figure(go.Pie(
        labels=counts.index,
        values=counts.values,
        hole=0.6,
        marker=dict(
            colors=PALETTE["colors"] * 3,
            line=dict(color=PALETTE["bg"], width=2),
        ),
        textfont=dict(size=9),
        hovertemplate="%{label}<br>%{value} fundos (%{percent})<extra></extra>",
    ))
    fig.update_layout(**_base_layout("Distribuição por Foco", height))
    fig.update_layout(legend=dict(orientation="v", font=dict(size=9)))
    return fig


def donut_market_share_solis(df_solis: pd.DataFrame, df_mercado: pd.DataFrame, height: int = 380) -> go.Figure:
    """Donut chart — Solis vs Mercado por AuM. Solis em dourado."""
    aum_solis   = df_solis["Valor_PL"].sum()   if "Valor_PL" in df_solis.columns   else 0
    aum_mercado = df_mercado["Valor_PL"].sum() if "Valor_PL" in df_mercado.columns else 0

    if aum_solis == 0 and aum_mercado == 0:
        return go.Figure()

    fig = go.Figure(go.Pie(
        labels=["Solis Investimentos", "Mercado"],
        values=[aum_solis, aum_mercado],
        hole=0.62,
        marker=dict(
            colors=[PALETTE["amber"], "rgba(62,91,125,0.3)"],
            line=dict(color=PALETTE["bg"], width=2),
        ),
        textfont=dict(size=12, color=PALETTE["text_hi"]),
        hovertemplate="%{label}<br>R$ %{value:,.2f} (%{percent})<extra></extra>",
    ))

    total_aum = aum_solis + aum_mercado
    pct_solis = (aum_solis / total_aum * 100) if total_aum > 0 else 0

    fig.update_layout(**_base_layout("Market Share — AuM Total", height))
    fig.update_layout(
        legend=dict(
            orientation="h", yanchor="bottom", y=-0.1,
            xanchor="center", x=0.5, font=dict(size=11),
        ),
        annotations=[dict(
            text=f"<b>{pct_solis:.1f}%</b>",
            x=0.5, y=0.5,
            font=dict(size=24, color=PALETTE["amber"], family="Figtree, sans-serif"),
            showarrow=False,
        )],
    )
    return fig


def heatmap_entity_taxa(df_agg: pd.DataFrame, entity_col: str, height: int = 500) -> go.Figure:
    """Heatmap: entity (rows) × taxa type (cols)."""
    taxa_cols = [c for c in TAXA_COLS if c in df_agg.columns]
    labels = [TAXA_LABELS.get(c, c).replace("Taxa de ", "") for c in taxa_cols]
    entities = df_agg[entity_col].tolist()

    z = df_agg[taxa_cols].values
    # Usa pd.isna (seguro para qualquer dtype, incluindo object)
    # ao invés de np.isnan que falha em arrays com strings
    z_float = pd.DataFrame(df_agg[taxa_cols]).to_numpy(dtype=float, na_value=float("nan"))
    text_vals = np.where(
        pd.isna(z_float),
        "—",
        np.round(z_float, 3).astype(str) + "%"
    )
    fig = go.Figure(go.Heatmap(
        z=z_float, x=labels, y=entities,
        colorscale=[
            [0,   PALETTE["blue"]],
            [0.5, "rgba(26,58,82,0.8)"],
            [1,   PALETTE["amber"]],
        ],
        colorbar=dict(thickness=10, ticksuffix="%", tickfont=dict(size=8)),
        text=text_vals,
        texttemplate="%{text}",
        textfont=dict(size=8, color=PALETTE["text_hi"]),
        hovertemplate="%{y}<br>%{x}: %{z:.3f}%<extra></extra>",
    ))
    fig.update_layout(**_base_layout(f"Heatmap — {entity_col.replace('_',' ').title()}", height))
    fig.update_yaxes(tickfont=dict(size=8), autorange="reversed")
    return fig


def boxplot_solis_vs_mercado(df_solis: pd.DataFrame, df_mercado: pd.DataFrame, col: str, height: int = 440) -> go.Figure:
    """Side-by-side boxplots — Mercado em azul, Solis em dourado."""
    label = TAXA_LABELS.get(col, col).replace("Taxa de ", "")
    fig = go.Figure()

    s_mercado = df_mercado[col].dropna()
    if not s_mercado.empty:
        fig.add_trace(go.Box(
            y=s_mercado, name="Mercado",
            marker_color=PALETTE["mercado"],
            boxmean=True,
            line_width=1.5,
            fillcolor="rgba(137,155,183,0.12)",
            marker=dict(size=4, opacity=0.5),
        ))

    s_solis = df_solis[col].dropna()
    if not s_solis.empty:
        fig.add_trace(go.Box(
            y=s_solis, name="Solis",
            marker_color=PALETTE["solis"],
            boxmean=True,
            line_width=1.5,
            fillcolor="rgba(255,195,106,0.12)",
            marker=dict(size=4, opacity=0.5),
        ))

    layout = _base_layout(f"Comparativo — {label}", height)
    layout["margin"] = dict(l=40, r=40, t=60, b=36)
    fig.update_layout(**layout)
    fig.update_yaxes(title_text="% a.a.")
    fig.update_xaxes(tickfont=dict(size=13))
    return fig


def multi_box_taxas(df: pd.DataFrame, height: int = 400) -> go.Figure:
    """Side-by-side boxplots for all taxa columns."""
    cols = [c for c in TAXA_COLS if c in df.columns and df[c].notna().sum() >= 5]
    if not cols:
        return go.Figure()
    fig = go.Figure()
    for i, col in enumerate(cols):
        s = df[col].dropna()
        color = PALETTE["colors"][i % len(PALETTE["colors"])]
        r = int(color[1:3], 16)
        g = int(color[3:5], 16)
        b = int(color[5:7], 16)
        fig.add_trace(go.Box(
            y=s,
            name=TAXA_LABELS.get(col, col).replace("Taxa de ", ""),
            marker_color=color,
            boxmean="sd",
            line_width=1.2,
            fillcolor=f"rgba({r},{g},{b},0.12)",
        ))
    fig.update_layout(**_base_layout("Comparativo de Taxas", height))
    fig.update_yaxes(title_text="% a.a.", title_font=dict(size=9, color=PALETTE["text"]))
    return fig


def bar_foco_comparativo(df_solis: pd.DataFrame, df_mercado: pd.DataFrame, height: int = None) -> go.Figure:
    """Grouped horizontal bar — Solis (dourado) vs Mercado (azul) with subplots to avoid scale squishing."""
    counts_solis   = df_solis["foco_atuacao"].value_counts()
    counts_mercado = df_mercado["foco_atuacao"].value_counts()

    top_focos = counts_mercado.nlargest(10).index.tolist()
    for f in counts_solis.index:
        if f not in top_focos:
            top_focos.append(f)

    df_plot = pd.DataFrame({
        "Foco":    top_focos,
        "Mercado": [counts_mercado.get(f, 0) for f in top_focos],
        "Solis":   [counts_solis.get(f, 0)   for f in top_focos],
    }).sort_values("Mercado", ascending=True)

    n_cats  = len(df_plot)
    chart_h = height or max(500, n_cats * 45 + 100)

    fig = make_subplots(
        rows=1, cols=2, 
        shared_yaxes=True,
        horizontal_spacing=0.03,
        subplot_titles=("Mercado (Qtd)", "Solis (Qtd)"),
        column_widths=[0.6, 0.4]
    )
    
    fig.add_trace(go.Bar(
        y=df_plot["Foco"], x=df_plot["Mercado"], name="Mercado", orientation="h",
        marker_color="rgba(137,155,183,0.45)",
        text=df_plot["Mercado"].astype(str),
        textposition="inside",
        insidetextanchor="end",
        textfont=dict(size=11, color=PALETTE["text_hi"]),
    ), row=1, col=1)
    
    fig.add_trace(go.Bar(
        y=df_plot["Foco"], x=df_plot["Solis"], name="Solis", orientation="h",
        marker_color=PALETTE["amber"],
        text=df_plot["Solis"].astype(str),
        textposition="inside",
        insidetextanchor="start",
        textfont=dict(size=11, color="#102432"),
    ), row=1, col=2)

    _layout = _base_layout("", chart_h)
    for _k in ("margin", "font", "legend", "barmode", "bargap", "bargroupgap"):
        _layout.pop(_k, None)
        
    _layout["bargap"] = 0.28
    _layout["font"] = dict(family="Figtree, sans-serif", size=12, color=PALETTE["text"])
    _layout["legend"] = dict(
        orientation="h", yanchor="bottom", y=1.1, xanchor="left", x=0,
        font=dict(size=12), bgcolor="rgba(0,0,0,0)",
    )
    
    fig.update_layout(
        **_layout,
        margin=dict(l=220, r=40, t=60, b=36),
        showlegend=False
    )
    
    # Format subplot titles
    for annotation in fig['layout']['annotations']: 
        annotation['font'] = dict(size=12, color=PALETTE['text_hi'])
        
    fig.update_xaxes(showgrid=False, title_text="", tickfont=dict(size=11), row=1, col=1)
    fig.update_xaxes(showgrid=False, title_text="", tickfont=dict(size=11), row=1, col=2)
    fig.update_yaxes(tickfont=dict(size=11), automargin=True, row=1, col=1)
    
    return fig
