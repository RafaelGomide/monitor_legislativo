"""
Orquestrador da fase de coleta.
Recebe a lista de PLs do leitor.py e chama o scraper correto para cada um.
"""

from scrapers.camara    import buscar_ultima_tramitacao as _buscar_camara
from scrapers.senado    import buscar_ultima_tramitacao as _buscar_senado
from scrapers.congresso import buscar_ultima_tramitacao as _buscar_congresso


def coletar_todos(pls: list[dict], callback=None) -> list[dict]:
    """
    Para cada PL na lista, chama o scraper adequado.

    Parâmetros
    ----------
    pls      : lista retornada por core.leitor.ler_planilha()
    callback : função opcional chamada a cada PL — recebe (i, total, numero)

    Retorno
    -------
    Lista de dicts com campo 'tramitacao' adicionado.
    """
    resultados = []
    total = len(pls)

    for i, pl in enumerate(pls):
        if callback:
            callback(i, total, pl["numero"])

        casa       = pl["casa"]
        id_externo = pl.get("id_externo")
        link       = pl.get("link", "")

        if casa == "camara" and id_externo:
            tramitacao = _buscar_camara(id_externo)

        elif casa == "senado" and id_externo:
            tramitacao = _buscar_senado(id_externo)

        elif casa == "congresso" and link:
            # O scraper do Congresso recebe o link completo e resolve internamente
            tramitacao = _buscar_congresso(link)

        else:
            tramitacao = {
                "ok": False, "data": "", "descricao": "",
                "situacao": "", "orgao": "",
                "erro": f"Casa '{casa}' não suportada ou link ausente.",
            }

        resultados.append({**pl, "tramitacao": tramitacao})

    return resultados
