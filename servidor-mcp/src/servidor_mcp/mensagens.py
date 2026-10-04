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
