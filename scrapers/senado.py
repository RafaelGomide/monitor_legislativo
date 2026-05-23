"""
Scraper do Senado Federal via API REST oficial.

Dois endpoints:
  /materia/movimentacoes/{id}  →  tramitação (Movimentacoes OU InformesLegislativos)
  /materia/{id}                →  situação atual (fallback garantido)

Retorno padrão:
  { ok, data, descricao, situacao, orgao, erro }
"""

import time
import requests
from config import REQUEST_TIMEOUT, REQUEST_DELAY

_BASE    = "https://legis.senado.leg.br/dadosabertos"
_HEADERS = {"User-Agent": "MonitorLegislativo/1.0", "Accept": "application/json"}

_VAZIO = {"ok": False, "data": "", "descricao": "", "situacao": "", "orgao": "", "erro": None}


# ── Utilidades ────────────────────────────────────────────────────────────────

def _fmt_data(raw: str) -> str:
    """Qualquer formato com 8 dígitos → DD/MM/YYYY."""
    if not raw:
        return ""
    try:
        d = "".join(c for c in str(raw) if c.isdigit())[:8]
        return f"{d[6:8]}/{d[4:6]}/{d[0:4]}"
    except Exception:
        return str(raw)


def _to_list(obj) -> list:
    if isinstance(obj, list): return obj
    if obj is not None:       return [obj]
    return []


def _get(url: str):
    try:
        time.sleep(REQUEST_DELAY)
        r = requests.get(url, headers=_HEADERS, timeout=REQUEST_TIMEOUT)
        r.raise_for_status()
        return r.json()
    except Exception:
        return None


def _sigla_local(obj) -> str:
    """Extrai sigla de um objeto Local ou Colegiado."""
    if not isinstance(obj, dict):
        return ""
    return (obj.get("SiglaLocal") or obj.get("SiglaColegiado")
            or obj.get("SiglaOrgao") or "")


# ── Parser principal ──────────────────────────────────────────────────────────

def _extrair_de_movimentacoes(json_data: dict) -> dict:
    """
    Cobre dois layouts da API:

    Layout ANTIGO  →  Autuacao → Movimentacoes → Movimentacao[]
                       campos: DataMovimentacao, DescricaoMovimentacao, Local/Orgao

    Layout NOVO    →  Autuacao → InformesLegislativos → InformeLegislativo[]
    (2024+)            campos: Data, Descricao, Local, Colegiado
                   +  Autuacao → SituacoesAtuais → SituacaoAtual[]
                       campos: DataSituacao, DescricaoSituacao
    """
    materia    = json_data.get("MovimentacaoMateria", {}).get("Materia", {})
    autuacoes  = _to_list((materia.get("Autuacoes") or {}).get("Autuacao"))

    data      = ""
    descricao = ""
    situacao  = ""
    orgao     = ""

    for aut in autuacoes:

        # ── Situação atual (funciona para PLs novos e antigos) ──────────────
        sits = _to_list((aut.get("SituacoesAtuais") or {}).get("SituacaoAtual"))
        if sits:
            sits.sort(key=lambda s: s.get("DataSituacao", ""))
            melhor = sits[-1]
            situacao = situacao or melhor.get("DescricaoSituacao", "")
            data     = data     or _fmt_data(melhor.get("DataSituacao", ""))

        # ── Layout NOVO: InformesLegislativos ───────────────────────────────
        informes = _to_list((aut.get("InformesLegislativos") or {}).get("InformeLegislativo"))
        if informes:
            informes.sort(key=lambda i: i.get("Data", ""))
            ultimo    = informes[-1]
            descricao = descricao or str(ultimo.get("Descricao", "")).strip()
            data      = data      or _fmt_data(ultimo.get("Data", ""))
            orgao     = orgao     or _sigla_local(ultimo.get("Local") or ultimo.get("Colegiado") or {})

        # ── Layout ANTIGO: Movimentacoes ────────────────────────────────────
        movs = _to_list((aut.get("Movimentacoes") or {}).get("Movimentacao"))
        if movs:
            movs.sort(key=lambda m: m.get("DataMovimentacao", ""))
            ultimo    = movs[-1]
            descricao = descricao or str(ultimo.get("DescricaoMovimentacao", "")).strip()
            data      = data      or _fmt_data(ultimo.get("DataMovimentacao", ""))
            local_obj = ultimo.get("Local") or ultimo.get("Orgao") or {}
            if isinstance(local_obj, str):
                local_obj = {"SiglaLocal": local_obj}
            orgao = orgao or _sigla_local(local_obj)

    # Caminho alternativo: Movimentacoes direto em Materia (algumas respostas antigas)
    if not descricao:
        movs = _to_list((materia.get("Movimentacoes") or {}).get("Movimentacao"))
        if movs:
            movs.sort(key=lambda m: m.get("DataMovimentacao", ""))
            u         = movs[-1]
            descricao = str(u.get("DescricaoMovimentacao", "")).strip()
            data      = data  or _fmt_data(u.get("DataMovimentacao", ""))

    return {"data": data, "descricao": descricao, "situacao": situacao, "orgao": orgao}


def _extrair_de_detalhe(json_data: dict) -> dict:
    """Extrai SituacaoAtual do endpoint /materia/{id} — sempre preenchida."""
    sit = (json_data.get("DetalheMateria", {})
                    .get("Materia", {})
                    .get("SituacaoAtual") or {})
    return {
        "situacao": sit.get("DescricaoSituacao", ""),
        "orgao":    _sigla_local(sit.get("Local") or sit.get("Orgao") or {}),
        "data":     _fmt_data(sit.get("DataSituacao", "")),
    }


# ── Função pública ────────────────────────────────────────────────────────────

def buscar_ultima_tramitacao(id_materia: str) -> dict:
    result = _VAZIO.copy()

    if not id_materia:
        result["erro"] = "id_materia não informado"
        return result

    try:
        mov_json = _get(f"{_BASE}/materia/movimentacoes/{id_materia}")
        det_json = _get(f"{_BASE}/materia/{id_materia}")

        if not mov_json and not det_json:
            result["erro"] = "Sem resposta dos dois endpoints"
            return result

        mov = _extrair_de_movimentacoes(mov_json) if mov_json else {}
        det = _extrair_de_detalhe(det_json)       if det_json else {}

        result["ok"]        = True
        result["data"]      = mov.get("data")      or det.get("data")      or ""
        result["orgao"]     = mov.get("orgao")      or det.get("orgao")     or ""
        result["descricao"] = mov.get("descricao")  or ""
        # Situação: /materia/{id} é mais confiável para PLs novos
        result["situacao"]  = det.get("situacao")  or mov.get("situacao")   or ""
        result["erro"]      = None

    except Exception as e:
        result["erro"] = f"Erro inesperado: {e}"

    return result
