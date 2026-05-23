<div align="center">

# 📋 Monitor de Projetos de Lei

Sistema automatizado para monitoramento de tramitações legislativas da **Câmara dos Deputados**, **Senado Federal** e **Congresso Nacional**.

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![Gradio](https://img.shields.io/badge/Gradio-6.x-FF7C00?style=for-the-badge&logo=gradio&logoColor=white)](https://gradio.app)
[![HuggingFace](https://img.shields.io/badge/HuggingFace-Spaces-FFD21E?style=for-the-badge&logo=huggingface&logoColor=black)](https://huggingface.co/spaces/Rafa06/monitor-legislativo)
[![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)](LICENSE)

[**🚀 Demo ao vivo**](https://huggingface.co/spaces/Rafa06/monitor-legislativo) · [**📖 Documentação técnica**](DOCUMENTACAO_TECNICA.md)

</div>

---

## 📌 Sobre o projeto

Projeto desenvolvido para automatizar o monitoramento de Projetos de Lei (PLs) de interesse de um cliente do setor privado. O sistema substitui o acompanhamento manual nos sites legislativos, gerando relatórios estruturados com classificação automática de alterações.

### O problema

Acompanhar dezenas de PLs manualmente exige acessar múltiplos sites, comparar status antigos com novos e registrar manualmente qualquer mudança — processo lento, repetitivo e sujeito a erros.

### A solução

Um app web que lê uma planilha de PLs, consulta as APIs oficiais da Câmara e do Senado em paralelo, compara com o histórico salvo e entrega um relatório classificado em segundos.

---

## ✨ Funcionalidades

- **Multi-casa** — suporta Câmara dos Deputados, Senado Federal e Congresso Nacional (matérias bicamerais)
- **Processamento paralelo** — até 5 scrapers simultâneos, reduzindo o tempo de 37 PLs de ~70s para ~15s
- **Classificação automática** — detecta COM ALTERAÇÃO / SEM ALTERAÇÃO / PRIMEIRA VERIFICAÇÃO por comparação de data e situação
- **Relatório formatado** — exporta `.xlsx` estilizado com destaque por tipo de resultado e aba de resumo
- **Planilha atualizada** — devolve a planilha original com o campo STATUS MAIS RECENTE preenchido
- **Busca individual** — permite selecionar PLs específicos sem processar a lista inteira
- **Histórico persistente** — salva estado entre sessões via `estado.json`
- **Deploy gratuito** — hospedado no Hugging Face Spaces

---

## 🏗️ Arquitetura

```
monitor_legislativo/
├── app.py                  # Interface Gradio (UI)
├── config.py               # Constantes globais
├── requirements.txt
│
├── scrapers/               # Camada de coleta de dados
│   ├── camara.py           # API REST dadosabertos.camara.leg.br
│   ├── senado.py           # API REST legis.senado.leg.br (2 endpoints)
│   └── congresso.py        # BeautifulSoup congressonacional.leg.br
│
├── core/                   # Lógica de negócio
│   ├── leitor.py           # Leitura e normalização da planilha
│   ├── executor.py         # Orquestração dos scrapers
│   ├── comparador.py       # Motor de comparação e classificação
│   └── formatador.py       # Geração de xlsx estilizado
│
└── data/
    ├── estado.json         # Histórico de tramitações
    └── pls_modelo.xlsx     # Planilha-modelo
```

---

## 🔄 Pipeline

```
Planilha .xlsx
      │
      ▼
 core/leitor.py          → extrai links, detecta casa (Câmara/Senado/CN),
                           normaliza dados, ignora linhas sem link
      │
      ▼
 core/executor.py        → ThreadPoolExecutor (5 workers)
      │
      ├── scrapers/camara.py    → GET /proposicoes/{id}/tramitacoes
      ├── scrapers/senado.py    → GET /materia/movimentacoes/{id}
      │                            GET /materia/{id} (fallback situação)
      └── scrapers/congresso.py → GET página HTML → BeautifulSoup
      │
      ▼
 core/comparador.py      → compara data+situação com estado.json
                           classifica cada PL
                           atualiza estado.json
                           atualiza STATUS MAIS RECENTE na planilha
      │
      ▼
 core/formatador.py      → gera xlsx resultado (estilizado)
                           gera xlsx planilha atualizada
      │
      ▼
   app.py (Gradio)       → exibe tabela + disponibiliza downloads
```

---

## 🛠️ Stack técnica

| Camada | Tecnologia |
|---|---|
| Interface | Gradio 6 |
| Scraping Câmara | `requests` + API REST JSON |
| Scraping Senado | `requests` + API REST JSON (2 endpoints) |
| Scraping Congresso | `requests` + `BeautifulSoup4` + `lxml` |
| Dados | `pandas` + `openpyxl` |
| Paralelismo | `concurrent.futures.ThreadPoolExecutor` |
| Estado | JSON file |
| Deploy | Hugging Face Spaces |

---

## 🚀 Rodando localmente

```bash
git clone https://github.com/seu-usuario/monitor-legislativo
cd monitor-legislativo

python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

pip install -r requirements.txt
python app.py
```

Acesse `http://localhost:7860`

---

## 🧪 Testes

```bash
# Testa cada scraper individualmente
python testa_scrapers.py
python testa_scrapers.py --camara 2572690
python testa_scrapers.py --senado 166666
python testa_scrapers.py --senado 166666 --debug  # inspeciona JSON bruto

# Testa o pipeline completo
python testa_pipeline.py --planilha sua_planilha.xlsx --limite 5
python testa_pipeline.py --planilha sua_planilha.xlsx --resetar
```

---

## 📊 Resultado do sistema

| Métrica | Valor |
|---|---|
| PLs suportados | Câmara + Senado + Congresso Nacional |
| Tempo médio (37 PLs) | ~15-20 segundos |
| Formato de entrada | `.xlsx` com link oficial por PL |
| Formatos de saída | Tabela de resultados `.xlsx` + Planilha atualizada `.xlsx` |

---

## 🎓 Aprendizados técnicos

- Consumo de **APIs REST públicas** (Câmara e Senado têm estruturas JSON distintas)
- **Web scraping adaptativo** — o Senado retorna estruturas JSON diferentes para PLs antigos vs. novos (2024+), exigindo parser com múltiplos caminhos de navegação
- **Processamento paralelo** com `ThreadPoolExecutor` e sincronização de resultados via `as_completed`
- **Persistência de estado** sem banco de dados — JSON como fonte de verdade entre sessões
- **Deploy serverless** no Hugging Face Spaces com Gradio

---

## 📄 Licença

MIT © Rafael
