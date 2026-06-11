"""Sidebar — Solis Investimentos Platform — Design System v3.0
Paleta fiel ao site solisinvestimentos.com.br
"""

import streamlit as st
import pandas as pd
import os
import base64


def load_css():
    css_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "styles", "main.css")
    with open(css_path, encoding="utf-8") as f:
        css = f.read()
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)

    # ── Botão flutuante para abrir/fechar a sidebar ──────────────────────────
    import streamlit.components.v1 as components
    components.html("""
    <script>
    (function() {
        var doc = window.parent.document;
        var win = window.parent;

        function reactClick(el) {
            el.dispatchEvent(new MouseEvent('click', {
                bubbles: true, cancelable: true, view: win
            }));
        }

        function getSidebarWidth() {
            var sb = doc.querySelector('[data-testid="stSidebar"]');
            return sb ? sb.getBoundingClientRect().width : 0;
        }

        function toggleSidebar() {
            var sbWidth = getSidebarWidth();
            var clicked = false;

            if (sbWidth > 50) {
                var closeCandidates = [
                    '[data-testid="stSidebar"] [data-testid="baseButton-header"]',
                    '[data-testid="stSidebar"] button[aria-label]',
                    '[data-testid="stSidebarContent"] button',
                    '[data-testid="stSidebar"] button',
                ];
                for (var i = 0; i < closeCandidates.length && !clicked; i++) {
                    var els = doc.querySelectorAll(closeCandidates[i]);
                    for (var j = 0; j < els.length && !clicked; j++) {
                        var r = els[j].getBoundingClientRect();
                        if (r.width > 0 && r.height > 0) {
                            reactClick(els[j]);
                            clicked = true;
                        }
                    }
                }
            } else {
                var openCandidates = [
                    '[data-testid="collapsedControl"] button',
                    '[data-testid="stSidebarCollapsedControl"] button',
                    '[data-testid="collapsedControl"]',
                    'header [data-testid="baseButton-header"]',
                    'header button',
                ];
                for (var k = 0; k < openCandidates.length && !clicked; k++) {
                    var els2 = doc.querySelectorAll(openCandidates[k]);
                    for (var l = 0; l < els2.length && !clicked; l++) {
                        reactClick(els2[l]);
                        clicked = true;
                    }
                }
            }

            if (!clicked) {
                doc.body.dispatchEvent(new KeyboardEvent('keydown', {
                    key: '[', code: 'BracketLeft', keyCode: 219, which: 219,
                    bubbles: true, cancelable: true
                }));
            }

            setTimeout(updateBtnIcon, 200);
        }

        function updateBtnIcon() {
            var btn = doc.getElementById('_solis_sidebar_toggle');
            if (!btn) return;
            btn.innerHTML = getSidebarWidth() > 50 ? '&#8249;' : '&#9776;';
            btn.title = getSidebarWidth() > 50 ? 'Fechar menu lateral' : 'Abrir menu lateral';
        }

        function createToggleBtn() {
            var existingBtn = doc.getElementById('_solis_sidebar_toggle');
            if (existingBtn) {
                existingBtn.onclick = function(e) {
                    e.stopPropagation();
                    toggleSidebar();
                };
                updateBtnIcon();
                return;
            }

            var btn = doc.createElement('button');
            btn.id = '_solis_sidebar_toggle';
            btn.innerHTML = '&#9776;';
            btn.title = 'Abrir / Fechar menu lateral';
            btn.style.cssText = [
                'position:fixed', 'top:10px', 'left:10px',
                'z-index:2147483647', 'width:36px', 'height:36px',
                'background:#1A3A52',
                'color:#899BB7',
                'border:1px solid rgba(137,155,183,0.25)',
                'border-radius:8px', 'font-size:18px', 'cursor:pointer',
                'display:flex', 'align-items:center', 'justify-content:center',
                'box-shadow:0 2px 12px rgba(16,36,50,0.5)',
                'transition:all 0.2s ease',
                'line-height:1'
            ].join(';');

            btn.onmouseover = function() {
                btn.style.background = '#3E5B7D';
                btn.style.color = '#FFC36A';
                btn.style.borderColor = 'rgba(255,195,106,0.4)';
                btn.style.boxShadow = '0 2px 12px rgba(255,195,106,0.2)';
            };
            btn.onmouseout = function() {
                btn.style.background = '#1A3A52';
                btn.style.color = '#899BB7';
                btn.style.borderColor = 'rgba(137,155,183,0.25)';
                btn.style.boxShadow = '0 2px 12px rgba(16,36,50,0.5)';
            };
            btn.onclick = function(e) {
                e.stopPropagation();
                toggleSidebar();
            };

            doc.body.appendChild(btn);
            updateBtnIcon();
        }

        createToggleBtn();
        setTimeout(createToggleBtn, 500);
        setTimeout(updateBtnIcon, 1000);

        var obs = new MutationObserver(function() {
            createToggleBtn();
        });
        obs.observe(doc.body, { childList: true, subtree: false });
    })();
    </script>
    """, height=1, scrolling=False)


def _get_logo_html() -> str:
    """Retorna HTML do logo SVG vertical (site oficial) ou PNG fallback."""
    # 1. Tenta SVG vertical baixado do site
    base_dir = os.path.dirname(os.path.dirname(__file__))
    for logo_file in ["logo_solis_vertical.svg", "logo_solis_v.png", "SOLIS_BRANDMARK.png"]:
        logo_path = os.path.join(base_dir, logo_file)
        if os.path.exists(logo_path):
            with open(logo_path, "rb") as f:
                data = f.read()
            b64 = base64.b64encode(data).decode()
            if logo_file.endswith(".svg"):
                mime = "image/svg+xml"
                height = "80px"
            else:
                mime = "image/png"
                height = "64px"
            return (
                f'<img src="data:{mime};base64,{b64}" '
                f'style="height:{height}; width:auto; display:block; margin:0 auto 8px; '
                f'filter:brightness(0) invert(1);" '
                f'alt="Solis Investimentos" />'
            )

    # Fallback texto com gradiente
    return (
        '<div style="font-family:Figtree,sans-serif; font-weight:700; font-size:1.3rem; '
        'background:linear-gradient(125deg,#E8EDF1,#F89B66,#FFC36A); '
        '-webkit-background-clip:text; -webkit-text-fill-color:transparent; '
        'background-clip:text; display:inline-block; text-align:center; width:100%;">'
        'SOLIS</div>'
    )


def render_sidebar(df: pd.DataFrame, show_date_filter: bool = True) -> dict:
    """Render the sidebar with filters. Returns a dict of active filter values."""
    with st.sidebar:
        # ── Logo SVG vertical (site oficial) ─────────────────────────────────
        logo_html = _get_logo_html()
        st.markdown(f"""
        <div class="sidebar-logo">
            {logo_html}
            <div class="logo-sub">Inteligência Competitiva · FIDCs</div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown(
            '<div class="sidebar-section-title">Filtros</div>',
            unsafe_allow_html=True,
        )

        data_base_sel = None
        if show_date_filter and "Data_Posicao" in df.columns:
            datas = sorted(df["Data_Posicao"].dropna().unique(), reverse=True)
            if datas:
                data_labels = [pd.to_datetime(d).strftime("%b/%Y").capitalize() for d in datas]
                data_map = dict(zip(data_labels, datas))
                selected_label = st.selectbox(
                    "Data Base",
                    options=data_labels,
                    index=0,
                )
                data_base_sel = data_map[selected_label]

        incluir_liquidacao = st.toggle("Incluir fundos em liquidação", value=True)
        filtrar_pl = st.toggle("Apenas fundos com PL Validado (Check PL = OK)", value=False)

        focos_disponiveis = sorted(df["foco_atuacao"].dropna().unique().tolist())
        focos = st.multiselect(
            "Segmento",
            options=focos_disponiveis,
            default=[],
            placeholder="Todos",
        )

        adm_disponiveis = sorted(df["administrador"].dropna().unique().tolist())
        administradores = st.multiselect(
            "Administrador",
            options=adm_disponiveis,
            default=[],
            placeholder="Todos",
        )

        ges_disponiveis = sorted(df["gestor"].dropna().unique().tolist())
        gestores = st.multiselect(
            "Gestor",
            options=ges_disponiveis,
            default=[],
            placeholder="Todos",
        )

        # ── Stats ─────────────────────────────────────────────────────────────
        st.markdown("---")
        st.markdown(f"""
        <div class="sidebar-stats">
            <div class="sidebar-stat">
                <span class="stat-value">{df['nome_fundo'].nunique()}</span>
                <span class="stat-label">FIDCs</span>
            </div>
            <div class="sidebar-stat">
                <span class="stat-value">{df['administrador'].nunique()}</span>
                <span class="stat-label">Admins</span>
            </div>
            <div class="sidebar-stat">
                <span class="stat-value">{df['gestor'].nunique()}</span>
                <span class="stat-label">Gestores</span>
            </div>
            <div class="sidebar-stat">
                <span class="stat-value">{df['foco_atuacao'].nunique()}</span>
                <span class="stat-label">Segmentos</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("---")
        st.markdown("""
        <div style="font-size:0.6rem; color:var(--text-muted); text-align:center;
                    letter-spacing:0.5px; line-height:1.6;">
            Fonte: Regulamentos CVM / FNET<br>
            <span style="opacity:0.6;">© Solis Investimentos</span>
        </div>
        """, unsafe_allow_html=True)

    filters_dict = {
        "data_base":           data_base_sel,
        "incluir_liquidacao":  incluir_liquidacao,
        "filtrar_pl":          filtrar_pl,
        "focos":               focos,
        "administradores":     administradores,
        "gestores":            gestores,
    }
    return filters_dict


def apply_sidebar_filters(df: pd.DataFrame, filters: dict) -> pd.DataFrame:
    """Apply the sidebar filter selections to df."""
    f = df.copy()
    if filters.get("data_base") is not None and "Data_Posicao" in f.columns:
        f = f[f["Data_Posicao"] == filters["data_base"]]
    if not filters.get("incluir_liquidacao", False) and "Situacao" in f.columns:
        f = f[~f["Situacao"].astype(str).str.contains("Liquida", case=False, na=False)]
    if filters.get("filtrar_pl", False) and "Check_PL" in f.columns:
        f = f[f["Check_PL"] == "OK"]
    if filters.get("focos"):
        f = f[f["foco_atuacao"].isin(filters["focos"])]
    if filters.get("administradores"):
        f = f[f["administrador"].isin(filters["administradores"])]
    if filters.get("gestores"):
        f = f[f["gestor"].isin(filters["gestores"])]
    return f
