"""
python testa_scrapers.py                          → testa 4 PLs reais hardcoded
python testa_scrapers.py --camara 2572690         → id específico da Câmara
python testa_scrapers.py --senado 166666          → id específico do Senado
python testa_scrapers.py --senado 166666 --debug  → imprime JSON bruto dos dois endpoints
python testa_scrapers.py --planilha arquivo.xlsx  → testa primeiros 5 PLs da planilha
"""

import sys, json, argparse, time, requests
sys.path.insert(0, ".")

from scrapers.camara import buscar_ultima_tramitacao as buscar_camara
from scrapers.senado import buscar_ultima_tramitacao as buscar_senado
from scrapers.senado import _BASE, _HEADERS
from config import REQUEST_TIMEOUT


def _imprimir(label, r):
    status = "✅ OK" if r["ok"] else "❌ ERRO"
    print(f"\n{'─'*60}")
    print(f"  {label}  →  {status}")
    print(f"{'─'*60}")
    if r["ok"]:
        print(f"  Data       : {r['data']}")
        print(f"  Órgão      : {r['orgao']}")
        print(f"  Descrição  : {r['descricao'] or '(vazio)'}")
        print(f"  Situação   : {r['situacao'] or '(vazio)'}")
    else:
        print(f"  Erro       : {r['erro']}")


def _debug_senado(id_materia):
    """Imprime o JSON bruto dos dois endpoints do Senado."""
    for sufixo in (f"materia/movimentacoes/{id_materia}", f"materia/{id_materia}"):
        url = f"{_BASE}/{sufixo}"
        print(f"\n{'═'*60}")
        print(f"  GET {url}")
        print(f"{'═'*60}")
        try:
            r = requests.get(url, headers=_HEADERS, timeout=REQUEST_TIMEOUT)
            print(f"  Status: {r.status_code}")
            print(json.dumps(r.json(), indent=2, ensure_ascii=False)[:3000])
        except Exception as e:
            print(f"  Erro: {e}")
        time.sleep(1)


def testar_ids_fixos():
    print("\n════  CÂMARA  ════")
    _imprimir("PL 5229/2025 (id 2572690)", buscar_camara("2572690"))
    _imprimir("PL 6021/2019 (id 1299577)", buscar_camara("1299577"))

    print("\n════  SENADO  ════")
    _imprimir("PL 5807/2025 (id 171596)",  buscar_senado("171596"))
    _imprimir("PL 4789/2024 (id 166464)",  buscar_senado("166464"))

    print("\n════  CONGRESSO  ════")
    _imprimir("PL 5257/2025", __import__('scrapers.congresso', fromlist=['buscar_ultima_tramitacao']).buscar_ultima_tramitacao("https://www.congressonacional.leg.br/materias/materias-bicamerais/-/ver/pl-5257-2025"))


def testar_planilha(caminho):
    from core.leitor import ler_planilha
    from core.executor import coletar_todos

    print(f"\nLendo planilha: {caminho}")
    with open(caminho, "rb") as f:
        df, pls = ler_planilha(f)

    print(f"{len(pls)} PLs encontrados. Testando os primeiros 5...\n")

    def prog(i, total, num):
        print(f"  [{i+1}/{total}] {num} ...", end=" ", flush=True)

    for r in coletar_todos(pls[:5], callback=prog):
        print()
        _imprimir(f"{r['casa'].upper()} · {r['numero']}", r["tramitacao"])



def testar_congresso(link):
    from scrapers.congresso import buscar_ultima_tramitacao as buscar_cn
    _imprimir(f"Congresso: {link.split('/')[-1]}", buscar_cn(link))


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--camara",   metavar="ID")
    p.add_argument("--senado",   metavar="ID")
    p.add_argument("--debug",    action="store_true", help="imprime JSON bruto (Senado)")
    p.add_argument("--congresso", metavar="LINK")
    p.add_argument("--planilha", metavar="ARQUIVO")
    args = p.parse_args()

    if args.debug and args.senado:
        _debug_senado(args.senado)
    elif args.camara:
        _imprimir(f"Câmara id={args.camara}", buscar_camara(args.camara))
    elif args.senado:
        _imprimir(f"Senado id={args.senado}", buscar_senado(args.senado))
    elif args.congresso:
        testar_congresso(args.congresso)
    elif args.planilha:
        testar_planilha(args.planilha)
    else:
        testar_ids_fixos()
