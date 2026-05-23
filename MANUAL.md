# 📋 Monitor de Projetos de Lei — Manual do Usuário

> Sistema para monitorar tramitações legislativas da **Câmara dos Deputados**,
> **Senado Federal** e **Congresso Nacional**, com classificação automática de
> alterações e exportação de relatórios.

---

## Sumário

1. [O que o sistema faz](#1-o-que-o-sistema-faz)
2. [Acessando o app](#2-acessando-o-app)
3. [A planilha de PLs](#3-a-planilha-de-pls)
4. [Como verificar tramitações](#4-como-verificar-tramitações)
5. [Entendendo os resultados](#5-entendendo-os-resultados)
6. [Downloads](#6-downloads)
7. [Histórico de verificações](#7-histórico-de-verificações)
8. [Adicionar ou remover um PL](#8-adicionar-ou-remover-um-pl)
9. [Verificar um PL específico](#9-verificar-um-pl-específico)
10. [Perguntas frequentes](#10-perguntas-frequentes)

---

## 1. O que o sistema faz

O Monitor de PLs acessa automaticamente os sites oficiais da Câmara dos
Deputados, do Senado Federal e do Congresso Nacional para verificar se houve
**nova movimentação** nos projetos de lei que você acompanha.

Para cada PL, o sistema retorna:

| Resultado | Significado |
|---|---|
| 🔴 **COM ALTERAÇÃO** | Houve nova tramitação desde a última verificação |
| ✅ **SEM ALTERAÇÃO** | Nenhuma mudança registrada |
| 🆕 **PRIMEIRA VERIFICAÇÃO** | PL verificado pela primeira vez (sem histórico anterior) |
| ❌ **ERRO** | Não foi possível acessar a página do PL (falha de rede, link inválido etc.) |

---

## 2. Acessando o app

Abra o link do sistema no navegador. A tela inicial exibe duas abas:

- **▶ Verificação** — aba principal para carregar a planilha e executar a verificação
- **🗂 Histórico** — consultar e resetar o histórico de tramitações salvo

---

## 3. A planilha de PLs

A planilha é o **único arquivo que você precisa manter atualizado**. Ela controla
quais projetos são monitorados.

### Formato esperado

A planilha deve ter a aba chamada **`2026 Monitoramento - PL`** com as seguintes colunas:

| Coluna | Descrição | Obrigatório? |
|---|---|---|
| SETOR | Setor econômico do PL (ex: Alimentos, Tabaco) | Não |
| CÂMARA /SENADO | Casa legislativa | Sim |
| N° - PL | Número do projeto (ex: PL 5229/2025) | Sim |
| AUTOR | Nome do autor | Não |
| APRESENTAÇÃO | Data de apresentação | Não |
| EMENTA | Descrição resumida do PL | Não |
| FORMA DE APRECIAÇÃO | Como o PL será votado | Não |
| REGIME DE TRAMITAÇÃO | Regime atual de tramitação | Não |
| **LINK PARA ACOMPANHAMENTO** | **URL oficial do PL** | **Sim** |
| PROCESSO SEI | Número do processo interno | Não |
| REPRESENTAÇÃO SETORIAL | Entidade que representa o setor | Não |
| STATUS MAIS RECENTE | Preenchido automaticamente pelo sistema | — |

### A coluna mais importante: LINK PARA ACOMPANHAMENTO

É a partir do link que o sistema identifica e consulta cada PL. Sem um link
válido, o PL é ignorado.

**Onde encontrar o link:**

- **Câmara:** acesse [camara.leg.br](https://www.camara.leg.br) → Proposições →
  busque o PL → copie a URL da página de tramitação.
  Exemplo: `https://www.camara.leg.br/proposicoesWeb/fichadetramitacao?idProposicao=2572690`

- **Senado:** acesse [senado.leg.br](https://www.senado.leg.br) → Atividade
  Legislativa → Matérias → copie a URL.
  Exemplo: `https://www25.senado.leg.br/web/atividade/materias/-/materia/171596`

- **Congresso Nacional (matérias bicamerais):** acesse
  [congressonacional.leg.br](https://www.congressonacional.leg.br) → Matérias
  Bicamerais → copie a URL.
  Exemplo: `https://www.congressonacional.leg.br/materias/materias-bicamerais/-/ver/pl-5257-2025`

---

## 4. Como verificar tramitações

### Passo a passo

**1. Carregue a planilha**

Na aba **▶ Verificação**, clique em *Planilha de PLs (.xlsx)* e selecione o
arquivo. O sistema exibirá uma confirmação com o número de PLs encontrados:

```
✅  37 PLs carregados  ·  Câmara 30  ·  Senado 6  ·  Congresso 1
```

**2. Escolha um nome para os arquivos de saída** *(opcional)*

No campo **Nome do arquivo de saída**, digite um nome descritivo.
A data de hoje é adicionada automaticamente.

Exemplos:
- `resultados_maio` → gera `resultados_maio_22-05-2026.xlsx`
- *(em branco)* → gera `resultado_22-05-2026.xlsx`

**3. Clique em ▶ Verificar agora**

O sistema processará os PLs em paralelo (até 5 por vez). O log de execução
mostra o progresso em tempo real:

```
🔄  Iniciando verificação de 37 PLs (até 5 em paralelo)...
✅  [01/37]  PL 5229/2025  →  07/05/2026
✅  [02/37]  PL 5807/2025  →  08/12/2025
❌  [03/37]  PL 3122/2025  →  Timeout ao acessar API
...
✅  Concluído  ·  22/05/2026 14:35
```

**4. Confira os resultados**

A tabela de resultados aparece logo abaixo do log, com uma linha por PL e a
classificação colorida na coluna **RESULTADO**.

---

## 5. Entendendo os resultados

### Tabela de resultados

| Coluna | Conteúdo |
|---|---|
| SETOR | Setor conforme a planilha |
| CASA | Câmara, Senado ou Congresso |
| Nº PL | Número do projeto |
| EMENTA | Descrição resumida |
| ÚLTIMA TRAMITAÇÃO | Data da movimentação mais recente |
| ÓRGÃO | Sigla do órgão responsável (ex: CCJC, PLEN) |
| SITUAÇÃO ATUAL | Status atual do PL |
| DESCRIÇÃO | Descrição da última movimentação |
| RESULTADO | 🔴 COM ALTERAÇÃO / ✅ SEM ALTERAÇÃO / 🆕 PRIMEIRA VERIFICAÇÃO / ❌ ERRO |
| OBSERVAÇÃO | Mensagem de erro (quando aplicável) |

### Como a comparação funciona

O sistema salva internamente a **data** e a **situação** da última tramitação
vista para cada PL. A cada nova verificação, compara com o que foi salvo:

- Se a **data** ou a **situação** mudou → **🔴 COM ALTERAÇÃO**
- Se ambas são iguais → **✅ SEM ALTERAÇÃO**
- Se é a primeira vez que o PL é verificado → **🆕 PRIMEIRA VERIFICAÇÃO**

> **Importante:** na primeira execução, todos os PLs aparecem como
> 🆕 PRIMEIRA VERIFICAÇÃO. Isso é esperado — o sistema ainda não tem histórico
> para comparar. A partir da segunda execução, a classificação COM/SEM
> ALTERAÇÃO passa a funcionar normalmente.

---

## 6. Downloads

Após a verificação, dois arquivos ficam disponíveis para download:

### Tabela de resultados (.xlsx)

Contém duas abas:

- **Resultado** — tabela completa com todos os PLs verificados, formatada e
  colorida por tipo de resultado
- **Resumo** — contagem por categoria (quantos COM ALTERAÇÃO, SEM ALTERAÇÃO etc.)

### Planilha atualizada (.xlsx)

É a sua planilha original com a coluna **STATUS MAIS RECENTE** atualizada
automaticamente para todos os PLs verificados com sucesso.

Formato do status atualizado:
```
* 22/05/2026 - CCJC - AGUARDANDO DESIGNAÇÃO DO RELATOR
```

> 💡 **Dica:** salve a planilha atualizada no lugar da original. Na próxima
> verificação, ela já terá o histórico mais recente.

---

## 7. Histórico de verificações

A aba **🗂 Histórico** permite consultar o estado salvo pelo sistema.

### Ver histórico atual

Clique em **🔍 Ver histórico** para exibir:

- Data e hora da última verificação
- Total de PLs no histórico
- Para cada PL: data, órgão, situação e quando foi verificado

### Resetar histórico

Clique em **🗑 Resetar histórico** para apagar todos os dados salvos. Use esta
opção quando:

- Quiser que todos os PLs sejam tratados como nova verificação
- O histórico estiver desatualizado após uma longa pausa no uso do sistema

> ⚠️ **Atenção:** ao resetar, a próxima verificação classificará todos os PLs
> como 🆕 PRIMEIRA VERIFICAÇÃO. Isso não apaga a coluna STATUS MAIS RECENTE
> da sua planilha.

---

## 8. Adicionar ou remover um PL

O sistema não exige nenhuma alteração de código para gerenciar a lista de PLs.
Tudo é feito diretamente na planilha.

### Adicionar um novo PL

1. Abra a planilha `.xlsx` no Excel ou Google Sheets
2. Vá para a aba **2026 Monitoramento - PL**
3. Insira uma nova linha com os dados do PL
4. Preencha obrigatoriamente a coluna **LINK PARA ACOMPANHAMENTO** com a URL
   oficial do PL
5. Salve o arquivo
6. Na próxima verificação, o novo PL será incluído automaticamente

### Remover um PL

- **Pausa temporária:** apague o conteúdo da célula de link. O sistema
  ignorará a linha sem excluir seus dados.
- **Remoção definitiva:** delete a linha inteira na planilha.

---

## 9. Verificar um PL específico

Para verificar apenas um ou alguns PLs sem processar a lista inteira:

1. Carregue a planilha normalmente
2. No campo **Selecionar PLs específicos**, clique e escolha os PLs desejados
   na lista suspensa (permite múltipla seleção)
3. Clique em **▶ Verificar agora**

Somente os PLs selecionados serão processados. Deixar o campo vazio verifica
todos os PLs da planilha.

---

## 10. Perguntas frequentes

**O sistema demora muito para verificar?**

Com 37 PLs, a verificação leva aproximadamente 15 a 25 segundos, pois o sistema
consulta até 5 PLs ao mesmo tempo. O progresso é exibido em tempo real no log.

---

**Por que alguns PLs aparecem com ❌ ERRO?**

Geralmente por uma destas razões:
- O link na planilha está inválido ou desatualizado
- O site da Câmara/Senado ficou temporariamente indisponível
- Timeout de rede (o sistema aguarda até 15 segundos por requisição)

**Solução:** verifique se o link abre normalmente no navegador. Se abrir, tente
executar a verificação novamente.

---

**A coluna STATUS MAIS RECENTE da planilha original é alterada?**

Sim, mas **apenas no arquivo de download** ("Planilha atualizada"). O arquivo
original que você faz upload nunca é modificado pelo sistema.

---

**Posso usar a planilha com o nome que quiser?**

Sim. O sistema lê qualquer arquivo `.xlsx` que contenha a aba
`2026 Monitoramento - PL` com as colunas no formato correto.

---

**O que acontece se eu fechar o navegador durante a verificação?**

A verificação é interrompida. Execute novamente após reabrir o app. Os PLs
já processados antes do fechamento não ficaram salvos nessa execução.

---

**Posso verificar PLs que não estão na planilha?**

No momento, não. Todos os PLs verificados precisam estar na planilha com um
link válido. Para adicionar um novo PL, siga as instruções da
[seção 8](#8-adicionar-ou-remover-um-pl).

---

*Dúvidas ou problemas? Entre em contato com o responsável pelo sistema.*
