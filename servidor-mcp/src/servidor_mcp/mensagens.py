"""Exact user-facing strings (startup errors and banner)."""

FALHA_CARREGAR_DADOS = "Falha ao carregar dados/: {arquivo} {motivo}"
POLITICA_SEM_VERSAO = "Politica de uso sem versao declarada"
PORTA_EM_USO = "Porta {port} em uso: defina MCP_PORT ou encerre o processo anterior"
MCP_PORT_INVALIDA = "MCP_PORT invalida: {valor}"
FALHA_ABRIR = "Falha ao abrir {host}:{port}: {motivo}"

BANNER_OUVINDO = "central-de-salas ouvindo em http://{host}:{port}/mcp"
BANNER_SALAS = "salas carregadas: {n}"
BANNER_RESERVAS = "reservas iniciais: {n}"
BANNER_POLITICA = "politica de uso: versao {versao}"
