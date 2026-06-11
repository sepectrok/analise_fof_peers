"""
Drive Loader — FoF Peers Dashboard
Baixa arquivos parquet do Google Drive quando não encontrados localmente.
Em desenvolvimento local, usa os arquivos locais diretamente.
No Streamlit Cloud, baixa para /tmp e cacheia em memória.

Usa requests (já dependência do Streamlit) com a URL drive.usercontent.google.com,
que bypassa automaticamente o aviso de vírus para arquivos grandes sem precisar
de gdown ou tokens de confirmação.
"""

import os
import logging
import requests
import pandas as pd
import streamlit as st

logger = logging.getLogger(__name__)

# ─── Diretório base do projeto ────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ─── Mapeamento: nome do arquivo → ID do Google Drive ────────────────────────
DRIVE_IDS: dict[str, str] = {
    "blc_total_detail":      "1TIBeGxkUmU7FWadZlcKDV8R4kOxhD8Kg",
    "blc_total_pivot":       "1rGXDq14VASFaAdqOILeAP4JxLpBbffaz",
    "check_pl":              "1huyqtuToBuYsOT2gYajmi5jSvvn-iy0Z",
    "cadastro_fof":          "1LAnXXt2dHwAovjxXsNrR_fH56YJEmkhB",
    "fundos_peers_carteira": "1siKr21tYEo9GMVZtz-etHq9lVoQjMx6y",
}

# Pasta de cache para o Streamlit Cloud (gravável)
_CACHE_DIR = os.environ.get("PARQUET_CACHE_DIR", "/tmp/fof_data")

# Tamanho de chunk para streaming (1 MB)
_CHUNK_SIZE = 1024 * 1024


def _ensure_cache_dir() -> None:
    os.makedirs(_CACHE_DIR, exist_ok=True)


def _local_path(base_name: str) -> str:
    """Caminho local do arquivo (em desenvolvimento)."""
    return os.path.join(BASE_DIR, f"{base_name}.parquet")


def _cache_path(base_name: str) -> str:
    """Caminho de cache no servidor (Streamlit Cloud)."""
    return os.path.join(_CACHE_DIR, f"{base_name}.parquet")


def _is_valid_parquet(path: str) -> bool:
    """
    Verifica se o arquivo é um parquet válido checando o magic number.
    Parquet começa e termina com os bytes b'PAR1'.
    """
    if not os.path.exists(path) or os.path.getsize(path) < 4:
        return False
    try:
        with open(path, "rb") as f:
            header = f.read(4)
        return header == b"PAR1"
    except OSError:
        return False


def _download_from_drive(base_name: str, dest_path: str) -> None:
    """
    Baixa o arquivo do Google Drive via HTTPS streaming com requests.

    Usa drive.usercontent.google.com com confirm=t, que bypassa
    automaticamente o aviso de confirmação para arquivos grandes (>40 MB),
    sem precisar de gdown ou cookies de sessão.
    """
    file_id = DRIVE_IDS.get(base_name)
    if not file_id:
        raise ValueError(f"ID do Drive não cadastrado para '{base_name}'.")

    # Esta URL bypassa o aviso de vírus do Google diretamente
    url = (
        "https://drive.usercontent.google.com/download"
        f"?id={file_id}&export=download&authuser=0&confirm=t"
    )

    _ensure_cache_dir()

    # Remove arquivo corrompido/incompleto de tentativas anteriores
    if os.path.exists(dest_path):
        os.remove(dest_path)

    logger.info("Baixando %s do Google Drive…", base_name)

    try:
        with requests.get(url, stream=True, timeout=600) as resp:
            resp.raise_for_status()
            with open(dest_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=_CHUNK_SIZE):
                    if chunk:
                        f.write(chunk)
    except requests.RequestException as exc:
        if os.path.exists(dest_path):
            os.remove(dest_path)
        raise RuntimeError(
            f"Falha ao baixar '{base_name}.parquet' do Google Drive: {exc}"
        ) from exc

    # Valida que o arquivo baixado é realmente um parquet
    if not _is_valid_parquet(dest_path):
        bad_size = os.path.getsize(dest_path) if os.path.exists(dest_path) else 0
        if os.path.exists(dest_path):
            os.remove(dest_path)
        raise RuntimeError(
            f"Download de '{base_name}.parquet' retornou arquivo inválido "
            f"({bad_size:,} bytes — esperado um parquet válido).\n"
            "Verifique se o arquivo está compartilhado como "
            "'Qualquer pessoa com o link pode visualizar'."
        )

    size_mb = os.path.getsize(dest_path) / 1_048_576
    logger.info("✓ %s baixado com sucesso (%.1f MB)", base_name, size_mb)


@st.cache_data(show_spinner=False)
def load_parquet(base_name: str) -> pd.DataFrame:
    """
    Carrega um arquivo parquet com fallback automático:
      1. Arquivo local (desenvolvimento)
      2. Cache em /tmp já validado (baixado anteriormente nesta instância)
      3. Download do Google Drive via HTTPS

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

    # 2️⃣ Cache do servidor — só usa se for um parquet válido
    cached = _cache_path(base_name)
    if _is_valid_parquet(cached):
        return pd.read_parquet(cached, engine="pyarrow")

    # 3️⃣ Download do Google Drive
    if base_name not in DRIVE_IDS:
        raise FileNotFoundError(
            f"Arquivo '{base_name}.parquet' não encontrado localmente "
            f"e não possui ID do Drive cadastrado."
        )

    _download_from_drive(base_name, cached)
    return pd.read_parquet(cached, engine="pyarrow")
