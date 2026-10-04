"""Exact user-facing strings (errors, Task messages, banner, startup failures).

Never inline user-facing strings.
"""

# JSON-RPC errors
ERRO_PARSE = "Erro de parse: o corpo nao e JSON valido"
REQUISICAO_INVALIDA = "Requisicao invalida: {detalhe}"
METODO_NAO_ENCONTRADO = "Metodo nao encontrado: {method}"
PARAMETROS_INVALIDOS = "Parametros invalidos: {detalhe}"
ERRO_INTERNO_AGENTE = "Erro interno do agente"
TASK_NAO_ENCONTRADA = "Task nao encontrada: {id}"
TASK_TERMINAL = "Task {id} esta em estado terminal: {state}"
TASK_NAO_AGUARDA_ENTRADA = "Task {id} nao aguarda entrada"
CONTEUDO_NAO_SUPORTADO = "Tipo de conteudo nao suportado: o agente aceita apenas partes de texto"
VERSAO_NAO_SUPORTADA = "Versao do protocolo A2A nao suportada: {valor}"

# Envelope details
DET_CORPO_NAO_OBJETO = "corpo deve ser um objeto JSON"
DET_LOTES = "lotes nao sao suportados"
DET_JSONRPC = 'jsonrpc deve ser "2.0"'
DET_METHOD = "method ausente ou nao textual"
DET_ID = "id ausente ou com tipo invalido"

# Params details
DET_PARAMS_OBJETO = "params deve ser um objeto"
DET_MESSAGE_AUSENTE = "params.message ausente"
DET_MESSAGE_OBJETO = "params.message deve ser um objeto"
DET_MESSAGE_ID = "params.message.messageId deve ser texto nao vazio"
DET_MESSAGE_ROLE = "params.message.role deve ser ROLE_USER"
DET_MESSAGE_PARTS = "params.message.parts deve ser uma lista nao vazia"
DET_MESSAGE_PART_INVALIDA = "params.message.parts[{i}] invalida"
DET_MESSAGE_TASK_ID = "params.message.taskId deve ser texto nao vazio"
DET_MESSAGE_CONTEXT_ID = "params.message.contextId deve ser texto nao vazio"
DET_ID_AUSENTE = "params.id ausente"
DET_ID_TEXTO = "params.id deve ser texto nao vazio"

# Task messages
FALHA_INTERNA = "Falha interna do agente"

# Reservation skill
PEDIDO_INVALIDO = (
    "Pedido invalido: use reservar sala=<id> inicio=<iso8601> fim=<iso8601> responsavel=<nome>"
)
RESERVA_CONFIRMADA = "Reserva {reserva} confirmada na {sala}."

# Bridge
ALTERNATIVAS = "alternativas: {lista}"
RESERVA_RECUSADA = "Reserva recusada: nenhuma alternativa escolhida."

# MCP host client
MCP_INDISPONIVEL = "Servidor MCP indisponivel"
MCP_ERRO = "Erro do servidor MCP: {detalhe}"
MCP_FERRAMENTA_AUSENTE = "Ferramenta {nome} nao encontrada no servidor MCP"
MCP_ARGUMENTOS_INCOMPATIVEIS = "Ferramenta {nome} anunciada com inputSchema incompativel com o pedido"
POLITICA_SEM_VERSAO = "Politica de uso sem versao declarada"
MCP_PEDIDO_NAO_SUPORTADO = "Pedido de entrada nao suportado pelo agente"
MCP_RESPOSTA_INESPERADA = "Resposta inesperada do servidor MCP"

# Startup
MCP_URL_INVALIDA = "MCP_URL invalida: {valor}"
AGENT_PORT_INVALIDA = "AGENT_PORT invalida: {valor}"
AGENT_PUBLIC_URL_INVALIDA = "AGENT_PUBLIC_URL invalida: {valor}"
PORTA_EM_USO = "Porta {port} em uso: defina AGENT_PORT ou encerre o processo anterior"
FALHA_ABRIR = "Falha ao abrir {host}:{port}: {motivo}"

BANNER_OUVINDO = "agente central-de-salas ouvindo em http://{host}:{port}"
BANNER_CARD = "agent card: http://{host}:{port}/.well-known/agent-card.json"
BANNER_ENDPOINT = "endpoint A2A anunciado: {public_url}/a2a"
