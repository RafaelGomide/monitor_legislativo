# Documentação Técnica — Monitor de Projetos de Lei

> Documento de referência interno. Cobre arquitetura, pipeline, APIs, lógica de
> comparação e decisões de design. Escrito para consulta futura e aprimoramento.

---

## Sumário

1. [Visão geral da arquitetura](#1-visão-geral-da-arquitetura)
2. [config.py — constantes globais](#2-configpy--constantes-globais)
3. [core/leitor.py — leitura da planilha](#3-coreleitorpy--leitura-da-planilha)
4. [scrapers/camara.py — API REST da Câmara](#4-scraperscamarapy--api-rest-da-câmara)
5. [scrapers/senado.py — API REST do Senado](#5-scraperssenadopy--api-rest-do-senado)
6. [scrapers/congresso.py — scraping do Congresso Nacional](#6-scraperscongresso--scraping-do-congresso-nacional)
7. [core/executor.py — orquestração paralela](#7-coreexecutorpy--orquestração-paralela)
8. [core/comparador.py — motor de comparação](#8-corecomparadorpy--motor-de-comparação)
9. [core/formatador.py — geração de xlsx](#9-coreformatadorpy--geração-de-xlsx)
10. [app.py — interface Gradio](#10-apppy--interface-gradio)
11. [data/estado.json — persistência de estado](#11-dataestadojson--persistência-de-estado)
12. [Fluxo de dados completo](#12-fluxo-de-dados-completo)
13. [Decisões de design](#13-decisões-de-design)
14. [Limitações conhecidas e melhorias futuras](#14-limitações-conhecidas-e-melhorias-futuras)

---

## 1. Visão geral da arquitetura

O sistema é dividido em três camadas:

```
┌─────────────────────────────────────────────┐
│              INTERFACE (app.py)             │
│  Gradio Blocks — upload, botões, downloads  │
└───────────────────┬─────────────────────────┘
                    │
┌───────────────────▼─────────────────────────┐
│           LÓGICA DE NEGÓCIO (core/)         │
│  leitor → executor → comparador → formador  │
└───────────────────┬─────────────────────────┘
                    │
┌───────────────────▼─────────────────────────┐
│          COLETA DE DADOS (scrapers/)        │
│       camara.py  senado.py  congresso.py    │
└─────────────────────────────────────────────┘
```

**Princípio central:** cada camada só conhece a interface da camada abaixo. O
`app.py` não sabe como os scrapers funcionam — só chama o `executor`. O
`executor` não sabe como comparar — só devolve resultados para o `comparador`.

---

## 2. config.py — constantes globais

Centraliza todas as constantes do projeto. Qualquer valor que pode mudar
(URL de API, nome de coluna, timeout) fica aqui — nunca hardcoded nos módulos.

```python
CAMARA_API_BASE    = "https://dadosabertos.camara.leg.br/api/v2"
SENADO_API_BASE    = "https://legis.senado.leg.br/dadosabertos"

# Nomes EXATOS das colunas na planilha do cliente
COL_LINK   = "LINK PARA ACOMPANHAMENTO"
COL_STATUS = "STATUS MAIS RECENTE"
COL_CASA   = "CÂMARA /SENADO"  # atenção: espaço antes de /
# ...

ABA_PRINCIPAL  = "2026 Monitoramento - PL"
LINHA_HEADER   = 2          # cabeçalho está na linha 2 (linha 1 é título mesclado)
REQUEST_DELAY  = 0.8        # segundos entre requisições por worker
REQUEST_TIMEOUT = 15
MAX_WORKERS    = 5          # scrapers em paralelo
ESTADO_PATH    = "data/estado.json"
```

**Por que os nomes das colunas têm espaços e caracteres estranhos?**
A planilha do cliente tem células mescladas e espaços extras nos nomes
(`CÂMARA /SENADO` com espaço antes do `/`, `REPRESENTAÇÃO  SETORIAL` com
dois espaços). O `leitor.py` trata isso na leitura — o `config.py` reflete
os nomes exatos para não haver discrepância.

---

## 3. core/leitor.py — leitura da planilha

### Responsabilidade

Ler o `.xlsx` e devolver dois objetos:
- `df` — DataFrame completo (todas as colunas, todas as linhas)
- `pls` — lista de dicts com apenas os PLs monitoráveis (têm link válido)

### Problema: células mescladas geram colunas `Unnamed`

A planilha do cliente usa células mescladas horizontalmente. Quando o
`pandas` lê o arquivo, cada célula mesclada gera colunas `Unnamed: N`
para as posições vazias.

```python
# Solução: filtrar colunas que começam com "Unnamed"
df = df_raw.loc[:, ~df_raw.columns.str.startswith("Unnamed")]
```

### Problema: nome da aba tem espaço no final

A aba `"2026 Monitoramento - PL "` tem um espaço invisível no final.
A solução é comparar com `.strip()`:

```python
aba = next((a for a in wb.sheetnames if a.strip() == ABA_PRINCIPAL.strip()), abas[0])
```

### Extração de IDs

Cada URL tem um padrão diferente:

| Casa | URL | Regex | Exemplo |
|---|---|---|---|
| Câmara | `.../fichadetramitacao?idProposicao=2572690` | `idProposicao=(\d+)` | `2572690` |
| Senado | `.../materia/171596` | `/materia/(\d+)` | `171596` |
| Congresso | `.../ver/pl-5257-2025` | `/ver/([\w-]+)` | `pl-5257-2025` |

### Detecção de casa legislativa

Prioriza o link sobre a coluna `CÂMARA /SENADO`:

```python
def detectar_casa(link, casa_coluna):
    if "camara.leg.br" in link:    return "camara"
    if "senado.leg.br" in link:    return "senado"
    if "congressonacional" in link: return "congresso"
    # fallback para o valor da coluna
    if "CÂMARA" in casa_coluna.upper(): return "camara"
    if "SENADO" in casa_coluna.upper(): return "senado"
    return "desconhecido"
```

### Estrutura de saída

Cada PL na lista `pls` é um dict com:

```python
{
    "numero":       "PL 5229/2025",
    "casa":         "camara",           # camara | senado | congresso
    "link":         "https://...",
    "id_externo":   "2572690",          # extraído da URL
    "status_salvo": "* 07/05/26 - ...", # valor atual da coluna STATUS MAIS RECENTE
    "linha_df":     3,                  # índice no DataFrame para update posterior
}
```

---

## 4. scrapers/camara.py — API REST da Câmara

### Endpoint utilizado

```
GET https://dadosabertos.camara.leg.br/api/v2/proposicoes/{id}/tramitacoes
```

A Câmara dos Deputados mantém uma API REST pública e bem documentada em
`dadosabertos.camara.leg.br`. Não é necessário autenticação.

### Por que API e não scraping HTML?

A página `fichadetramitacao` renderiza parte do conteúdo via JavaScript,
o que tornaria necessário o Selenium. A API retorna JSON limpo e estável.

### Estrutura da resposta

```json
{
  "dados": [
    {
      "dataHora":              "2026-05-07T00:00:00",
      "sequencia":             42,
      "siglaOrgao":            "CCJC",
      "descricaoTramitacao":   "Recebimento pelo(a) CCJC",
      "descricaoSituacao":     "Aguardando Designação de Relator",
      "codTipoTramitacao":     "...",
      "url":                   "..."
    }
  ],
  "links": [...]
}
```

A lista `dados` vem em **ordem crescente de `sequencia`**. O último item
é sempre a tramitação mais recente.

### Lógica de extração

```python
dados = resp.json().get("dados", [])
ultima = dados[-1]  # mais recente

result["data"]      = formatar_data(ultima["dataHora"])   # "07/05/2026"
result["descricao"] = ultima["descricaoTramitacao"]
result["situacao"]  = ultima["descricaoSituacao"]
result["orgao"]     = ultima["siglaOrgao"]
```

### Headers necessários

A API da Câmara rejeita requisições sem `User-Agent`:

```python
headers = {
    "User-Agent": "MonitorLegislativo/1.0",
    "Accept":     "application/json",
}
```

---

## 5. scrapers/senado.py — API REST do Senado

### Por que dois endpoints?

O Senado tem uma API pública em `legis.senado.leg.br/dadosabertos`, mas
a estrutura da resposta varia significativamente entre PLs antigos e novos.

**PLs antigos (até ~2023):** têm o campo `Movimentacoes → Movimentacao[]`
com `DataMovimentacao` e `DescricaoMovimentacao` preenchidos.

**PLs novos (2024+):** o campo `Movimentacoes` existe mas está vazio ou
ausente. A tramitação fica em `InformesLegislativos → InformeLegislativo[]`
e a situação em `SituacoesAtuais → SituacaoAtual[]`.

Para cobrir os dois casos sem duplicar lógica, o scraper usa **dois endpoints**:

| Endpoint | Dados extraídos | Confiabilidade |
|---|---|---|
| `/materia/movimentacoes/{id}` | data, órgão, descrição | Boa para antigos, fraca para novos |
| `/materia/{id}` | situação atual | Confiável para qualquer ano |

### Estrutura da resposta — PLs novos (2024+)

Descoberta via `--debug` no script de teste:

```json
{
  "MovimentacaoMateria": {
    "Materia": {
      "Autuacoes": {
        "Autuacao": [{
          "SituacoesAtuais": {
            "SituacaoAtual": [{
              "DataSituacao":      "2025-02-10",
              "DescricaoSituacao": "AGUARDANDO DESIGNAÇÃO DO RELATOR"
            }]
          },
          "InformesLegislativos": {
            "InformeLegislativo": [{
              "Data":     "2025-02-10 09:02:13",
              "Descricao": "Não foram oferecidas emendas...",
              "Local": { "SiglaLocal": "SACCJ" }
            }]
          }
        }]
      }
    }
  }
}
```

### Lógica de parsing com múltiplos caminhos

```python
for aut in autuacoes:
    # Situação: funciona para antigos e novos
    sits = _to_list(aut.get("SituacoesAtuais", {}).get("SituacaoAtual"))
    if sits:
        sits.sort(key=lambda s: s.get("DataSituacao", ""))
        situacao = sits[-1]["DescricaoSituacao"]

    # Descrição: layout novo (InformesLegislativos)
    informes = _to_list(aut.get("InformesLegislativos", {}).get("InformeLegislativo"))
    if informes:
        informes.sort(key=lambda i: i.get("Data", ""))
        ultimo    = informes[-1]
        descricao = ultimo.get("Descricao", "")
        orgao     = ultimo.get("Local", {}).get("SiglaLocal", "")

    # Descrição: layout antigo (Movimentacoes)
    movs = _to_list(aut.get("Movimentacoes", {}).get("Movimentacao"))
    if movs:
        movs.sort(key=lambda m: m.get("DataMovimentacao", ""))
        ultimo    = movs[-1]
        descricao = descricao or ultimo.get("DescricaoMovimentacao", "")
```

### Merging dos dois endpoints

```python
mov = _extrair_de_movimentacoes(mov_json)  # data, orgao, descricao
det = _extrair_de_detalhe(det_json)        # situacao (sempre confiável)

result["data"]      = mov.get("data")     or det.get("data")
result["orgao"]     = mov.get("orgao")    or det.get("orgao")
result["descricao"] = mov.get("descricao")
result["situacao"]  = det.get("situacao") or mov.get("situacao")  # /materia/{id} tem prioridade
```

---

## 6. scrapers/congresso.py — scraping do Congresso Nacional

### Por que BeautifulSoup e não API?

O Congresso Nacional não tem uma API pública equivalente à Câmara e ao
Senado para matérias bicamerais. A tentativa inicial foi usar a API de
busca do Senado (`/materia/pesquisa/lista?sigla=PL&numero=5257&ano=2025`),
mas PLs bicamerais acompanhados no CN não aparecem nessa busca.

A solução foi fazer scraping direto da página HTML.

### Descoberta da estrutura HTML

Foi necessário rodar `debug_congresso_html.py` localmente para mapear os
seletores CSS reais da página:

```
div.cn-mb-fase--quadro--ativa    → bloco da fase ativa
  p (contendo "situação:")       → situação atual
    span                         → texto da situação

div.accordion-group              → histórico de tramitações
  (texto livre com padrão)       → "16/10/2025 SF-SLSF - Secretaria ... ação: Autuado..."
```

### Parsing do accordion por regex

O histórico de tramitações não está em uma tabela — é texto livre dentro
de um `div.accordion`. O parser divide por data:

```python
DATE_RE = re.compile(r'\b(\d{2}/\d{2}/\d{4})\b')

partes = DATE_RE.split(texto_accordion)
# ['tramitação ', '16/10/2025', ' SF-SLSF - ... ação: Autuado...', ...]

entradas = [(partes[i], partes[i+1]) for i in range(1, len(partes)-1, 2)]
data, corpo = entradas[-1]  # mais recente

# Extrai órgão e descrição do corpo
if "ação:" in corpo.lower():
    idx       = corpo.lower().index("ação:")
    orgao     = corpo[:idx].split(" - ")[0].split()[0].upper()
    descricao = corpo[idx + len("ação:"):].strip()[:250]
```

---

## 7. core/executor.py — orquestração paralela

### Problema: 37 PLs × 1.5s de delay = 55s sequencial

Cada scraper tem um `time.sleep(REQUEST_DELAY)` para evitar bloqueio por
rate limiting. Com 37 PLs sequenciais, o tempo mínimo era ~55 segundos.

### Solução: ThreadPoolExecutor

```python
with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
    future_map = {executor.submit(_scrape, pl): (i, pl) for i, pl in enumerate(pls)}

    for future in as_completed(future_map):
        i, pl      = future_map[future]
        resultado  = future.result()
        resultados[i] = resultado
        # yield para atualizar o log no Gradio
```

Com `MAX_WORKERS=5` e `REQUEST_DELAY=0.8s`:
- 37 PLs em ~⌈37/5⌉ × 0.8s = ~6s de delay puro
- + tempo de rede por requisição
- **Total real: ~15-20 segundos**

### Por que ThreadPoolExecutor e não asyncio?

Os scrapers usam `requests` que é síncrono (blocking I/O). Para usar
`asyncio` seria necessário migrar para `httpx` ou `aiohttp`. A escolha
do `ThreadPoolExecutor` mantém o código dos scrapers simples e funcionando
com a mesma base.

### Sincronização de resultados

Como `as_completed` não preserva ordem, os resultados são armazenados
por índice:

```python
resultados = [None] * total
# ...
resultados[i] = resultado  # preserva a ordem original da planilha
```

---

## 8. core/comparador.py — motor de comparação

### Chave de identificação

Cada PL é identificado pela sua **URL** no `estado.json`. URLs são mais
estáveis que números de PLs (que podem ter sufixos como "com apensação").

```python
chave = pl["link"]  # ex: "https://www.camara.leg.br/...?idProposicao=2572690"
```

### Lógica de comparação

```python
def _houve_mudanca(anterior, atual):
    return (
        str(anterior.get("data", "")).strip()     != str(atual.get("data", "")).strip()
        or
        str(anterior.get("situacao", "")).strip() != str(atual.get("situacao", "")).strip()
    )
```

**Por que comparar `data` E `situacao` juntos?**

- Só `data` não basta: uma mesma data pode ter situações diferentes (dois eventos no mesmo dia)
- Só `situacao` não basta: a situação pode voltar ao mesmo estado em uma data diferente
- A combinação dos dois garante sensibilidade sem falsos positivos

### Classificação

```python
if anterior is None:
    resultado = "🆕 PRIMEIRA VERIFICAÇÃO"
elif _houve_mudanca(anterior, tram):
    resultado = "🔴 COM ALTERAÇÃO"
else:
    resultado = "✅ SEM ALTERAÇÃO"
```

### Atualização do estado

O estado é sempre atualizado com os dados mais recentes, independente
do resultado da comparação:

```python
estado[chave] = {
    "numero":        pl["numero"],
    "data":          tram["data"],
    "situacao":      tram["situacao"],
    "orgao":         tram["orgao"],
    "descricao":     tram["descricao"],
    "verificado_em": agora,
}
```

### Atualização da planilha

O comparador também atualiza o DataFrame original (que será exportado
como "planilha atualizada"):

```python
df_out.at[linha_df, COL_STATUS] = f"* {tram['data']} - {tram['orgao']} - {tram['situacao']}"
```

### Retorno

```python
return df_resultado, df_atualizado, estado
# df_resultado:  tabela para exibição no app
# df_atualizado: planilha original com STATUS atualizado
# estado:        dict para salvar em estado.json
```

---

## 9. core/formatador.py — geração de xlsx

### Dois tipos de saída

**`salvar_resultado_xlsx(df, nome)`** — tabela de resultados com:
- Aba `Resultado`: cada PL em uma linha, colorida por tipo de resultado
- Aba `Resumo`: contagem por categoria

**`salvar_planilha_xlsx(df, nome)`** — planilha original reformatada com
STATUS MAIS RECENTE atualizado.

### Coloração por resultado

```python
MAPA_RESULTADO = {
    "🔴 COM ALTERAÇÃO":        "FFDEDE",  # vermelho claro
    "✅ SEM ALTERAÇÃO":        "DEFFED",  # verde claro
    "🆕 PRIMEIRA VERIFICAÇÃO": "FFF8DE",  # amarelo claro
    "❌ ERRO":                 "FFE8D0",  # laranja claro
}
```

A cor é aplicada na célula da coluna RESULTADO **e** em toda a linha
(versão mais clara) para facilitar a leitura visual.

### Arquivo temporário

Os xlsx são salvos em arquivo temporário e o caminho é devolvido para o
Gradio servir como download:

```python
tmp = tempfile.NamedTemporaryFile(suffix=f"_{nome}.xlsx", delete=False)
wb.save(tmp.name)
return tmp.name  # Gradio usa esse caminho no gr.File
```

---

## 10. app.py — interface Gradio

### Generator function para progresso em tempo real

O Gradio suporta funções geradoras (`yield`) para atualizar a UI
incrementalmente. Isso permite mostrar o log sendo preenchido PL por PL:

```python
def verificar(arquivo, selecao, nome_saida, pls_state, df_state):
    yield DF_VAZIO, "🔄 Lendo planilha...", None, None, gr.Markdown("")

    # ... leitura ...

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        for future in as_completed(future_map):
            # processa resultado
            yield DF_VAZIO, "\n".join(log[-20:]), None, None, gr.Markdown("")

    # resultado final
    yield df_resultado, "\n".join(log), path_res, path_pl, gr.Markdown(banner)
```

### State management no Gradio

`gr.State` armazena dados entre interações sem reprocessar a planilha a
cada clique:

```python
pls_state = gr.State([])   # lista de PLs parseados
df_state  = gr.State(None) # DataFrame original

# Populados quando o arquivo é carregado
arquivo.change(fn=ao_carregar, outputs=[info_carga, selecao, pls_state, df_state])
```

### CSS e compatibilidade Gradio 6

No Gradio 4, o CSS era passado no `gr.Blocks(css=CSS)`.
No Gradio 6 (usado no Hugging Face), o CSS vai no `app.launch(css=CSS)`.

---

## 11. data/estado.json — persistência de estado

### Estrutura

```json
{
  "_info": "Historico de tramitacoes.",
  "_ultima_verificacao": "22/05/2026 14:35",

  "https://www.camara.leg.br/...?idProposicao=2572690": {
    "numero":        "PL 5229/2025",
    "data":          "07/05/2026",
    "situacao":      "Aguardando Designação de Relator",
    "orgao":         "CCJC",
    "descricao":     "Recebimento pelo(a) CCJC",
    "verificado_em": "22/05/2026 14:35"
  }
}
```

### Por que URL como chave e não número do PL?

Números de PL têm variações na planilha do cliente:
- `"PL 5229/2025"`
- `"PL 5229/2025 com apensação dos PLs 5319/2025 e 6000/2025"`

A URL é determinística — sempre a mesma para o mesmo PL.

### Persistência no Hugging Face Spaces

No plano gratuito, o filesystem persiste entre sessões mas é apagado em
redeploys. A solução é o cliente sempre baixar a **planilha atualizada**
após cada verificação — ela funciona como backup do estado.

---

## 12. Fluxo de dados completo

Exemplo com `PL 5229/2025` (Câmara, `idProposicao=2572690`):

```
1. leitor.py lê a planilha
   → detecta link "https://www.camara.leg.br/...?idProposicao=2572690"
   → extrai id_externo = "2572690"
   → detecta casa = "camara"
   → status_salvo = "* 07/05/26 - Recebimento pelo(a) CCJC..."

2. executor.py submete ao ThreadPoolExecutor
   → chama scrapers/camara.py com id="2572690"

3. camara.py faz requisição
   → GET dadosabertos.camara.leg.br/api/v2/proposicoes/2572690/tramitacoes
   → recebe lista de 42 tramitações
   → pega a última: data="07/05/2026", descricao="Recebimento pelo(a) CCJC",
                    situacao="Aguardando Designação de Relator", orgao="CCJC"
   → retorna dict {ok:True, data, descricao, situacao, orgao}

4. comparador.py carrega estado.json
   → chave = "https://www.camara.leg.br/...?idProposicao=2572690"
   → estado anterior: {data:"07/05/2026", situacao:"Aguardando Designação de Relator"}
   → dado atual:      {data:"07/05/2026", situacao:"Aguardando Designação de Relator"}
   → datas iguais E situações iguais → "✅ SEM ALTERAÇÃO"
   → atualiza estado.json com verificado_em = agora

5. formatador.py gera resultado_22-05-2026.xlsx
   → linha verde claro com "✅ SEM ALTERAÇÃO" na coluna RESULTADO

6. app.py exibe tabela e disponibiliza download
```

---

## 13. Decisões de design

### Por que Gradio e não Flask/FastAPI?

O cliente precisa de uma interface simples: upload de arquivo, botão,
tabela, download. Gradio entrega isso com menos código e tem deploy
nativo no Hugging Face Spaces — sem necessidade de configurar servidor,
WSGI, nem templates HTML.

### Por que JSON e não banco de dados?

O volume de dados é pequeno (< 50 PLs), o acesso é sempre feito pelo
mesmo processo, e não há concorrência. Um arquivo JSON é suficiente,
mais simples de inspecionar manualmente e de fazer backup.

### Por que a planilha como fonte de verdade e não um formulário no app?

O cliente já trabalha com a planilha no dia a dia. Manter a planilha
como interface de gerenciamento elimina curva de aprendizado e permite
adicionar/remover PLs sem abrir o app.

### Por que scraping para o Congresso Nacional?

A API de busca do Senado não retorna matérias bicamerais do CN. O site
do CN usa Liferay e não tem API pública equivalente. BeautifulSoup com
seletores CSS estáveis (`cn-mb-fase--quadro--ativa`, `accordion-group`)
é suficiente para o volume de PLs.

---

## 14. Limitações conhecidas e melhorias futuras

### Limitações atuais

**Estado efêmero no HF Spaces gratuito**
O `estado.json` é apagado em redeploys. Solução parcial: o cliente
baixa a planilha atualizada após cada verificação.

**Congresso Nacional frágil**
O scraper do CN usa seletores CSS que podem quebrar se o site mudar o
layout. Uma API própria do CN resolveria permanentemente.

**PLs sem link**
PLs sem `LINK PARA ACOMPANHAMENTO` são silenciosamente ignorados. Seria
útil exibir uma lista dos PLs pulados ao final da verificação.

**Sem notificação automática**
O sistema é inteiramente manual (o usuário inicia a verificação). Uma
melhoria seria agendamento automático + notificação por e-mail quando
houver COM ALTERAÇÃO.

### Melhorias futuras

- **Agendamento** — usar APScheduler para verificação automática diária
- **Notificação** — enviar e-mail com PLs alterados via SendGrid/SMTP
- **Persistência robusta** — usar Hugging Face Dataset como storage permanente
- **Histórico visual** — linha do tempo de tramitações por PL
- **Suporte a mais casas** — Assembleias Legislativas estaduais
- **Busca por palavra-chave** — filtrar PLs por tema na ementa
