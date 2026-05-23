"""
Scraper da Câmara dos Deputados via API REST oficial.
Endpoint: dadosabertos.camara.leg.br/api/v2/proposicoes/{id}/tramitacoes

Retorno padrão de qualquer função pública:
{
    "ok":       bool,
    "data":     str,   # ex: "07/05/2026"
    "descricao": str,  # ex: "Recebimento pelo(a) CCJC"
    "situacao": str,   # ex: "Aguardando Designação de Relator"
    "orgao":    str,   # ex: "CCJC"
    "erro":     str | None
}
"""

import time
import requests
from config import CAMARA_API_BASE, REQUEST_TIMEOUT, REQUEST_DELAY

_HEADERS = {
    "User-Agent": "MonitorLegislativo/1.0 (contato@exemplo.com)",
    "Accept": "application/json",
}

_RESULTADO_VAZIO = {
    "ok": False,
    "data": "",
    "descricao": "",
    "situacao": "",
    "orgao": "",
    "erro": None,
}


def _formatar_data(data_hora: str) -> str:
    """Converte '2026-05-07T00:00:00' → '07/05/2026'."""
    if not data_hora:
        return ""
    try:
        parte = data_hora.split("T")[0]           # '2026-05-07'
        ano, mes, dia = parte.split("-")
        return f"{dia}/{mes}/{ano}"
    except Exception:
        return data_hora


def buscar_ultima_tramitacao(id_proposicao: str) -> dict:
    """
    Consulta a API da Câmara e retorna a tramitação mais recente do PL.

    Parâmetros
    ----------
    id_proposicao : str
        Número extraído da URL (ex: '2572690' de ?idProposicao=2572690)
    """
    result = _RESULTADO_VAZIO.copy()

    if not id_proposicao:
        result["erro"] = "id_proposicao não informado"
        return result

    url = f"{CAMARA_API_BASE}/proposicoes/{id_proposicao}/tramitacoes"

    try:
        time.sleep(REQUEST_DELAY)
        resp = requests.get(url, headers=_HEADERS, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()

        dados = resp.json().get("dados", [])
        if not dados:
            result["erro"] = "Nenhuma tramitação retornada pela API"
            return result

        # A API retorna em ordem crescente de sequência; o último é o mais recente
        ultima = dados[-1]

        result["ok"]       = True
        result["data"]     = _formatar_data(ultima.get("dataHora", ""))
        result["descricao"]= ultima.get("descricaoTramitacao", "").strip()
        result["situacao"] = ultima.get("descricaoSituacao", "").strip()
        result["orgao"]    = ultima.get("siglaOrgao", "").strip()
        result["erro"]     = None

    except requests.exceptions.Timeout:
        result["erro"] = f"Timeout ao acessar API da Câmara (id={id_proposicao})"
    except requests.exceptions.HTTPError as e:
        result["erro"] = f"HTTP {e.response.status_code} — {url}"
    except requests.exceptions.RequestException as e:
        result["erro"] = f"Erro de rede: {e}"
    except Exception as e:
        result["erro"] = f"Erro inesperado: {e}"

    return result
