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

# Wire-visible strings of the catalog tool and the policy resource.
DESCRICAO_LISTAR_SALAS = "Lista todas as salas com capacidade e recursos."
POLITICA_NOME = "politica-de-uso"
POLITICA_TITULO = "Politica de uso das salas"
POLITICA_DESCRICAO = "Politica de uso das salas. A primeira linha declara a versao no formato versao: <valor>."

# Availability tool description and policy validation messages (shared with the reservation).
DESCRICAO_CONSULTAR_DISPONIBILIDADE = "Diz se uma sala esta livre no intervalo, e quais reservas conflitam."
SALA_INEXISTENTE = "Sala inexistente: {sala}"
HORARIO_INVALIDO = "Horario invalido: {valor}"
INTERVALO_INVALIDO = "Intervalo invalido: fim deve ser posterior a inicio"
FORA_DA_JANELA = "Fora da janela de uso: a politica permite reservas entre 08:00 e 20:00"
DURACAO_ACIMA_DO_LIMITE = "Duracao acima do limite: a politica permite no maximo 2 horas"

# Reservation tool description and failure messages.
DESCRICAO_RESERVAR_SALA = "Reserva uma sala. Se o intervalo estiver ocupado, pergunta qual alternativa usar."
FALHA_INTERNA_RESERVA = "Falha interna ao registrar a reserva"

# MRTR conflict resolution and request-state security.
SEGREDO_INVALIDO = (
    "REQUEST_STATE_SECRET ausente ou com menos de 32 bytes: "
    'gere com python3 -c "import secrets; print(secrets.token_hex(32))"'
)
MENSAGEM_ESCOLHA = "A sala pedida esta ocupada nesse intervalo. Escolha uma alternativa."
CAMPO_SALA_TITULO = "Sala"
CAMPO_SALA_DESCRICAO = "Sala alternativa escolhida"
SEM_ALTERNATIVAS = "Sem alternativas disponiveis no intervalo"
ESTADO_INVALIDO = "Invalid or expired requestState"
RESPOSTA_AUSENTE = "inputResponses sem resposta para {chave}"
CAPACIDADE_AUSENTE = "Client did not declare the form elicitation capability required by '{chave}'"
