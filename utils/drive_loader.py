"""
Drive Loader — FoF Peers Dashboard
Baixa arquivos parquet do Google Drive quando não encontrados localmente.
Em desenvolvimento local, usa os arquivos locais diretamente.
No Streamlit Cloud, baixa para /tmp e cacheia em memória.
"""

import os
import logging
import pandas as pd
import streamlit as st

logger = logging.getLogger(__name__)

# ─── Diretório base do projeto ────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ─── Mapeamento: nome do arquivo → ID do Google Drive ────────────────────────
DRIVE_IDS: dict[str, str] = {
    "blc_total_detail":     "1TIBeGxkUmU7FWadZlcKDV8R4kOxhD8Kg",
    "blc_total_pivot":      "1rGXDq14VASFaAdqOILeAP4JxLpBbffaz",
    "check_pl":             "1huyqtuToBuYsOT2gYajmi5jSvvn-iy0Z",
    "cadastro_fof":         "1LAnXXt2dHwAovjxXsNrR_fH56YJEmkhB",
    "fundos_peers_carteira":"1siKr21tYEo9GMVZtz-etHq9lVoQjMx6y",
}

# Pasta de cache para o Streamlit Cloud (gravável)
_CACHE_DIR = os.environ.get("PARQUET_CACHE_DIR", "/tmp/fof_data")


def _ensure_cache_dir() -> None:
    os.makedirs(_CACHE_DIR, exist_ok=True)


def _local_path(base_name: str) -> str:
    """Caminho local do arquivo (em desenvolvimento)."""
    return os.path.join(BASE_DIR, f"{base_name}.parquet")


def _cache_path(base_name: str) -> str:
    """Caminho de cache no servidor (Streamlit Cloud)."""
    return os.path.join(_CACHE_DIR, f"{base_name}.parquet")


def _download_from_drive(base_name: str, dest_path: str) -> None:
    """Baixa o arquivo do Google Drive via gdown."""
    try:
        import gdown  # noqa: PLC0415
    except ImportError as exc:
        raise ImportError(
            "Pacote 'gdown' não encontrado. Adicione 'gdown' ao requirements.txt."
        ) from exc

    file_id = DRIVE_IDS.get(base_name)
    if not file_id:
        raise ValueError(f"ID do Drive não cadastrado para '{base_name}'.")

    url = f"https://drive.google.com/uc?id={file_id}"
    logger.info("Baixando %s do Google Drive…", base_name)

    _ensure_cache_dir()
    gdown.download(url, dest_path, quiet=False, fuzzy=True)

    if not os.path.exists(dest_path) or os.path.getsize(dest_path) == 0:
        raise RuntimeError(
            f"Download falhou ou arquivo vazio: {base_name}.parquet\n"
            "Verifique se o arquivo está compartilhado como 'Qualquer pessoa com o link'."
        )


@st.cache_data(show_spinner=False)
def load_parquet(base_name: str) -> pd.DataFrame:
    """
    Carrega um arquivo parquet com fallback automático:
      1. Arquivo local (desenvolvimento)
      2. Cache em /tmp (já baixado anteriormente na sessão do servidor)
      3. Download do Google Drive

    Parameters
    ----------
    base_name : str
        Nome do arquivo sem extensão (ex: 'blc_total_detail').

    Returns
    -------
    pd.DataFrame
    """
    # 1️⃣ Arquivo local (desenvolvimento)
    local = _local_path(base_name)
    if os.path.exists(local):
        return pd.read_parquet(local, engine="pyarrow")

    # 2️⃣ Cache do servidor (já foi baixado antes nesta instância)
    cached = _cache_path(base_name)
    if os.path.exists(cached) and os.path.getsize(cached) > 0:
        return pd.read_parquet(cached, engine="pyarrow")

    # 3️⃣ Download do Google Drive
    if base_name not in DRIVE_IDS:
        raise FileNotFoundError(
            f"Arquivo '{base_name}.parquet' não encontrado localmente "
            f"e não possui ID do Drive cadastrado."
        )

    _download_from_drive(base_name, cached)
    return pd.read_parquet(cached, engine="pyarrow")
