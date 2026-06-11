"""
gerador_de_base.py — Solis Investimentos
Gera os CSVs de base para o dashboard de Peers FoF.

CORREÇÃO CONCEITUAL:
  Os dados ANBIMA são do FUNDO ANALISADO (o FoF investidor),
  não dos fundos por ele geridos/investidos.
  O join por CPF_CNPJ_Emissor continua para enriquecer a carteira
  com informações dos fundos INVESTIDOS (para classificar o tipo de ativo).
"""

import pandas as pd
import pyodbc
import re
import os
import pyarrow

# ─────────────────────────────────────────
# CONFIGURAÇÃO
# ─────────────────────────────────────────
quem_esta_usando = os.getlogin()
credenciais = pd.read_csv(
    fr"C:\Users\{quem_esta_usando}\Documents\acesso_banco.txt", header=None
)
server   = '10.175.84.61'
database = 'Solis'
username = re.search(r'username:\s*(.*)', credenciais.iloc[0, 0]).group(1)
password = re.search(r'password:\s*(.*)', credenciais.iloc[1, 0]).group(1)

connection_string = (
    'DRIVER={ODBC Driver 17 for SQL Server};'
    f'SERVER={server};DATABASE={database};UID={username};PWD={password}'
)

# Filtra apenas dados a partir desta data (deixe None para tudo)
DATA_INICIO = pd.to_datetime('2026-01-01')


def conectar():
    return pyodbc.connect(connection_string)


def ler_tabela(query: str) -> pd.DataFrame:
    with conectar() as conn:
        return pd.read_sql(query, conn)


# ─────────────────────────────────────────
# 1. LEITURA DAS TABELAS BRUTAS
# ─────────────────────────────────────────
print("Lendo tabelas CVM BLC...")
print("BLC1")
df_blc1 = ler_tabela(f"SELECT * FROM BdTeste.CVM.CDA_BLC1 WHERE Data_Posicao >= '{DATA_INICIO}'")
print("BLC2")
df_blc2 = ler_tabela(f"SELECT * FROM BdTeste.CVM.CDA_BLC2 WHERE Data_Posicao >= '{DATA_INICIO}'")
print("BLC3")
df_blc3 = ler_tabela(f"SELECT * FROM BdTeste.CVM.CDA_BLC3 WHERE Data_Posicao >= '{DATA_INICIO}'")
print("BLC4")
df_blc4 = ler_tabela(f"SELECT * FROM BdTeste.CVM.CDA_BLC4 WHERE Data_Posicao >= '{DATA_INICIO}'")
print("BLC5")
df_blc5 = ler_tabela(f"SELECT * FROM BdTeste.CVM.CDA_BLC5 WHERE Data_Posicao >= '{DATA_INICIO}'")
print("BLC6")
df_blc6 = ler_tabela(f"SELECT * FROM BdTeste.CVM.CDA_BLC6 WHERE Data_Posicao >= '{DATA_INICIO}'")
print("BLC7")
df_blc7 = ler_tabela(f"SELECT * FROM BdTeste.CVM.CDA_BLC7 WHERE Data_Posicao >= '{DATA_INICIO}'")
print("BLC8")
df_blc8 = ler_tabela(f"SELECT * FROM BdTeste.CVM.CDA_BLC8 WHERE Data_Posicao >= '{DATA_INICIO}'")
print("CONFID")
df_blc9 = ler_tabela(f"SELECT * FROM BdTeste.CVM.CDA_CONFID WHERE Data_Posicao >= '{DATA_INICIO}'")

# BLC9 (CONFID) usa Valor_Mercado como valor monetário
if 'Valor_Mercado' in df_blc9.columns and 'Valor_Presente' not in df_blc9.columns:
    df_blc9['Valor_Presente'] = df_blc9['Valor_Mercado']
elif 'Valor_Mercado' in df_blc9.columns:
    df_blc9['Valor_Presente'] = df_blc9['Valor_Mercado']

print("Lendo tabela PL e cadastros ANBIMA...")
df_pl               = ler_tabela("SELECT * FROM BdTeste.CVM.CDA_PL")
df_anbima_fundo     = ler_tabela("SELECT * FROM BdTeste.Anbima.Detalhe_Fundo_Classe")
df_anbima_subclasse = ler_tabela("SELECT * FROM BdTeste.Anbima.Detalhe_Subclasse")


# ─────────────────────────────────────────
# 2. CONSOLIDAÇÃO BLC TOTAL (plano de contas)
# ─────────────────────────────────────────
print("Consolidando BLC total...")

COLUNAS_BLC = [
    'Tipo_Fundo', 'ID_CNPJ_Fundo', 'Nome_Fundo_CVM', 'Data_Posicao',
    'Tipo_Composicao', 'Detalhe_Composicao', 'Descricao_Ativo',
    'Quantidade_Posicao', 'Valor_Presente',
    'Tipo_Negociacao', 'Codigo_Selic', 'Data_Vencimento',
    'ID_CNPJ_Fundo_Investido', 'Nome_Fundo_Classe_Investida',
    'ID_CNPJ_Emissor', 'Nome_Emissor', 'PF_PF_Emissor', 'CPF_CNPJ_Emissor',
]

blc_frames = [df_blc1,df_blc2, df_blc3, df_blc4,
              df_blc5, df_blc6, df_blc7, df_blc8,
              df_blc9]

blc_padded = []
for df in blc_frames:
    for col in COLUNAS_BLC:
        if col not in df.columns:
            df[col] = pd.NA
    blc_padded.append(df[COLUNAS_BLC].copy())

df_blc_raw = pd.concat(blc_padded, ignore_index=True)

# Conversões numéricas
df_blc_raw['Quantidade_Posicao'] = pd.to_numeric(df_blc_raw['Quantidade_Posicao'], errors='coerce')
df_blc_raw['Valor_Presente']     = pd.to_numeric(df_blc_raw['Valor_Presente'],     errors='coerce')
df_blc_raw['Data_Posicao']       = pd.to_datetime(df_blc_raw['Data_Posicao'],      errors='coerce')

# Filtro por data
if DATA_INICIO is not None:
    df_blc_raw = df_blc_raw[df_blc_raw['Data_Posicao'] >= DATA_INICIO]

# PL = Valor_Presente com sinal invertido para "VALORES A PAGAR"
mask_pagar = df_blc_raw['Tipo_Composicao'] == "VALORES A PAGAR"
df_blc_raw['PL'] = df_blc_raw['Valor_Presente'].copy()
df_blc_raw.loc[mask_pagar, 'PL'] = -df_blc_raw.loc[mask_pagar, 'Valor_Presente']

# PU Teórico
def _calc_pu(row):
    qtd = row['Quantidade_Posicao']
    denom = 1 if (pd.isna(qtd) or qtd == 0) else qtd
    try:
        return round(row['Valor_Presente'] / denom, 4)
    except Exception:
        return pd.NA

df_blc_raw['PU_Teorico'] = df_blc_raw.apply(_calc_pu, axis=1)

# Corrige Nome_Emissor / CPF_CNPJ_Emissor para cotas de fundos e títulos públicos
mask_cotas  = df_blc_raw['Tipo_Composicao'] == "COTAS DE FUNDOS"
mask_titpub = df_blc_raw['Tipo_Composicao'].isin(
    ["TÍTULOS PÚBLICOS", "T?TULOS P?BLICOS", "TITULOS PUBLICOS"]
)
df_blc_raw.loc[mask_cotas, 'Nome_Emissor']    = df_blc_raw.loc[mask_cotas, 'Nome_Fundo_Classe_Investida']
df_blc_raw.loc[mask_titpub, 'Nome_Emissor']   = df_blc_raw.loc[mask_titpub, 'Tipo_Composicao']
df_blc_raw.loc[mask_cotas, 'PF_PF_Emissor']  = "PJ"
df_blc_raw.loc[mask_cotas, 'CPF_CNPJ_Emissor'] = df_blc_raw.loc[mask_cotas, 'ID_CNPJ_Fundo_Investido']

df_blc_total = df_blc_raw[[
    'Tipo_Fundo', 'ID_CNPJ_Fundo', 'Nome_Fundo_CVM', 'Data_Posicao',
    'Tipo_Composicao', 'Detalhe_Composicao', 'Valor_Presente',
    'Descricao_Ativo', 'Quantidade_Posicao', 'PL', 'PU_Teorico',
    'Tipo_Negociacao', 'Codigo_Selic', 'Data_Vencimento',
    'ID_CNPJ_Fundo_Investido', 'Nome_Fundo_Classe_Investida',
    'ID_CNPJ_Emissor', 'Nome_Emissor', 'PF_PF_Emissor', 'CPF_CNPJ_Emissor',
]].copy()


# ─────────────────────────────────────────
# 3. PATRIMÔNIO LÍQUIDO
# ─────────────────────────────────────────
df_pl['Data_Posicao']       = pd.to_datetime(df_pl['Data_Posicao'], errors='coerce')
df_pl['Patrimonio_Liquido'] = pd.to_numeric(df_pl['Patrimonio_Liquido'], errors='coerce')

if DATA_INICIO is not None:
    df_pl = df_pl[df_pl['Data_Posicao'] >= DATA_INICIO]

df_pl_tratado = df_pl[[
    'Tipo_Fundo', 'ID_CNPJ_Fundo', 'Nome_Fundo_CVM', 'Data_Posicao', 'Patrimonio_Liquido'
]].rename(columns={'Patrimonio_Liquido': 'PL_Est_Cap'}).copy()


# ─────────────────────────────────────────
# 4. CHECK PL: Plano de Contas vs PL Estimado
# ─────────────────────────────────────────
print("Calculando check de PL...")

plano_conta_cvm = (
    df_blc_total
    .groupby(['Tipo_Fundo', 'ID_CNPJ_Fundo', 'Nome_Fundo_CVM', 'Data_Posicao'], as_index=False)
    .agg(PL_Contas=('PL', 'sum'))
)

check_pl = (
    df_pl_tratado
    .merge(plano_conta_cvm,
           on=['Tipo_Fundo', 'ID_CNPJ_Fundo', 'Nome_Fundo_CVM', 'Data_Posicao'],
           how='left')
)
check_pl['Check_PL'] = (check_pl['PL_Est_Cap'] - check_pl['PL_Contas']).round(2)
check_pl['Status_Check_PL'] = check_pl.apply(
    lambda x: "NOK" if (pd.notna(x['PL_Est_Cap']) and x['PL_Est_Cap'] != 0
                        and abs(x['Check_PL']) >= x['PL_Est_Cap'] * 0.05)
              else "OK",
    axis=1
)

print("Tratando cadastro ANBIMA dos fundos investidos (para classificar ativos)...")

MAPA_INVESTIDO = {
    'ID_CNPJ_Fundo'              : 'CPF_CNPJ_Emissor',  # chave de join com a carteira
    'Nome_Comercial'             : 'Nome_Comercial_Investido',
    'Tipo_Fundo'                 : 'Tipo_Fundo_Investido',
    'Gestor_Nome_Comercial'      : 'Gestor_Investido',
    'Administrador_Nome_Comercial': 'Administrador_Investido',
    'Alavancado'                 : 'Alavancado_Investido',
    'Foco_Atuacao'               : 'Foco_Atuacao_Investido',
    'Categoria_Cvm'              : 'Categoria_Cvm_Investido',
    'Composicao'                 : 'Composicao_Investido',
    'Tipo_Anbima'                : 'Tipo_Anbima_Investido',
    'Nivel1_Categoria'           : 'Categoria_1_Investido',
    'Nivel2_Categoria'           : 'Categoria_2_Investido',
    'Nivel3_Subcategoria'        : 'Sub_Categoria_Investido',
    'Forma_Condominio'           : 'Forma_Condominio_Investido',
}
cols_investido = {k: v for k, v in MAPA_INVESTIDO.items() if k in df_anbima_fundo.columns}
dados_fundos_investidos = (
    df_anbima_fundo[list(cols_investido.keys())]
    .rename(columns=cols_investido)
    .drop_duplicates(subset=['CPF_CNPJ_Emissor'])
    .copy()
)


# ─────────────────────────────────────────
# 6. CADASTRO ANBIMA DO FUNDO ANALISADO
#    (atributos do próprio FoF — Tipo_Investidor, gestor, prazo, etc.)
# ─────────────────────────────────────────
print("Tratando cadastro ANBIMA do fundo analisado (FoF investidor)...")

MAPA_ANALISADO = {
    'ID_CNPJ_Fundo'              : 'ID_CNPJ_Fundo',       # chave de join
    'Nome_Comercial'             : 'Nome_Comercial',
    'Tipo_Fundo'                 : 'Tipo_Fundo',
    'Gestor_Identificador'       : 'ID_CNPJ_Gestor',
    'Gestor_Nome_Comercial'      : 'Gestor',
    'Administrador_Identificador': 'ID_CNPJ_Administrador',
    'Administrador_Nome_Comercial': 'Administrador',
    'Alavancado'                 : 'Alavancado',
    'Foco_Atuacao'               : 'Foco_Atuacao',
    'Categoria_Cvm'              : 'Categoria_Cvm',
    'Composicao'                 : 'Composicao',
    'Tipo_Anbima'                : 'Tipo_Anbima',
    'Nivel1_Categoria'           : 'Categoria_1',
    'Nivel2_Categoria'           : 'Categoria_2',
    'Nivel3_Subcategoria'        : 'Sub_Categoria',
    'Forma_Condominio'           : 'Forma_Condominio',
    'Data_Inicio_Atividade_Classe': 'Data_Inicio_Atividade',
    'Data_Encerramento_Classe'   : 'Data_Encerramento',
    'Credito_Privado'            : 'Credito_Privado',
    'Responsabilidade_Limitada'  : 'Responsabilidade_Limitada',
}
cols_analisado = {k: v for k, v in MAPA_ANALISADO.items() if k in df_anbima_fundo.columns}
dados_fundo_analisado = (
    df_anbima_fundo[list(cols_analisado.keys())]
    .rename(columns=cols_analisado)
    .drop_duplicates(subset=['ID_CNPJ_Fundo'])
    .copy()
)

# Dados de subclasse (Tipo_Investidor, prazos, periodicidade)
MAPA_SUBCLASSE = {
    'ID_CNPJ_Fundo'                    : 'ID_CNPJ_Fundo',
    'Tipo_Investidor'                  : 'Tipo_Investidor',
    'Codigo_Classe'                    : 'Codigo_Classe',
    'Nome_Comercial'                   : 'Nome_Comercial_Subclasse',
    'Periodicidade_envio_cota'         : 'Periodicidade_envio_cota',
    'Indicador_prazo_conversao_resgate': 'Tipo_conversao',
    'Prazo_conversao_resgate'          : 'Prazo_conversao',
    'Indicador_prazo_pagamento_resgate': 'Tipo_resgate',
    'Prazo_pagamento_resgate'          : 'Prazo_resgate',
}
cols_sub = {k: v for k, v in MAPA_SUBCLASSE.items() if k in df_anbima_subclasse.columns}
dados_subclasse = (
    df_anbima_subclasse[list(cols_sub.keys())]
    .rename(columns=cols_sub)
    .copy()
)

# Merge fundo analisado + subclasse
dados_cadastro_fof = dados_fundo_analisado.merge(
    dados_subclasse, on='ID_CNPJ_Fundo', how='left'
)

# Prazos ausentes na ANBIMA: converte NA para rótulo explícito.
# Esses fundos NÃO devem ser usados como critério de filtragem de peers.
for _col_prazo in ('Prazo_conversao', 'Prazo_resgate'):
    if _col_prazo in dados_cadastro_fof.columns:
        dados_cadastro_fof[_col_prazo] = (
            dados_cadastro_fof[_col_prazo]
            .astype(object)
            .where(dados_cadastro_fof[_col_prazo].notna(), other='Sem Informação Anbima')
        )


# ─────────────────────────────────────────
# 7. BLC TOTAL DETALHADO
#    Join com classificação dos ativos investidos
# ─────────────────────────────────────────
print("Gerando blc_total_detail...")

blc_total_detail = df_blc_total.merge(
    dados_fundos_investidos,
    on='CPF_CNPJ_Emissor',
    how='left'
)

# Tipo de composição ajustado: "COTA DE FIDC", "COTA DE FIM", etc.
blc_total_detail['Tipo_Composicao_Ajustado'] = blc_total_detail.apply(
    lambda x: (
        "COTA DE " + (
            "SEM CADASTRO"
            if pd.isna(x.get('Tipo_Fundo_Investido'))
            else str(x['Tipo_Fundo_Investido']).strip().upper()
        )
    ) if x['Tipo_Composicao'] == "COTAS DE FUNDOS"
    else x['Tipo_Composicao'],
    axis=1
)


# ─────────────────────────────────────────
# 8. PIVOT POR COMPOSIÇÃO + ATRIBUTOS DO FoF
# ─────────────────────────────────────────
print("Gerando pivot por composição (com atributos do fundo analisado)...")

grupo_col = 'Tipo_Composicao_Ajustado'

blc_pivot = (
    blc_total_detail
    .groupby(['ID_CNPJ_Fundo', 'Nome_Fundo_CVM', 'Data_Posicao', grupo_col], as_index=False)
    .agg(
        PL_Conta=('PL', 'sum'),
        Qtd_Linhas=('PL', 'count')
    )
)

# % dentro de cada fundo × mês
pl_por_fundo_mes = (
    blc_pivot
    .groupby(['ID_CNPJ_Fundo', 'Nome_Fundo_CVM', 'Data_Posicao'], as_index=False)
    ['PL_Conta'].sum()
    .rename(columns={'PL_Conta': 'PL_Total_Fundo'})
)
blc_pivot = blc_pivot.merge(pl_por_fundo_mes, on=['ID_CNPJ_Fundo', 'Nome_Fundo_CVM', 'Data_Posicao'], how='left')
blc_pivot['Percentual'] = (blc_pivot['PL_Conta'] / blc_pivot['PL_Total_Fundo']).round(4)
blc_pivot = blc_pivot.drop(columns=['PL_Total_Fundo'])

# Join com PL estimado e status check
pl_ref = check_pl[['ID_CNPJ_Fundo', 'Nome_Fundo_CVM', 'Data_Posicao', 'PL_Est_Cap', 'Status_Check_PL']].copy()
blc_pivot = blc_pivot.merge(pl_ref, on=['ID_CNPJ_Fundo', 'Nome_Fundo_CVM', 'Data_Posicao'], how='left')
blc_pivot['Percentual_Conta_PL_Est_Cap'] = (blc_pivot['PL_Conta'] / blc_pivot['PL_Est_Cap']).round(4)

# JOIN com cadastro ANBIMA do FUNDO ANALISADO (o FoF)
blc_pivot = blc_pivot.merge(
    dados_cadastro_fof,
    on='ID_CNPJ_Fundo',
    how='left'
)


# ─────────────────────────────────────────
# 9. SELEÇÃO DE PEERS (≥30% em FIDC por padrão)
# ─────────────────────────────────────────
print("Selecionando peers de FIDC...")

PCT_MIN_FIDC = 0.3

# % total em FIDC por fundo×mês
pct_fidc = (
    blc_pivot[blc_pivot[grupo_col].str.contains("FIDC", na=False)]
    .groupby(['ID_CNPJ_Fundo', 'Nome_Fundo_CVM', 'Data_Posicao'], as_index=False)
    ['Percentual'].sum()
    .rename(columns={'Percentual': 'Pct_FIDC_Total'})
)

cnpjs_peers = pct_fidc.loc[
    pct_fidc['Pct_FIDC_Total'] >= PCT_MIN_FIDC, 'ID_CNPJ_Fundo'
].unique()

print(f"  → {len(cnpjs_peers)} fundos selecionados como peers de FIDC")

# Tabela de peers com todos os atributos do FoF
fundos_peers_carteira = (
    blc_pivot[
        blc_pivot['ID_CNPJ_Fundo'].isin(cnpjs_peers) &
        (blc_pivot['PL_Est_Cap'].fillna(0) > 0) &
        blc_pivot[grupo_col].str.contains("FIDC", na=False)
    ]
    .merge(pct_fidc, on=['ID_CNPJ_Fundo', 'Nome_Fundo_CVM', 'Data_Posicao'], how='left')
    .drop_duplicates(subset=['ID_CNPJ_Fundo', 'Data_Posicao'])
)


# ─────────────────────────────────────────
# 10. EXPORTAÇÃO — CSV + PARQUET
# Os arquivos .parquet são lidos pelo Streamlit (5-10x mais rápido que CSV).
# Os .csv são mantidos como fallback/retrocompatibilidade.
# ─────────────────────────────────────────
OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__))

# ── Tabelas a exportar ──────────────────────────────────────────────────────
# (nome_base, dataframe, colunas_de_data_para_normalizar)
EXPORTS = [
    ("blc_total_detail",     blc_total_detail,     ["Data_Posicao", "Data_Vencimento"]),
    ("blc_total_pivot",      blc_pivot,             ["Data_Posicao"]),
    ("fundos_peers_carteira",fundos_peers_carteira, ["Data_Posicao"]),
    ("check_pl",             check_pl,              ["Data_Posicao"]),
    ("cadastro_fof",         dados_cadastro_fof,    []),
]


def _normalizar_datas(df: pd.DataFrame, cols: list) -> pd.DataFrame:
    """Garante que colunas de data sejam datetime64[ns] sem timezone (Parquet exige)."""
    df = df.copy()
    for col in cols:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce").dt.tz_localize(None)
    return df


print("\nExportando Parquets...")

for nome, df_exp, cols_data in EXPORTS:
    # Parquet (leitura pelo Streamlit)
    parquet_path = os.path.join(OUTPUT_DIR, f"{nome}.parquet")
    df_parquet = _normalizar_datas(df_exp, cols_data)
    df_parquet.to_parquet(parquet_path, index=False, compression="snappy", engine="pyarrow")
    size_mb = os.path.getsize(parquet_path) / 1_048_576
    print(f"  Parquet : {nome}.parquet  ({size_mb:.1f} MB)")

print("\n Base gerada com sucesso!")
print(f"   Linhas blc_total  : {len(df_blc_total):,}")
print(f"   Fundos no pivot   : {blc_pivot['ID_CNPJ_Fundo'].nunique():,}")
print(f"   Peers FIDC (>=30%): {len(cnpjs_peers):,}")