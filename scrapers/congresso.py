"""
Scraper para matérias bicamerais do Congresso Nacional.
URL: congressonacional.leg.br/materias/materias-bicamerais/-/ver/pl-5257-2025

Usa BeautifulSoup para extrair:
  - Situação  →  div.cn-mb-fase--quadro--ativa  →  <p> "situação: ..." → <span>
  - Tramitação →  div.accordion  →  texto "DD/MM/YYYY SIGLA - Orgao ação: Desc"

Retorno padrão:
  { ok, data, descricao, situacao, orgao, erro }
"""

import re
import time
import requests
from bs4 import BeautifulSoup
from config import REQUEST_TIMEOUT, REQUEST_DELAY

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    ),
    "Accept-Language": "pt-BR,pt;q=0.9",
    "Accept": "text/html,application/xhtml+xml",
}

_VAZIO = {"ok": False, "data": "", "descricao": "", "situacao": "", "orgao": "", "erro": None}

# Regex para datas no formato DD/MM/AAAA dentro do texto do accordion
_DATE_RE = re.compile(r'\b(\d{2}/\d{2}/\d{4})\b')


# ── Parser BeautifulSoup ──────────────────────────────────────────────────────

def _extrair_situacao(soup: BeautifulSoup) -> str:
    """
    Extrai a situação atual do quadro ativo.
    Procura dentro de div.cn-mb-fase--quadro--ativa por um <p> com 'situação:'
    e retorna o texto do <span> interno ou o texto após o ':'.
    """
    quadro = soup.find("div", class_="cn-mb-fase--quadro--ativa")
    if not quadro:
        # Fallback: procura qualquer elemento com a classe de situação
        el = soup.find("div", class_="cn-mb-fase--descricao-situacao")
        return el.get_text(strip=True) if el else ""

    for p in quadro.find_all("p"):
        txt = p.get_text(" ", strip=True).lower()
        if "situação:" in txt or "situacao:" in txt:
            span = p.find("span")
            if span:
                return span.get_text(strip=True)
            # Sem span: pega o texto depois dos ':'
            return p.get_text(strip=True).split(":")[-1].strip()

    return ""


def _extrair_tramitacao(soup: BeautifulSoup) -> dict:
    """
    Extrai a tramitação mais recente do accordion.
    Formato do texto do accordion:
        'tramitação 16/10/2025 sf-slsf - Secretaria Legislativa ... ação: Autuado ...'

    Retorna dict com data, orgao, descricao.
    """
    vazio = {"data": "", "orgao": "", "descricao": ""}

    # Pega o div do accordion que contém o histórico de tramitação
    accordion = soup.find("div", class_="accordion-group")
    if not accordion:
        accordion = soup.find("div", class_="accordion")
    if not accordion:
        return vazio

    texto = accordion.get_text(" ", strip=True)

    # Divide o texto pelas datas para isolar cada entrada de tramitação
    # Resultado: ['tramitação ', '16/10/2025', ' sf-slsf - ... ação: ...', ...]
    partes = _DATE_RE.split(texto)

    # Agrupa em pares (data, corpo)
    entradas = []
    for i in range(1, len(partes) - 1, 2):
        data  = partes[i].strip()
        corpo = partes[i + 1].strip() if i + 1 < len(partes) else ""
        entradas.append((data, corpo))

    if not entradas:
        return vazio

    # Mais recente = última entrada (o accordion lista em ordem cronológica)
    data, corpo = entradas[-1]

    # Extrai órgão e descrição do corpo:  "sf-slsf - Secretaria ... ação: Autuado ..."
    corpo_lower = corpo.lower()
    if "ação:" in corpo_lower:
        idx_acao = corpo_lower.index("ação:")
        pre_acao  = corpo[:idx_acao].strip()
        descricao = corpo[idx_acao + len("ação:"):].strip()
        # Órgão = primeira "palavra" antes do " - "
        orgao = pre_acao.split(" - ")[0].split()[0].upper() if pre_acao else ""
    else:
        # Sem "ação:" explícito: pega o primeiro token como órgão e o resto como descrição
        tokens    = corpo.split()
        orgao     = tokens[0].upper() if tokens else ""
        descricao = " ".join(tokens[1:])[:250] if len(tokens) > 1 else ""

    return {
        "data":      data,
        "orgao":     orgao,
        "descricao": descricao[:250],
    }


# ── Função pública ────────────────────────────────────────────────────────────

def buscar_ultima_tramitacao(link: str) -> dict:
    """
    Recebe o link completo do Congresso Nacional e retorna a tramitação mais recente.

    Parâmetros
    ----------
    link : str
        Ex.: 'https://www.congressonacional.leg.br/materias/materias-bicamerais/-/ver/pl-5257-2025'
    """
    result = _VAZIO.copy()

    if not link or "congressonacional.leg.br" not in link:
        result["erro"] = f"Link do Congresso Nacional inválido: {link}"
        return result

    try:
        time.sleep(REQUEST_DELAY)
        resp = requests.get(link, headers=_HEADERS, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()

        if len(resp.text) < 1000:
            result["erro"] = "Página retornou conteúdo insuficiente (possível bloqueio)"
            return result

        soup = BeautifulSoup(resp.text, "lxml")

        situacao  = _extrair_situacao(soup)
        tramitacao = _extrair_tramitacao(soup)

        if not situacao and not tramitacao["data"]:
            result["erro"] = "Não foi possível extrair dados da página do Congresso"
            return result

        result["ok"]        = True
        result["situacao"]  = situacao
        result["data"]      = tramitacao["data"]
        result["orgao"]     = tramitacao["orgao"]
        result["descricao"] = tramitacao["descricao"]
        result["erro"]      = None

    except requests.exceptions.Timeout:
        result["erro"] = f"Timeout ao acessar página do Congresso"
    except requests.exceptions.HTTPError as e:
        result["erro"] = f"HTTP {e.response.status_code}"
    except requests.exceptions.RequestException as e:
        result["erro"] = f"Erro de rede: {e}"
    except Exception as e:
        result["erro"] = f"Erro inesperado: {e}"

    return result
