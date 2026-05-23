"""
Testa o parser do Congresso com o HTML já salvo localmente.
Não precisa de rede.

    python debug_congresso_parser.py
"""
import sys
sys.path.insert(0, ".")

from bs4 import BeautifulSoup
from scrapers.congresso import _extrair_situacao, _extrair_tramitacao

with open("debug_cn_page.html", encoding="utf-8") as f:
    soup = BeautifulSoup(f.read(), "lxml")

situacao   = _extrair_situacao(soup)
tramitacao = _extrair_tramitacao(soup)

print("=== RESULTADO DO PARSER ===")
print(f"  Situação  : {situacao or '(vazio)'}")
print(f"  Data      : {tramitacao['data'] or '(vazio)'}")
print(f"  Órgão     : {tramitacao['orgao'] or '(vazio)'}")
print(f"  Descrição : {tramitacao['descricao'][:120] or '(vazio)'}")
