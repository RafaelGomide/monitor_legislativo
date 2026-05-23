# ── URLs das casas legislativas ───────────────────────────────────────────────
CAMARA_API_BASE    = "https://dadosabertos.camara.leg.br/api/v2"
SENADO_MATERIA_URL = "https://www25.senado.leg.br/web/atividade/materias/-/materia/{id}"

# ── Nomes EXATOS das colunas na planilha do cliente (como aparecem no arquivo) ─
COL_SETOR         = "SETOR"
COL_CASA          = "CÂMARA /SENADO"           # atenção: espaço antes do /
COL_NUMERO        = "N° - PL"
COL_AUTOR         = "AUTOR"
COL_APRESENTACAO  = "APRESENTAÇÃO"
COL_EMENTA        = "EMENTA"
COL_EMENTA        = "EMENTA"
COL_FORMA         = "FORMA DE APRECIAÇÃO"
COL_REGIME        = "REGIME DE TRAMITAÇÃO"
COL_LINK          = "LINK PARA ACOMPANHAMENTO"
COL_SEI           = "PROCESSO SEI"
COL_REPRESENTACAO = "REPRESENTAÇÃO  SETORIAL"  # atenção: dois espaços
COL_STATUS        = "STATUS MAIS RECENTE"

# Colunas mínimas necessárias para o sistema funcionar
COLUNAS_OBRIGATORIAS = [COL_CASA, COL_LINK, COL_STATUS, COL_NUMERO]

# Nome da aba principal (strip() é aplicado na comparação)
ABA_PRINCIPAL = "2026 Monitoramento - PL"

# Linha do cabeçalho na planilha (1-indexed)
LINHA_HEADER = 2

# ── Caminhos de arquivo ───────────────────────────────────────────────────────
ESTADO_PATH = "data/estado.json"

# ── Parâmetros de rede ────────────────────────────────────────────────────────
REQUEST_DELAY   = 0.8
REQUEST_TIMEOUT = 15
MAX_WORKERS     = 5   # scrapers paralelos
