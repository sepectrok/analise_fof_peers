"""
Drive Loader — FoF Peers Dashboard
Baixa arquivos parquet do Google Drive.
Usa cache em disco (/tmp) com validação de ID para detectar quando o
mapeamento muda (evita servir arquivo de cache com ID desatualizado).
"""

import os
import tempfile
import logging
import requests
import pandas as pd
import streamlit as st

logger = logging.getLogger(__name__)

# ─── Mapeamento: nome do arquivo → ID do Google Drive ────────────────────────
DRIVE_IDS: dict[str, str] = {
    "blc_total_detail":      "1siKr21tYEo9GMVZtz-etHq9lVoQjMx6y",
    "blc_total_pivot":       "1rGXDq14VASFaAdqOILeAP4JxLpBbffaz",
    "check_pl":              "1LAnXXt2dHwAovjxXsNrR_fH56YJEmkhB",
    "cadastro_fof":          "1TIBeGxkUmU7FWadZlcKDV8R4kOxhD8Kg",
    "fundos_peers_carteira": "1huyqtuToBuYsOT2gYajmi5jSvvn-iy0Z",
}

# URLs a tentar, em ordem de preferência
def _drive_urls(file_id: str) -> list[str]:
    return [
        # URL moderna — bypassa confirmação de vírus diretamente
        f"https://drive.usercontent.google.com/download?id={file_id}&export=download&confirm=t",
        # URL clássica com confirmação explícita
        f"https://drive.google.com/uc?export=download&id={file_id}&confirm=t",
    ]

# Pasta de cache — usa tempfile para funcionar em Windows e Linux
_CACHE_DIR = os.environ.get(
    "PARQUET_CACHE_DIR",
    os.path.join(tempfile.gettempdir(), "fof_data"),
)
_CHUNK_SIZE = 1024 * 1024  # 1 MB por chunk
_TIMEOUT    = 600           # 10 minutos (arquivos grandes)
_MAX_TRIES  = 2


def _ensure_cache_dir() -> None:
    os.makedirs(_CACHE_DIR, exist_ok=True)


def _cache_path(base_name: str) -> str:
    return os.path.join(_CACHE_DIR, f"{base_name}.parquet")


def _meta_path(base_name: str) -> str:
    """Arquivo sidecar que guarda o Drive ID usado no download do cache."""
    return os.path.join(_CACHE_DIR, f"{base_name}.parquet.meta")


def _remove_if_exists(path: str) -> None:
    try:
        if os.path.exists(path):
            os.remove(path)
    except OSError:
        pass


def _is_valid_parquet(path: str) -> bool:
    """
    Verifica header E footer do arquivo.
    Parquet válido: primeiros 4 bytes = b'PAR1' e últimos 4 bytes = b'PAR1'.
    Detecta arquivos truncados, HTML ou qualquer conteúdo inválido.
    """
    if not os.path.exists(path):
        return False
    size = os.path.getsize(path)
    if size < 8:
        return False
    try:
        with open(path, "rb") as f:
            header = f.read(4)
            f.seek(-4, 2)
            footer = f.read(4)
        return header == b"PAR1" and footer == b"PAR1"
    except OSError:
        return False


def _cache_id_matches(base_name: str) -> bool:
    """
    Verifica se o arquivo em cache foi baixado com o ID atual do Drive.
    Retorna False se o ID mudou (cache desatualizado) ou se o .meta não existe.
    """
    meta = _meta_path(base_name)
    if not os.path.exists(meta):
        return False
    try:
        with open(meta, "r") as f:
            return f.read().strip() == DRIVE_IDS.get(base_name, "")
    except OSError:
        return False


def _save_cache_meta(base_name: str) -> None:
    """Salva o ID do Drive usado no download para validação futura."""
    try:
        with open(_meta_path(base_name), "w") as f:
            f.write(DRIVE_IDS[base_name])
    except OSError:
        pass


def _invalidate_cache(base_name: str) -> None:
    """Remove o parquet e o meta do cache."""
    _remove_if_exists(_cache_path(base_name))
    _remove_if_exists(_meta_path(base_name))


def _try_download_url(url: str, dest_path: str, label: str) -> bool:
    """
    Tenta baixar o arquivo de uma URL específica.
    Retorna True se baixou e validou com sucesso, False caso contrário.
    """
    _remove_if_exists(dest_path)
    try:
        with requests.get(url, stream=True, timeout=_TIMEOUT) as resp:
            # Detecta resposta HTML (página de erro/aviso do Google)
            content_type = resp.headers.get("Content-Type", "")
            if "text/html" in content_type:
                logger.warning(
                    "[%s] Google retornou HTML (content-type: %s). "
                    "Arquivo pode não estar compartilhado corretamente.",
                    label, content_type,
                )
                return False

            if not resp.ok:
                logger.warning("[%s] HTTP %s", label, resp.status_code)
                return False

            with open(dest_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=_CHUNK_SIZE):
                    if chunk:
                        f.write(chunk)

    except requests.RequestException as exc:
        logger.warning("[%s] Falha de rede: %s", label, exc)
        _remove_if_exists(dest_path)
        return False

    if not _is_valid_parquet(dest_path):
        size = os.path.getsize(dest_path) if os.path.exists(dest_path) else 0
        logger.warning(
            "[%s] Arquivo baixado não é parquet válido (%d bytes).", label, size
        )
        _remove_if_exists(dest_path)
        return False

    size_mb = os.path.getsize(dest_path) / 1_048_576
    logger.info("[%s] Download OK (%.1f MB)", label, size_mb)
    return True


def _download_from_drive(base_name: str, dest_path: str) -> None:
    """
    Baixa o arquivo do Google Drive com múltiplas URLs de fallback e retry.
    Lança RuntimeError se todas as tentativas falharem.
    """
    file_id = DRIVE_IDS.get(base_name)
    if not file_id:
        raise ValueError(f"ID do Drive não cadastrado para '{base_name}'.")

    urls = _drive_urls(file_id)
    _ensure_cache_dir()

    for attempt in range(1, _MAX_TRIES + 1):
        for url in urls:
            label = f"{base_name} · tentativa {attempt}"
            logger.info("[%s] Tentando URL: %s", label, url)
            if _try_download_url(url, dest_path, label):
                _save_cache_meta(base_name)  # registra ID usado
                return  # sucesso!

    # Todas as tentativas falharam
    raise RuntimeError(
        f"❌ Não foi possível baixar '{base_name}.parquet' do Google Drive "
        f"após {_MAX_TRIES} tentativas.\n\n"
        "Verifique:\n"
        "  • O arquivo está compartilhado como **'Qualquer pessoa com o link pode visualizar'**\n"
        f"  • O ID do Drive está correto: `{file_id}`\n"
        "  • O arquivo não foi movido ou excluído do Drive"
    )


@st.cache_data(show_spinner=False)
def load_parquet(base_name: str) -> pd.DataFrame:
    """
    Carrega um arquivo parquet do Google Drive.
    Usa cache em disco para evitar re-download, mas invalida automaticamente
    quando o ID do Drive muda no mapeamento DRIVE_IDS.

    Parameters
    ----------
    base_name : str
        Nome do arquivo sem extensão (ex: 'blc_total_detail').

    Returns
    -------
    pd.DataFrame
    """
    if base_name not in DRIVE_IDS:
        raise FileNotFoundError(
            f"Arquivo '{base_name}.parquet' não possui ID do Drive cadastrado."
        )

    cached = _cache_path(base_name)

    # Cache válido = parquet íntegro (PAR1 header+footer) E ID ainda é o mesmo
    if _is_valid_parquet(cached) and _cache_id_matches(base_name):
        try:
            df = pd.read_parquet(cached, engine="pyarrow")
            if len(df.columns) > 0:
                logger.info("[%s] Lido do cache (%d colunas, %d linhas)",
                            base_name, len(df.columns), len(df))
                return df
        except Exception as exc:
            logger.warning("[%s] Cache corrompido ao ler: %s. Re-baixando…", base_name, exc)

    # ID mudou ou cache inválido — limpa e re-baixa
    _invalidate_cache(base_name)
    _download_from_drive(base_name, cached)

    try:
        df = pd.read_parquet(cached, engine="pyarrow")
    except Exception as exc:
        _invalidate_cache(base_name)
        raise RuntimeError(
            f"[{base_name}] Parquet baixado mas inválido ao ler com pandas: {exc}"
        ) from exc

    logger.info("[%s] Download OK — %d colunas: %s",
                base_name, len(df.columns), list(df.columns))
    return df
