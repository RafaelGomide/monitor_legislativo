"""
Roda na sua máquina e salva o HTML da página do Congresso para análise.

    python debug_congresso_html.py
"""
import requests, sys, re
from bs4 import BeautifulSoup

URL = "https://www.congressonacional.leg.br/materias/materias-bicamerais/-/ver/pl-5257-2025"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept-Language": "pt-BR,pt;q=0.9",
    "Accept": "text/html,application/xhtml+xml",
}

print(f"Buscando: {URL}")
r = requests.get(URL, headers=HEADERS, timeout=20)
print(f"Status: {r.status_code}")
print(f"Tamanho: {len(r.text)} chars\n")

soup = BeautifulSoup(r.text, "lxml")

# ── 1. Imprime o <title> para confirmar que a página certa foi carregada ──────
print("=== TITLE ===")
print(soup.title.string if soup.title else "(sem title)")

# ── 2. Procura por palavras-chave de tramitação na página ─────────────────────
keywords = ["tramit", "situaç", "moviment", "status", "andament", "despacho"]
print("\n=== ELEMENTOS COM PALAVRAS-CHAVE DE TRAMITAÇÃO ===")
encontrados = set()
for tag in soup.find_all(True):
    texto = (tag.get_text(" ", strip=True) or "").lower()
    classe = " ".join(tag.get("class", []))
    tag_id = tag.get("id", "")
    for kw in keywords:
        if kw in texto and len(texto) < 300 and tag.name in ("h1","h2","h3","h4","div","span","td","th","li","p","section"):
            chave = f"<{tag.name} class='{classe}' id='{tag_id}'>"
            if chave not in encontrados:
                encontrados.add(chave)
                print(f"  {chave}")
                print(f"    → {texto[:150]}")

# ── 3. Todas as tabelas da página ─────────────────────────────────────────────
print("\n=== TABELAS ENCONTRADAS ===")
for i, table in enumerate(soup.find_all("table")):
    cls = " ".join(table.get("class", []))
    linhas = table.find_all("tr")
    primeira = linhas[0].get_text(" ", strip=True)[:100] if linhas else ""
    print(f"  Tabela {i}: class='{cls}'  linhas={len(linhas)}  primeira='{primeira}'")

# ── 4. Salva HTML completo para inspeção ──────────────────────────────────────
with open("debug_cn_page.html", "w", encoding="utf-8") as f:
    f.write(r.text)
print("\n✅ HTML completo salvo em debug_cn_page.html")
print("   Abra no navegador ou procure por 'tramit' no arquivo.")
