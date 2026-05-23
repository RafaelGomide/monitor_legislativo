import re
import openpyxl
import pandas as pd
from config import (
    COL_CASA, COL_LINK, COL_STATUS, COL_NUMERO,
    COLUNAS_OBRIGATORIAS, ABA_PRINCIPAL, LINHA_HEADER,
)

_URL_RE = re.compile(r'https?://\S+', re.IGNORECASE)


def extrair_primeiro_link(texto: str) -> str | None:
    """Retorna a primeira URL válida encontrada na célula, ou None."""
    if not texto or str(texto).strip() in ("", "_", "NÃO", "NAO"):
        return None
    matches = _URL_RE.findall(str(texto))
    if not matches:
        return None
    url = matches[0].split("#")[0].rstrip(".,;)")
    return url


def detectar_casa(link: str, casa_coluna: str) -> str:
    if link and "camara.leg.br" in link:
        return "camara"
    if link and "senado.leg.br" in link:
        return "senado"
    if link and "congressonacional.leg.br" in link:
        return "congresso"
    val = str(casa_coluna).upper()
    if "CÂMARA" in val or "CAMARA" in val:
        return "camara"
    if "SENADO" in val:
        return "senado"
    return "desconhecido"


def extrair_id_camara(link: str) -> str | None:
    match = re.search(r'idProposicao=(\d+)', link)
    return match.group(1) if match else None


def extrair_id_senado(link: str) -> str | None:
    match = re.search(r'/materia/(\d+)', link)
    return match.group(1) if match else None


def extrair_id_congresso(link: str) -> str | None:
    """
    Extrai o slug de uma URL do Congresso Nacional.
    Ex.: '.../ver/pl-5257-2025' → 'pl-5257-2025'
    O scraper congresso.py usa esse slug para pesquisar a matéria na API do Senado.
    """
    match = re.search(r'/ver/([\w-]+?)(?:\?|$)', link.rstrip('/'))
    return match.group(1) if match else None


def _encontrar_aba(arquivo) -> str:
    """Encontra o nome exato da aba principal (tolera espaços extras)."""
    if hasattr(arquivo, 'seek'):
        arquivo.seek(0)
    wb = openpyxl.load_workbook(arquivo, read_only=True)
    abas = wb.sheetnames
    wb.close()
    if hasattr(arquivo, 'seek'):
        arquivo.seek(0)
    match = next((a for a in abas if a.strip() == ABA_PRINCIPAL.strip()), None)
    return match or abas[0]


def ler_planilha(arquivo) -> tuple[pd.DataFrame, list[dict]]:
    """
    Lê a planilha do cliente e retorna:
      - df:  DataFrame limpo (apenas colunas nomeadas, sem Unnamed)
      - pls: lista de dicts com os PLs que têm link válido
    """
    aba = _encontrar_aba(arquivo)
    if hasattr(arquivo, 'seek'):
        arquivo.seek(0)

    df_raw = pd.read_excel(
        arquivo,
        sheet_name=aba,
        header=LINHA_HEADER - 1,
        dtype=str,
    )
    df_raw.fillna("", inplace=True)

    # Remove colunas Unnamed (artefato de células mescladas)
    df = df_raw.loc[:, ~df_raw.columns.str.startswith("Unnamed")]

    # Verifica colunas obrigatórias
    faltando = [c for c in COLUNAS_OBRIGATORIAS if c not in df.columns]
    if faltando:
        raise ValueError(
            f"Colunas não encontradas na planilha: {faltando}\n"
            f"Colunas disponíveis: {list(df.columns)}"
        )

    pls = []
    for idx, row in df.iterrows():
        link = extrair_primeiro_link(row.get(COL_LINK, ""))
        if not link:
            continue

        casa = detectar_casa(link, row.get(COL_CASA, ""))
        id_externo = (
            extrair_id_camara(link)     if casa == "camara"
            else extrair_id_senado(link)    if casa == "senado"
            else extrair_id_congresso(link) if casa == "congresso"
            else None
        )

        pls.append({
            "numero":       str(row.get(COL_NUMERO, "")).strip(),
            "casa":         casa,
            "link":         link,
            "id_externo":   id_externo,
            "status_salvo": str(row.get(COL_STATUS, "")).strip(),
            "linha_df":     idx,
        })

    return df, pls
