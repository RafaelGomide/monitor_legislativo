"""
Motor de comparação — Fase 3.

Recebe os resultados do executor.py, compara com o estado.json
e classifica cada PL como COM ALTERAÇÃO, SEM ALTERAÇÃO ou PRIMEIRA VERIFICAÇÃO.

Retorna:
  df_resultado   → tabela resumida para exibição no app
  df_atualizado  → planilha original com STATUS MAIS RECENTE atualizado (para download)
  estado         → dict atualizado (o chamador salva em estado.json)
"""

import json
import datetime
import pandas as pd
from pathlib import Path
from config import (
    ESTADO_PATH,
    COL_SETOR, COL_CASA, COL_NUMERO, COL_EMENTA, COL_STATUS,
)

# ── Rótulos de resultado ──────────────────────────────────────────────────────
LABEL_ALTERADO    = "🔴 COM ALTERAÇÃO"
LABEL_SEM_ALTER   = "✅ SEM ALTERAÇÃO"
LABEL_PRIMEIRA    = "🆕 PRIMEIRA VERIFICAÇÃO"
LABEL_ERRO        = "❌ ERRO"

# Colunas do DataFrame de resultado
COLUNAS_RESULTADO = [
    "SETOR", "CASA", "Nº PL", "EMENTA",
    "ÚLTIMA TRAMITAÇÃO", "ÓRGÃO", "SITUAÇÃO ATUAL", "DESCRIÇÃO",
    "RESULTADO", "OBSERVAÇÃO",
]


# ── Estado ────────────────────────────────────────────────────────────────────

def carregar_estado(caminho: str = ESTADO_PATH) -> dict:
    path = Path(caminho)
    if path.exists():
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"_ultima_verificacao": None}


def salvar_estado(estado: dict, caminho: str = ESTADO_PATH) -> None:
    estado["_ultima_verificacao"] = _agora()
    path = Path(caminho)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(estado, f, ensure_ascii=False, indent=2)


def _agora() -> str:
    return datetime.datetime.now().strftime("%d/%m/%Y %H:%M")


# ── Comparação ────────────────────────────────────────────────────────────────

def _houve_mudanca(anterior: dict, atual: dict) -> bool:
    """
    Compara data + situação.
    Qualquer diferença (nova data OU nova situação) → COM ALTERAÇÃO.
    """
    return (
        str(anterior.get("data", "")).strip()     != str(atual.get("data", "")).strip()
        or
        str(anterior.get("situacao", "")).strip() != str(atual.get("situacao", "")).strip()
    )


def _status_formatado(tram: dict) -> str:
    """
    Formata a string do STATUS MAIS RECENTE para gravar na planilha.
    Ex.: '* 07/05/2026 - CCJC - AGUARDANDO DESIGNAÇÃO DO RELATOR'
    """
    partes = [p for p in [tram.get("data"), tram.get("orgao"), tram.get("situacao")] if p]
    return "* " + " - ".join(partes) if partes else ""


# ── Função principal ──────────────────────────────────────────────────────────

def comparar_e_atualizar(
    resultados: list[dict],
    df_original: pd.DataFrame,
    estado_path: str = ESTADO_PATH,
) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """
    Compara cada PL com o estado salvo e classifica.

    Parâmetros
    ----------
    resultados  : lista de dicts do executor (com campo 'tramitacao')
    df_original : DataFrame completo da planilha original
    estado_path : caminho do estado.json

    Retorno
    -------
    df_resultado  : tabela de resultados para exibição
    df_atualizado : planilha original com STATUS MAIS RECENTE atualizado
    estado        : dict atualizado (salvar com salvar_estado())
    """
    estado    = carregar_estado(estado_path)
    df_out    = df_original.copy()
    agora     = _agora()
    linhas    = []

    for r in resultados:
        chave = r["link"]          # URL como chave única
        tram  = r["tramitacao"]
        linha_df = r["linha_df"]

        # ── Dados da linha original ──────────────────────────────────────────
        row_orig = df_original.loc[linha_df] if linha_df in df_original.index else {}
        setor  = str(row_orig.get(COL_SETOR,  "")).strip()
        casa   = str(row_orig.get(COL_CASA,   "")).strip()
        numero = str(row_orig.get(COL_NUMERO, "")).strip() or r["numero"]
        ementa = str(row_orig.get(COL_EMENTA, "")).strip()[:80]

        # ── Caso de erro no scraper ──────────────────────────────────────────
        if not tram["ok"]:
            linhas.append({
                "SETOR": setor, "CASA": casa, "Nº PL": numero, "EMENTA": ementa,
                "ÚLTIMA TRAMITAÇÃO": "", "ÓRGÃO": "", "SITUAÇÃO ATUAL": "",
                "DESCRIÇÃO": "", "RESULTADO": LABEL_ERRO,
                "OBSERVAÇÃO": tram.get("erro", ""),
            })
            continue

        # ── Comparação com estado anterior ───────────────────────────────────
        anterior = estado.get(chave)

        if anterior is None:
            resultado = LABEL_PRIMEIRA
        elif _houve_mudanca(anterior, tram):
            resultado = LABEL_ALTERADO
        else:
            resultado = LABEL_SEM_ALTER

        # ── Atualiza estado.json ──────────────────────────────────────────────
        estado[chave] = {
            "numero":        numero,
            "data":          tram["data"],
            "situacao":      tram["situacao"],
            "orgao":         tram["orgao"],
            "descricao":     tram["descricao"],
            "verificado_em": agora,
        }

        # ── Atualiza STATUS MAIS RECENTE na planilha ─────────────────────────
        if linha_df in df_out.index and COL_STATUS in df_out.columns:
            df_out.at[linha_df, COL_STATUS] = _status_formatado(tram)

        # ── Linha do resultado ────────────────────────────────────────────────
        linhas.append({
            "SETOR":              setor,
            "CASA":               casa,
            "Nº PL":              numero,
            "EMENTA":             ementa,
            "ÚLTIMA TRAMITAÇÃO":  tram["data"],
            "ÓRGÃO":              tram["orgao"],
            "SITUAÇÃO ATUAL":     tram["situacao"],
            "DESCRIÇÃO":          tram["descricao"],
            "RESULTADO":          resultado,
            "OBSERVAÇÃO":         "",
        })

    estado["_ultima_verificacao"] = agora

    df_resultado = pd.DataFrame(linhas, columns=COLUNAS_RESULTADO)
    return df_resultado, df_out, estado
