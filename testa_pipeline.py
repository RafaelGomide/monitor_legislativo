"""
Teste completo do pipeline — sem Gradio.

    python testa_pipeline.py --planilha MONITORAMENTO_DE_PROJETOS_DE_LEI.xlsx
    python testa_pipeline.py --planilha MONITORAMENTO_DE_PROJETOS_DE_LEI.xlsx --limite 5
    python testa_pipeline.py --planilha MONITORAMENTO_DE_PROJETOS_DE_LEI.xlsx --resetar

Flags
-----
--planilha  Caminho do .xlsx do cliente (obrigatório)
--limite    Quantos PLs processar (padrão: todos)
--resetar   Apaga o estado.json antes de rodar (simula primeira execução)
"""

import sys
import json
import argparse
import time
from pathlib import Path

sys.path.insert(0, ".")

from core.leitor      import ler_planilha
from core.executor    import coletar_todos
from core.comparador  import comparar_e_atualizar, salvar_estado, carregar_estado
from config           import ESTADO_PATH


# ── Helpers de exibição ───────────────────────────────────────────────────────

SEP  = "─" * 65
SEP2 = "═" * 65

def _h(titulo: str):
    print(f"\n{SEP2}\n  {titulo}\n{SEP2}")

def _linha(label: str, valor: str):
    print(f"  {label:<22}: {valor}")


# ── Pipeline ──────────────────────────────────────────────────────────────────

def rodar(caminho_planilha: str, limite: int | None, resetar: bool):

    # 0. Opcional: apaga estado para simular primeira execução
    if resetar:
        path = Path(ESTADO_PATH)
        if path.exists():
            path.unlink()
            print(f"[INFO] estado.json apagado — simulando primeira execução.")

    # ── FASE 1: Leitura da planilha ───────────────────────────────────────────
    _h("FASE 1 — Leitura da planilha")
    t0 = time.time()

    with open(caminho_planilha, "rb") as f:
        df, pls = ler_planilha(f)

    if limite:
        pls = pls[:limite]

    camara  = sum(1 for p in pls if p["casa"] == "camara")
    senado  = sum(1 for p in pls if p["casa"] == "senado")
    congresso = sum(1 for p in pls if p["casa"] == "congresso")
    outros  = len(pls) - camara - senado - congresso

    _linha("Total de linhas",   str(len(df)))
    _linha("PLs a processar",   str(len(pls)))
    _linha("  Câmara",          str(camara))
    _linha("  Senado",          str(senado))
    _linha("  Congresso",       str(congresso))
    _linha("  Sem casa",        str(outros))
    print(f"\n  ✅ Planilha lida em {time.time()-t0:.1f}s")

    # ── FASE 2: Scrapers ──────────────────────────────────────────────────────
    _h("FASE 2 — Coleta de tramitações")
    t1 = time.time()

    erros_scraper = []

    def progresso(i, total, numero):
        print(f"  [{i+1:02d}/{total:02d}] {numero[:50]:<50}", end=" ", flush=True)

    resultados = coletar_todos(pls, callback=progresso)

    for r in resultados:
        t = r["tramitacao"]
        if t["ok"]:
            print(f"✅  {t['data'] or '(sem data)'}")
        else:
            print(f"❌  {t['erro'][:60]}")
            erros_scraper.append(r["numero"])

    print(f"\n  Concluído em {time.time()-t1:.1f}s")
    print(f"  Erros de scraper: {len(erros_scraper)}")

    # ── FASE 3: Comparação ────────────────────────────────────────────────────
    _h("FASE 3 — Comparação com estado anterior")
    t2 = time.time()

    estado_antes = carregar_estado(ESTADO_PATH)
    pls_no_estado = len([k for k in estado_antes if not k.startswith("_")])
    print(f"  PLs no estado.json antes: {pls_no_estado}")

    df_resultado, df_atualizado, estado_novo = comparar_e_atualizar(
        resultados, df, estado_path=ESTADO_PATH
    )

    salvar_estado(estado_novo, ESTADO_PATH)
    pls_no_estado_depois = len([k for k in estado_novo if not k.startswith("_")])
    print(f"  PLs no estado.json depois: {pls_no_estado_depois}")
    print(f"\n  ✅ Comparação concluída em {time.time()-t2:.1f}s")

    # ── RESULTADO FINAL ───────────────────────────────────────────────────────
    _h("RESULTADO FINAL")

    contagem = df_resultado["RESULTADO"].value_counts()
    for label, count in contagem.items():
        print(f"  {label}  →  {count} PL(s)")

    print(f"\n{SEP}")
    print(f"  {'RESULTADO':<30} {'CASA':<10} {'Nº PL'}")
    print(SEP)

    for _, row in df_resultado.iterrows():
        res    = row["RESULTADO"]
        casa   = str(row["CASA"])[:8]
        numero = str(row["Nº PL"])[:40]
        print(f"  {res:<30} {casa:<10} {numero}")

    # ── Detalhe dos PLs COM ALTERAÇÃO ─────────────────────────────────────────
    alterados = df_resultado[df_resultado["RESULTADO"] == "🔴 COM ALTERAÇÃO"]
    if not alterados.empty:
        print(f"\n{SEP}")
        print("  DETALHE — PLs com alteração:")
        print(SEP)
        for _, row in alterados.iterrows():
            print(f"\n  PL        : {row['Nº PL']}")
            print(f"  Data      : {row['ÚLTIMA TRAMITAÇÃO']}")
            print(f"  Órgão     : {row['ÓRGÃO']}")
            print(f"  Situação  : {row['SITUAÇÃO ATUAL']}")
            print(f"  Descrição : {row['DESCRIÇÃO'][:100]}")

    # ── Erros ─────────────────────────────────────────────────────────────────
    erros_df = df_resultado[df_resultado["RESULTADO"] == "❌ ERRO"]
    if not erros_df.empty:
        print(f"\n{SEP}")
        print("  ERROS:")
        print(SEP)
        for _, row in erros_df.iterrows():
            print(f"  {row['Nº PL'][:45]} → {row['OBSERVAÇÃO'][:60]}")

    print(f"\n{SEP2}")
    total = time.time() - t0
    print(f"  Pipeline concluído em {total:.1f}s  |  {len(pls)} PLs processados")
    print(SEP2)


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--planilha", required=True, metavar="ARQUIVO",
                        help="Caminho para o .xlsx do cliente")
    parser.add_argument("--limite",   type=int, default=None, metavar="N",
                        help="Limita a N PLs (útil para teste rápido)")
    parser.add_argument("--resetar",  action="store_true",
                        help="Apaga estado.json antes de rodar")
    args = parser.parse_args()

    rodar(args.planilha, args.limite, args.resetar)
