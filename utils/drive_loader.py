"""
Drive Loader — FoF Peers Dashboard
Baixa arquivos parquet do Google Drive quando não encontrados localmente.
Em desenvolvimento local, usa os arquivos locais diretamente.
No Streamlit Cloud, baixa para /tmp e cacheia em memória.

NOTA: Para arquivos >40 MB, o Google Drive exige confirmação de download
(aviso de vírus). O gdown precisa ser chamado com o ID direto para
contornar isso automaticamente.
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
    "blc_total_detail":      "1TIBeGxkUmU7FWadZlcKDV8R4kOxhD8Kg",
    "blc_total_pivot":       "1rGXDq14VASFaAdqOILeAP4JxLpBbffaz",
    "check_pl":              "1huyqtuToBuYsOT2gYajmi5jSvvn-iy0Z",
    "cadastro_fof":          "1LAnXXt2dHwAovjxXsNrR_fH56YJEmkhB",
    "fundos_peers_carteira": "1siKr21tYEo9GMVZtz-etHq9lVoQjMx6y",
}

# Tamanho mínimo em bytes para considerar o download válido (1 MB)
_MIN_VALID_SIZE = 1 * 1024 * 1024

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


def _is_valid_parquet(path: str) -> bool:
    """
    Verifica se o arquivo é um parquet válido checando o magic number.
    Parquet começa com os bytes b'PAR1' e termina com b'PAR1'.
    Evita aceitar páginas HTML do Google Drive como se fossem dados.
    """
    if not os.path.exists(path):
        return False
    if os.path.getsize(path) < _MIN_VALID_SIZE:
        return False
    try:
        with open(path, "rb") as f:
            header = f.read(4)
        return header == b"PAR1"
    except OSError:
        return False


def _download_from_drive(base_name: str, dest_path: str) -> None:
    """
    Baixa o arquivo do Google Drive via gdown.

    Usa o parâmetro `id=` diretamente (em vez de URL) para que o gdown
    consiga tratar automaticamente o aviso de confirmação do Google para
    arquivos grandes (>40 MB).
    """
    try:
        import gdown  # noqa: PLC0415
    except ImportError as exc:
        raise ImportError(
            "Pacote 'gdown' não encontrado. Adicione 'gdown' ao requirements.txt."
        ) from exc

    file_id = DRIVE_IDS.get(base_name)
    if not file_id:
        raise ValueError(f"ID do Drive não cadastrado para '{base_name}'.")

    _ensure_cache_dir()

    # Remove arquivo corrompido/incompleto antes de tentar de novo
    if os.path.exists(dest_path):
        os.remove(dest_path)

    logger.info("Baixando %s do Google Drive (id=%s)…", base_name, file_id)

    # Usar id= em vez de URL garante que o gdown lide com a confirmação
    # de arquivos grandes automaticamente (sem baixar a página de aviso HTML)
    gdown.download(
        id=file_id,
        output=dest_path,
        quiet=False,
        resume=False,
    )

    if not _is_valid_parquet(dest_path):
        # Remove o arquivo inválido (provavelmente HTML de aviso do Google)
        if os.path.exists(dest_path):
            bad_size = os.path.getsize(dest_path)
            os.remove(dest_path)
        else:
            bad_size = 0
        raise RuntimeError(
            f"Download de '{base_name}.parquet' falhou ou retornou arquivo inválido "
            f"({bad_size:,} bytes). Possíveis causas:\n"
            "  • Arquivo não compartilhado como 'Qualquer pessoa com o link'\n"
            "  • ID do Drive incorreto\n"
            "  • Falha temporária de rede"
        )


@st.cache_data(show_spinner=False)
def load_parquet(base_name: str) -> pd.DataFrame:
    """
    Carrega um arquivo parquet com fallback automático:
      1. Arquivo local (desenvolvimento)
      2. Cache em /tmp já validado (baixado anteriormente nesta instância)
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
