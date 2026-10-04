"""Exact user-facing strings (startup errors, banner and wire-visible primitive text)."""

FALHA_CARREGAR_DADOS = "Falha ao carregar dados/: {arquivo} {motivo}"
POLITICA_SEM_VERSAO = "Politica de uso sem versao declarada"
PORTA_EM_USO = "Porta {port} em uso: defina MCP_PORT ou encerre o processo anterior"
MCP_PORT_INVALIDA = "MCP_PORT invalida: {valor}"
FALHA_ABRIR = "Falha ao abrir {host}:{port}: {motivo}"

BANNER_OUVINDO = "central-de-salas ouvindo em http://{host}:{port}/mcp"
BANNER_SALAS = "salas carregadas: {n}"
BANNER_RESERVAS = "reservas iniciais: {n}"
BANNER_POLITICA = "politica de uso: versao {versao}"

# F02: wire-visible strings of the catalog tool and the policy resource.
DESCRICAO_LISTAR_SALAS = "Lista todas as salas com capacidade e recursos."
POLITICA_NOME = "politica-de-uso"
POLITICA_TITULO = "Politica de uso das salas"
POLITICA_DESCRICAO = "Politica de uso das salas. A primeira linha declara a versao no formato versao: <valor>."

# F03: availability tool description and policy validation messages (shared with F04/F05).
DESCRICAO_CONSULTAR_DISPONIBILIDADE = "Diz se uma sala esta livre no intervalo, e quais reservas conflitam."
SALA_INEXISTENTE = "Sala inexistente: {sala}"
HORARIO_INVALIDO = "Horario invalido: {valor}"
INTERVALO_INVALIDO = "Intervalo invalido: fim deve ser posterior a inicio"
FORA_DA_JANELA = "Fora da janela de uso: a politica permite reservas entre 08:00 e 20:00"
DURACAO_ACIMA_DO_LIMITE = "Duracao acima do limite: a politica permite no maximo 2 horas"
