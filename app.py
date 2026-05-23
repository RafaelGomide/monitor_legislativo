import gradio as gr
import pandas as pd
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

from core.leitor      import ler_planilha
from core.comparador  import comparar_e_atualizar, salvar_estado, carregar_estado
from core.formatador  import salvar_resultado_xlsx, salvar_planilha_xlsx
from config           import ESTADO_PATH, MAX_WORKERS
from scrapers.camara  import buscar_ultima_tramitacao as _buscar_camara
from scrapers.senado  import buscar_ultima_tramitacao as _buscar_senado
from scrapers.congresso import buscar_ultima_tramitacao as _buscar_congresso


# ── Utilitários ───────────────────────────────────────────────────────────────

def _scrape(pl: dict) -> dict:
    casa, id_ext, link = pl["casa"], pl.get("id_externo"), pl.get("link","")
    if   casa == "camara"    and id_ext: tram = _buscar_camara(id_ext)
    elif casa == "senado"    and id_ext: tram = _buscar_senado(id_ext)
    elif casa == "congresso" and link:   tram = _buscar_congresso(link)
    else: tram = {"ok":False,"data":"","descricao":"","situacao":"","orgao":"",
                  "erro":f"Casa '{casa}' não suportada."}
    return {**pl, "tramitacao": tram}


def _label_pl(pl: dict) -> str:
    return f"{pl['numero']} ({pl['casa'].upper()})"


# ── Carregamento da planilha ──────────────────────────────────────────────────

def ao_carregar(arquivo):
    if arquivo is None:
        return [], "Nenhuma planilha carregada.", gr.Dropdown(choices=[]), [], None
    try:
        with open(arquivo, "rb") as f:
            df, pls = ler_planilha(f)
        camara = sum(1 for p in pls if p["casa"] == "camara")
        senado = sum(1 for p in pls if p["casa"] == "senado")
        congresso = sum(1 for p in pls if p["casa"] == "congresso")
        info = (f"✅  {len(pls)} PLs carregados  ·  "
                f"Câmara {camara}  ·  Senado {senado}  ·  Congresso {congresso}")
        choices = [_label_pl(p) for p in pls]
        return info, gr.Dropdown(choices=choices, value=[]), pls, df
    except Exception as e:
        return f"❌ Erro: {e}", gr.Dropdown(choices=[]), [], None


# ── Verificação com scrapers paralelos ────────────────────────────────────────

def verificar(arquivo, selecao, nome_saida, pls_state, df_state):
    DF_VAZIO = pd.DataFrame()
    log = []

    def _emit(msg):
        log.append(msg)
        return "\n".join(log[-20:])

    if arquivo is None or not pls_state:
        yield DF_VAZIO, "⚠️  Carregue a planilha primeiro.", None, None, gr.Markdown("")
        return

    # Filtra PLs selecionados (vazio = todos)
    if selecao:
        nums = {s.split(" (")[0] for s in selecao}
        pls = [p for p in pls_state if p["numero"] in nums]
    else:
        pls = pls_state

    total = len(pls)
    from datetime import date
    _base = nome_saida.strip() or "resultado"
    _hoje = date.today().strftime("%d-%m-%Y")
    nome  = f"{_base.replace(' ','_')}_{_hoje}"

    yield DF_VAZIO, _emit(f"🔄  Iniciando verificação de {total} PLs  "
                          f"(até {MAX_WORKERS} em paralelo)..."), None, None

    # ── Scrapers paralelos ────────────────────────────────────────────────────
    resultados   = [None] * total
    completed    = 0
    lock         = threading.Lock()
    log_lines    = list(log)

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_map = {executor.submit(_scrape, pl): (i, pl) for i, pl in enumerate(pls)}

        for future in as_completed(future_map):
            i, pl = future_map[future]
            resultado = future.result()
            resultados[i] = resultado

            with lock:
                completed += 1
                t = resultado["tramitacao"]
                if t["ok"]:
                    msg = (f"✅  [{completed:02d}/{total:02d}]  "
                           f"{pl['numero'][:42]}  →  {t['data'] or 'sem data'}")
                else:
                    msg = (f"❌  [{completed:02d}/{total:02d}]  "
                           f"{pl['numero'][:42]}  →  {t['erro'][:50]}")
                log.append(msg)

            yield DF_VAZIO, "\n".join(log[-20:]), None, None, gr.Markdown("")

    # ── Comparação ────────────────────────────────────────────────────────────
    yield DF_VAZIO, _emit("─"*55 + "\n🔄  Comparando com estado anterior..."), None, None, gr.Markdown("")

    df_resultado, df_atualizado, estado = comparar_e_atualizar(
        resultados, df_state, estado_path=ESTADO_PATH
    )
    salvar_estado(estado, ESTADO_PATH)

    # ── Resumo ────────────────────────────────────────────────────────────────
    _emit("─"*55)
    contagem = df_resultado["RESULTADO"].value_counts()
    for label, count in contagem.items():
        _emit(f"   {label}  →  {count} PL(s)")
    _emit(f"\n✅  Concluído  ·  {datetime.now().strftime('%d/%m/%Y %H:%M')}")

    # ── Arquivos formatados ────────────────────────────────────────────────────
    path_res = salvar_resultado_xlsx(df_resultado,  nome)
    path_pl  = salvar_planilha_xlsx(df_atualizado,  f"{nome}_planilha")

    # Banner de resumo
    partes = []
    for label, cnt in contagem.items():
        partes.append(f"{label}  **{cnt}**")
    banner = "  ·  ".join(partes)
    yield df_resultado, "\n".join(log), path_res, path_pl, gr.Markdown(banner, visible=True)


# ── Histórico ─────────────────────────────────────────────────────────────────

def ver_estado():
    estado = carregar_estado(ESTADO_PATH)
    pls    = {k:v for k,v in estado.items() if not k.startswith("_")}
    ultima = estado.get("_ultima_verificacao") or "nunca"

    if not pls:
        return f"Última verificação: {ultima}\n\nNenhum PL no histórico ainda."

    linhas = [f"Última verificação : {ultima}",
              f"PLs no histórico   : {len(pls)}", "─"*55]
    for link, d in pls.items():
        linhas += [f"\n{d.get('numero', link)}",
                   f"  Data      : {d.get('data','—')}",
                   f"  Órgão     : {d.get('orgao','—')}",
                   f"  Situação  : {d.get('situacao','—')}",
                   f"  Verificado: {d.get('verificado_em','—')}"]
    return "\n".join(linhas)


def resetar_estado():
    p = Path(ESTADO_PATH)
    if p.exists(): p.unlink()
    return "🗑  Estado resetado. Próxima verificação tratará todos os PLs como primeira execução."


# ── CSS e tema ────────────────────────────────────────────────────────────────

CSS = """
/* Fundo geral */
body, .gradio-container { background:#0D0D1A !important; }

/* Blocos */
.gr-box, .gr-form, .block, .panel {
    background:#13132A !important;
    border:1px solid #2A2A4A !important;
    border-radius:10px !important;
}

/* Título */
h1 { color:#FFFFFF !important; letter-spacing:.5px; }
h3, label, .label-wrap span { color:#C0C0D8 !important; }

/* Inputs e textareas */
input, textarea, .gr-input, .gr-text-input {
    background:#1A1A30 !important;
    color:#FFFFFF !important;
    border:1px solid #3A3A6A !important;
    border-radius:6px !important;
}

/* Botão primário — roxo */
.primary { background: linear-gradient(135deg,#5B21B6,#2563EB) !important;
           color:#FFF !important; border:none !important;
           border-radius:8px !important; font-weight:600 !important; }
.primary:hover { background: linear-gradient(135deg,#6D28D9,#3B82F6) !important; }

/* Botão stop — vermelho escuro */
.stop { background:#7F1D1D !important; color:#FFC0C0 !important;
        border:1px solid #991B1B !important; border-radius:8px !important; }

/* Botão secundário */
button:not(.primary):not(.stop) {
    background:#1E1E3A !important; color:#A0A8FF !important;
    border:1px solid #4A4A8A !important; border-radius:8px !important; }

/* Tabs */
.tab-nav button { color:#9090C0 !important; background:transparent !important;
                  border-bottom:2px solid transparent !important; }
.tab-nav button.selected { color:#A78BFA !important;
                           border-bottom:2px solid #7C3AED !important; }

/* Log box */
.log-box textarea { font-family:monospace !important; font-size:12px !important;
                    color:#C8FFD4 !important; background:#0A0A18 !important; }

/* Dataframe */
.dataframe th { background:#1E1B4B !important; color:#FFF !important; }
.dataframe td { color:#E0E0F0 !important; background:#13132A !important; }
.dataframe tr:nth-child(even) td { background:#1A1A30 !important; }

/* File upload */
.file-preview { background:#1A1A30 !important; color:#FFF !important; }

/* Dropdown */
.wrap .multiselect { background:#1A1A30 !important; color:#FFF !important; }
"""

# ── Layout ────────────────────────────────────────────────────────────────────

with gr.Blocks(
    title="Monitor Legislativo",
    css=CSS,
    theme=gr.themes.Base(
        primary_hue=gr.themes.colors.purple,
        secondary_hue=gr.themes.colors.blue,
        neutral_hue=gr.themes.colors.slate,
    ),
) as app:

    # States
    pls_state = gr.State([])
    df_state  = gr.State(None)

    gr.Markdown(
        "# 📋 Monitor de Projetos de Lei\n"
        "Câmara dos Deputados · Senado Federal · Congresso Nacional"
    )

    with gr.Tabs():

        # ── Aba Verificação ───────────────────────────────────────────────────
        with gr.Tab("▶  Verificação"):

            with gr.Row():
                with gr.Column(scale=2):
                    arquivo = gr.File(
                        label="Planilha de PLs (.xlsx)",
                        file_types=[".xlsx"],
                    )
                    info_carga = gr.Textbox(
                        label="", lines=1, interactive=False,
                        placeholder="Carregue a planilha para começar..."
                    )
                with gr.Column(scale=2):
                    selecao = gr.Dropdown(
                        label="Selecionar PLs específicos  (vazio = verificar todos)",
                        choices=[], multiselect=True,
                        interactive=True,
                    )
                    nome_saida = gr.Textbox(
                        label="Nome do arquivo de saída",
                        placeholder="ex: resultados_maio",
                        value="resultado",
                    )
                    btn = gr.Button("▶  Verificar agora", variant="primary", size="lg")

            log_box = gr.Textbox(
                label="Log de execução",
                lines=14, interactive=False,
                elem_classes=["log-box"],
            )

            df_resultado = gr.Dataframe(
                label="Resultado",
                wrap=True, interactive=False,
            )

            resumo_md = gr.Markdown("", visible=False)
            gr.Markdown("### ⬇  Downloads")
            with gr.Row():
                dl_resultado = gr.File(label="Tabela de resultados (.xlsx)",  interactive=False)
                dl_planilha  = gr.File(label="Planilha atualizada (.xlsx)",   interactive=False)

        # ── Aba Histórico ─────────────────────────────────────────────────────
        with gr.Tab("🗂  Histórico"):
            with gr.Row():
                btn_ver   = gr.Button("🔍  Ver histórico")
                btn_reset = gr.Button("🗑  Resetar histórico", variant="stop")
            info_estado = gr.Textbox(
                label="Estado salvo", lines=22,
                interactive=False, elem_classes=["log-box"],
            )

    # ── Eventos ───────────────────────────────────────────────────────────────
    arquivo.change(
        fn=ao_carregar,
        inputs=arquivo,
        outputs=[info_carga, selecao, pls_state, df_state],
    )

    btn.click(
        fn=verificar,
        inputs=[arquivo, selecao, nome_saida, pls_state, df_state],
        outputs=[df_resultado, log_box, dl_resultado, dl_planilha, resumo_md],
    )

    btn_ver.click(fn=ver_estado,   outputs=info_estado)
    btn_reset.click(fn=resetar_estado, outputs=info_estado)


if __name__ == "__main__":
    app.launch()
