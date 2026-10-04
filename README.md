# A Ponte — Central de Salas

Dois processos que conversam por HTTP: um **servidor MCP** (porta 7301, Streamable HTTP, três tools, um resource e o ciclo MRTR completo na tool de reserva) e um **agente** (porta 7300) que é host MCP por dentro e servidor A2A por fora (Agent Card, `SendMessage`, `GetTask`). Quando o servidor MCP responde `input_required`, o agente pausa a Task em `TASK_STATE_INPUT_REQUIRED`, devolve as alternativas ao cliente A2A e, quando a escolha chega, repete o `tools/call` com um id novo e o `requestState` guardado. O agente não usa LLM: interpreta um pedido de formato fixo e decide por regra.

Starter do desafio: <https://github.com/devfullcycle/desafio-a2a-com-mcp>

## Como rodar

**Pré-requisitos:** Python 3.10 ou mais novo, `git` e `curl`. Em Debian/Ubuntu, instale também o módulo de ambientes virtuais (`sudo apt install python3-venv`); sem ele o `python3 -m venv` falha com um aviso sobre o `ensurepip`. Os comandos abaixo são para Linux/macOS (ou WSL / Git Bash). Para PowerShell, veja [Windows (PowerShell)](#windows-powershell).

Use **três terminais**: um para o servidor MCP, um para o agente e um para o validador.

1. **Clonar** o repositório e entrar na raiz:

   ```bash
   git clone https://github.com/miguelmarques1/desafio-a2a-com-mcp.git
   cd desafio-a2a-com-mcp
   ```

2. **Criar e ativar o ambiente virtual** (um único `.venv` na raiz, usado pelos dois pacotes):

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

3. **Instalar os dois pacotes** em modo editável (as dependências já vêm com versão fixa `==`):

   ```bash
   pip install -e ./servidor-mcp -e ./agente
   ```

   Opcional, para reproduzir também as versões das dependências transitivas da execução registrada abaixo: `pip install -c constraints.txt -e ./servidor-mcp -e ./agente`.

4. **Gerar o segredo do `requestState`.** Só o servidor MCP precisa dele; o agente não lê esse valor. O segredo tem de ter pelo menos 64 caracteres hexadecimais (32 bytes). Gere e exporte no **terminal 1**:

   ```bash
   export REQUEST_STATE_SECRET="$(python3 -c 'import secrets; print(secrets.token_hex(32))')"
   ```

   Sem um segredo válido o servidor encerra com código `1` e a mensagem `REQUEST_STATE_SECRET ausente ou com menos de 32 bytes`. Nenhum valor de segredo é versionado: o `.env` está no `.gitignore`. Se for reiniciar o servidor no meio de um teste (passo 12 do [Roteiro manual](#roteiro-manual)), reutilize **o mesmo valor**, senão os `requestState` já emitidos deixam de valer. O atalho com `.env` (abaixo) resolve isso.

5. **Terminal 1 — servidor MCP** (com o `.venv` ativo e o segredo exportado):

   ```bash
   source .venv/bin/activate
   python -m servidor_mcp
   ```

   Saída esperada (stderr):

   ```text
   central-de-salas ouvindo em http://127.0.0.1:7301/mcp
   salas carregadas: 5
   reservas iniciais: 2
   politica de uso: versao 2026-11-01
   ```

6. **Terminal 2 — agente** (com o `.venv` ativo; não precisa do segredo):

   ```bash
   source .venv/bin/activate
   python -m agente
   ```

   Saída esperada (stderr):

   ```text
   agente central-de-salas ouvindo em http://127.0.0.1:7300
   agent card: http://127.0.0.1:7300/.well-known/agent-card.json
   endpoint A2A anunciado: http://localhost:7300/a2a
   ```

7. **Terminal 3 — validador** (só biblioteca padrão; não precisa do `.venv`):

   ```bash
   python3 validador/validar.py --agente http://localhost:7300 --mcp http://localhost:7301
   ```

   Termina com `resumo: 36 passaram, 0 falharam, de 36 verificacoes` e código de saída `0`. A primeira linha imprime o trace-id da execução; procure esse valor no stderr do terminal 1 para conferir a propagação do `traceparent`.

**Regra de reexecução:** as reservas criadas por uma execução mudam o resultado da seguinte. Antes de **cada** execução do validador (e antes do Roteiro manual), reinicie os dois processos (Ctrl+C e os mesmos comandos de subida). Rodar duas vezes seguidas sem reiniciar produz falsos negativos, como diz o `validador/README.md`.

### Variáveis de ambiente

| Variável | Processo | Padrão | Descrição |
|---|---|---|---|
| `REQUEST_STATE_SECRET` | servidor MCP | obrigatório | Segredo do `requestState`, pelo menos 64 caracteres hexadecimais (32 bytes) |
| `MCP_PORT` | servidor MCP | `7301` | Porta do servidor MCP |
| `MCP_HOST` | servidor MCP | `127.0.0.1` | Interface de escuta |
| `MCP_DADOS_DIR` | servidor MCP | automático | Pasta com `salas.json`, `reservas.json` e a política. Por padrão é achada a partir do pacote instalado (primeiro ancestral que contém `dados/` e `servidor-mcp/`) e depois a partir do diretório atual |
| `AGENT_PORT` | agente | `7300` | Porta do agente |
| `AGENT_HOST` | agente | `127.0.0.1` | Interface de escuta |
| `AGENT_PUBLIC_URL` | agente | `http://localhost:<AGENT_PORT>` | URL pública anunciada no Agent Card (o endpoint A2A anunciado é `<AGENT_PUBLIC_URL>/a2a`) |
| `MCP_URL` | agente | `http://localhost:7301/mcp` | Endpoint do servidor MCP que o agente consome |

### Atalho: scripts de subida

Os scripts ativam o `.venv` da raiz, carregam o `.env` (se existir) e iniciam um processo em primeiro plano. Variáveis já exportadas no terminal **têm precedência** sobre o `.env`. Os scripts nunca geram segredo.

```bash
cp .env.example .env
python3 -c "import secrets; print('REQUEST_STATE_SECRET=' + secrets.token_hex(32))" > .env   # ou edite o .env e cole o valor
./subir-servidor-mcp.sh     # terminal 1
./subir-agente.sh           # terminal 2
```

O `.env.example` é versionado com `REQUEST_STATE_SECRET=` vazio e os padrões comentados; o `.env` real nunca é versionado. Um segredo vazio faz o servidor encerrar com a própria mensagem de erro. Se `./subir-*.sh` não for executável no seu sistema de arquivos, use `bash subir-servidor-mcp.sh`.

### Windows (PowerShell)

```powershell
py -3 -m venv .venv                      # ou: python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ./servidor-mcp -e ./agente

# terminal 1
$env:REQUEST_STATE_SECRET = (python -c "import secrets; print(secrets.token_hex(32))")
python -m servidor_mcp

# terminal 2 (com o .venv ativo)
python -m agente

# terminal 3
python validador\validar.py --agente http://localhost:7300 --mcp http://localhost:7301
```

Se uma política de aplicativos do Windows bloquear o executável `pip.exe`, use `python -m pip install -e ./servidor-mcp -e ./agente` (é o mesmo comando). Os scripts equivalentes são `.\subir-servidor-mcp.ps1` e `.\subir-agente.ps1` (leem o mesmo `.env`). Se a política de execução bloquear scripts: `powershell -ExecutionPolicy Bypass -File .\subir-servidor-mcp.ps1`. No Windows, `localhost` pode resolver primeiro para `::1`; se o agente não alcançar o servidor MCP, defina `MCP_URL=http://127.0.0.1:7301/mcp` antes de subir o agente.

### Testes automatizados

```bash
pip install -e "./servidor-mcp[dev]" -e "./agente[dev]"
python -m pytest servidor-mcp
python -m pytest agente
python -m pytest tests          # checagens estáticas da entrega (README, scripts, pins, starter intacto)
```

### Roteiro manual

Reproduz os passos 7 a 13 do fluxo do avaliador com `curl`. Rode **logo após subir os dois processos do zero** (e antes do validador), na raiz do repositório, em bash com `python3` e `curl`. Os corpos dos requests são extraídos de `exemplos/wire/`; os valores vivos (`taskId`, `requestState`, chave de `inputRequests`, texto) são substituídos na hora.

Defina os auxiliares uma vez (`corpo` imprime o `request.body` de um arquivo de `exemplos/wire/` com ajustes `caminho.pontuado=valor`; `campo` lê um valor de uma resposta JSON, e `@0` pega a primeira chave de um objeto):

```bash
corpo() { python3 -c '
import json, sys
arquivo, *ajustes = sys.argv[1:]
corpo = json.load(open("exemplos/wire/" + arquivo, encoding="utf-8"))["request"]["body"]
for ajuste in ajustes:
    caminho, valor = ajuste.split("=", 1)
    if caminho == "chave":
        respostas = corpo["params"]["inputResponses"]
        respostas[valor] = respostas.pop(next(iter(respostas)))
        continue
    *trilha, ultimo = caminho.split(".")
    alvo = corpo
    for passo in trilha:
        alvo = alvo[int(passo)] if isinstance(alvo, list) else alvo[passo]
    alvo[int(ultimo) if isinstance(alvo, list) else ultimo] = valor
print(json.dumps(corpo, ensure_ascii=False, separators=(",", ":")))
' "$@"; }

campo() { python3 -c '
import json, sys
valor = json.loads(sys.argv[1])
for passo in sys.argv[2].split("."):
    if passo.startswith("@"):
        valor = list(valor)[int(passo[1:])]
    else:
        valor = valor[int(passo)] if isinstance(valor, list) else valor[passo]
print(valor if isinstance(valor, str) else json.dumps(valor, ensure_ascii=False))
' "$1" "$2"; }

TRACE=$(python3 -c 'import secrets; print(secrets.token_hex(16))')
a2a() { curl -sS -X POST http://localhost:7300/a2a -H 'Content-Type: application/json' \
  -H "traceparent: 00-$TRACE-00f067aa0ba902b7-01" -d "$1"; }
```

Os valores esperados abaixo seguem o estado acumulado de um servidor recém-iniciado.

**Passo 7 — Task pausada.** `SendMessage` de uma sala ocupada. Espera: `TASK_STATE_INPUT_REQUIRED` e `alternativas: sala-fusca, sala-mirante`.

```bash
R=$(a2a "$(corpo 08-a2a-send-message.json)")
TASK=$(campo "$R" result.task.id)
campo "$R" result.task.status.state
campo "$R" result.task.status.message.parts.0.text
```

**Passo 8 — continuar e conferir com `GetTask`.** Espera: `TASK_STATE_COMPLETED` nas duas respostas, artefato `reserva` com `sala-mirante` e o campo `politica`.

```bash
R=$(a2a "$(corpo 10-a2a-send-message-continuacao.json params.message.taskId=$TASK params.message.parts.0.text=escolha=sala-mirante)")
campo "$R" result.task.status.state
R=$(a2a "$(corpo 09-a2a-get-task-input-required.json params.id=$TASK)")
campo "$R" result.task.status.state
campo "$R" result.task.artifacts.0.name
campo "$R" result.task.artifacts.0.parts.0.text
```

**Passo 9 — recusa.** O mesmo pedido pausa de novo, agora só com `alternativas: sala-fusca` (a `sala-mirante` já foi reservada no passo 8), e a recusa termina a Task. Espera: `TASK_STATE_INPUT_REQUIRED` e depois `TASK_STATE_CANCELED`.

```bash
R=$(a2a "$(corpo 08-a2a-send-message.json)")
TASK=$(campo "$R" result.task.id)
campo "$R" result.task.status.message.parts.0.text
R=$(a2a "$(corpo 10-a2a-send-message-continuacao.json params.message.taskId=$TASK params.message.parts.0.text=escolha=recusar)")
campo "$R" result.task.status.state
```

**Passo 10 — sala inexistente.** Espera: `TASK_STATE_FAILED` e `Sala inexistente: sala-inexistente`.

```bash
R=$(a2a "$(corpo 08-a2a-send-message.json params.message.parts.0.text='reservar sala=sala-inexistente inicio=2026-11-03T14:00:00-03:00 fim=2026-11-03T15:00:00-03:00 responsavel=Marty')")
campo "$R" result.task.status.state
campo "$R" result.task.status.message.parts.0.text
```

**Passo 11 — `requestState` adulterado.** Pede o conflito direto ao servidor MCP, troca o último caractere do `requestState` e reenvia. Espera: HTTP `400` e erro JSON-RPC `-32602`.

```bash
R=$(curl -sS -X POST http://localhost:7301/mcp -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' -H 'MCP-Protocol-Version: 2026-07-28' \
  -H 'Mcp-Method: tools/call' -H 'Mcp-Name: reservar_sala' \
  -d "$(corpo 03-tools-call-conflito-input-required.json)")
CHAVE=$(campo "$R" result.inputRequests.@0)
ESTADO=$(campo "$R" result.requestState)
ALTERADO="${ESTADO%?}$([ "${ESTADO: -1}" = A ] && echo B || echo A)"
curl -sS -w '\nHTTP %{http_code}\n' -X POST http://localhost:7301/mcp -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' -H 'MCP-Protocol-Version: 2026-07-28' \
  -H 'Mcp-Method: tools/call' -H 'Mcp-Name: reservar_sala' \
  -d "$(corpo 04-tools-call-retry.json chave=$CHAVE params.requestState=$ALTERADO)"
```

A chave de `inputRequests` é a que o servidor atribui (`reservar_sala:escolha_de_sala`); os exemplos de `exemplos/wire/` mostram outra (`__main__:escolha_de_sala`), por isso o auxiliar a substitui pela viva.

*Extra (11b):* reenviar o `requestState` **intacto** mas com `arguments` editados também é rejeitado com `-32602`. Veja [Decisões técnicas](#decisões-técnicas).

```bash
curl -sS -w '\nHTTP %{http_code}\n' -X POST http://localhost:7301/mcp -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' -H 'MCP-Protocol-Version: 2026-07-28' \
  -H 'Mcp-Method: tools/call' -H 'Mcp-Name: reservar_sala' \
  -d "$(corpo 04-tools-call-retry.json chave=$CHAVE params.requestState=$ESTADO params.arguments.responsavel=Outro)"
```

**Passo 12 — o `requestState` sobrevive ao restart do servidor MCP.** Pede o conflito de novo, guarda o estado, **reinicia o servidor MCP com o mesmo segredo** e reenvia o estado intacto aceitando `sala-fusca`. Espera: `resultType: complete` e `reservado: true`.

```bash
R=$(curl -sS -X POST http://localhost:7301/mcp -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' -H 'MCP-Protocol-Version: 2026-07-28' \
  -H 'Mcp-Method: tools/call' -H 'Mcp-Name: reservar_sala' \
  -d "$(corpo 03-tools-call-conflito-input-required.json)")
CHAVE=$(campo "$R" result.inputRequests.@0)
ESTADO=$(campo "$R" result.requestState)
```

Agora, no terminal 1: Ctrl+C e suba o servidor de novo com o **mesmo** segredo (o `export` ainda vale nesse terminal, ou use `./subir-servidor-mcp.sh` com o `.env`). Depois, no terminal do Roteiro:

```bash
R=$(curl -sS -X POST http://localhost:7301/mcp -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' -H 'MCP-Protocol-Version: 2026-07-28' \
  -H 'Mcp-Method: tools/call' -H 'Mcp-Name: reservar_sala' \
  -d "$(corpo 04-tools-call-retry.json chave=$CHAVE params.requestState=$ESTADO)")
campo "$R" result.resultType
campo "$R" result.structuredContent.reservado
campo "$R" result.structuredContent.sala
```

**Passo 13 — cliente sem a capability de elicitation.** Espera: HTTP `400`, erro `-32021` e `data.requiredCapabilities`.

```bash
curl -sS -w '\nHTTP %{http_code}\n' -X POST http://localhost:7301/mcp -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' -H 'MCP-Protocol-Version: 2026-07-28' \
  -H 'Mcp-Method: tools/call' -H 'Mcp-Name: reservar_sala' \
  -d "$(corpo 06-erro-32021-sem-elicitation.json)"
```

**Conferir o `traceparent` (passo 5).** O trace-id usado pelas chamadas A2A acima aparece nas linhas `mcp ...` do terminal 1 (somente as emitidas antes do restart do passo 12):

```bash
echo "$TRACE"      # procure este valor no stderr do servidor MCP
```

## Onde a ponte acontece

O `input_required` do MCP vira `TASK_STATE_INPUT_REQUIRED` em [`pause_task`](agente/src/agente/skills/bridge.py#L70): o handler de `reservar_sala` (`agente/src/agente/skills/reservar_sala.py`) recebe o `InputRequired` de `McpClient.call_tool` e o entrega a `pause_for_choice`, que chama `pause_task`; essa função guarda o `PausedRecord` (com o `requestState`) no anexo privado da Task e move a Task para `TASK_STATE_INPUT_REQUIRED` com a mensagem `alternativas: ...`. Quando a escolha chega numa nova `SendMessage` com o `taskId`, o handler de continuação chama [`send_retry`](agente/src/agente/skills/bridge.py#L80), e o `requestState` guardado volta para o servidor por `McpClient.retry_tool` (`agente/src/agente/mcp_host/client.py`), que repete o `tools/call` com um novo id JSON-RPC, as `inputResponses` sob a chave recebida e o `requestState` sem nenhuma alteração.

## Decisões técnicas

- **Proteção do `requestState`.** O servidor usa o utilitário do SDK, `RequestStateSecurity(keys=[segredo], ttl=600)` (`servidor-mcp/src/servidor_mcp/seguranca.py`). A chave vem de `REQUEST_STATE_SECRET` (pelo menos 64 caracteres hexadecimais, 32 bytes) e o selo é **AEAD AES-256-GCM** com chave derivada por HKDF-SHA256. Não é HMAC literal, mas dá a mesma garantia de integridade que um HMAC daria (qualquer alteração é rejeitada com `-32602`) e ainda acrescenta confidencialidade: o conteúdo não é legível por quem o carrega. Sem segredo válido o servidor sai com código `1`.
- **Validade.** O estado vale **10 minutos** (TTL de 600 s). Depois disso o retry recebe `-32602` e a Task do agente termina em `TASK_STATE_FAILED` com mensagem iniciada por `Erro do servidor MCP: -32602`.
- **Estado autocontido.** O servidor MCP não guarda nada do pedido pausado: tudo viaja dentro do `requestState`. Por isso ele continua válido depois de um restart do servidor, desde que o segredo seja o mesmo (passo 12 do Roteiro).
- **Valores selados vencem.** No retry, o servidor reconstrói a reserva a partir do conteúdo selado (sala original, `inicio`, `fim`, `responsavel`, alternativas e chave) e ignora os `arguments` reenviados (`_retomar` em `servidor-mcp/src/servidor_mcp/primitives/reservar_sala.py`). Além disso, o envelope do SDK recusa o retry cujos `arguments` foram editados, mesmo com o `requestState` intacto: observado com `curl` (passo 11b), resposta HTTP `400` com `-32602 Invalid or expired requestState`.
- **Estado das Tasks na memória do agente.** As Tasks vivem na memória do processo do agente e se perdem se ele reiniciar. O registro da pausa (com o `requestState`) fica no anexo privado da Task, que é descartado em qualquer estado terminal; ele não é devolvido nas respostas A2A.
- **Cliente MCP próprio.** O agente usa um cliente `httpx` escrito à mão (`agente/src/agente/mcp_host/client.py`) em vez do `ClientSession` do SDK. O cliente do SDK responderia a elicitation por conta própria por um callback; aqui é preciso ver o `input_required` cru para pausar a Task. Um contador de ids JSON-RPC único no processo mantém os ids distintos entre chamadas e retries.
- **Descoberta em runtime.** Cada Task nova começa com `tools/list`; o agente só chama `reservar_sala` se ela foi anunciada e se o `inputSchema` anunciado aceita os argumentos do pedido (campos `required` presentes, nenhum campo fora de `properties`). Caso contrário a Task termina em `TASK_STATE_FAILED` sem chegar ao `tools/call`. É checagem de forma do protocolo, não regra de sala.
- **Rastreamento.** O `traceparent` recebido pelo agente é propagado a cada request MCP: o trace-id é herdado e cada chamada ganha um span-id novo. Uma Task pausada e retomada deixa quatro linhas `mcp` no stderr do servidor (`tools/list`, `resources/read` e dois `tools/call` com ids diferentes).
- **Determinismo.** O agente interpreta um pedido de formato fixo (`reservar sala=... inicio=... fim=... responsavel=...`) e a escolha (`escolha=<sala>` ou `escolha=recusar`) por regras; não há LLM em nenhum dos dois pacotes.
- **Dois processos, só HTTP.** O agente nunca importa `servidor_mcp`; as duas pontas só conversam por MCP sobre HTTP.

### Limitações do SDK

**Roteamento de era pelo cabeçalho `MCP-Protocol-Version`.** O SDK (`mcp==2.3.0`) decide a era do protocolo só pelo cabeçalho, antes de qualquer validação do corpo. Em `.venv/lib/python3.*/site-packages/mcp/server/streamable_http_manager.py` (no Windows, `.venv\Lib\site-packages\...`), linhas 192–197:

```python
header = MCP_PROTOCOL_VERSION_HEADER.encode("ascii")
pv = next((v.decode("latin-1") for k, v in scope["headers"] if k == header), None)
if pv is not None and pv not in HANDSHAKE_PROTOCOL_VERSIONS:
    await handle_modern_request(
        self.app, self.security_settings, self.json_response, self._lifespan_state, scope, receive, send
    )
    return
```

O comentário logo acima (linha 187) diz `TODO(L49): header-only era-routing for now`. Efeito observado com `curl` num `tools/list` (corpo do `exemplos/wire/01`): cabeçalho ausente, ou com uma versão da era do handshake (`2025-11-25`), cai no caminho legado do SDK e recebe **HTTP 200**, em vez de `-32020`; um valor desconhecido (`2099-01-01`) vai para o caminho moderno, é comparado com o corpo e recebe HTTP `400` com `-32020`. Divergência de `Mcp-Method` também recebe `-32020`, que é o que o critério exige. Não há contorno no código do servidor: a limitação fica documentada, não escondida.

O SDK também carimba sozinho `resultType` nas respostas e `serverInfo` no `_meta`; isso é comportamento, não limitação.

## Saída do validador

Execução de 2026-10-04 em Windows 11 com Python 3.14.4, a partir de um clone limpo do commit entregue, seguindo os comandos de "Como rodar" (ambiente virtual, `pip install -e`, segredo gerado e exportado, `python -m servidor_mcp`, `python -m agente`, valores padrão de porta e `MCP_URL`), com os dois processos recém-iniciados e código de saída `0`. A mesma sequência também passou nas 36 verificações com Python 3.12.13. A saída está colada sem cortes:

```text
trace-id desta execucao: 9e47382fb886b6a8070c1dae28a71f2f
procure esse valor no stderr do servidor MCP para conferir a propagacao do traceparent.

PASS 01 tools/list traz as tres tools
PASS 02 toda tool tem inputSchema de objeto
PASS 03 listar_salas devolve structuredContent e o mesmo JSON em texto
PASS 04 _meta sem protocolVersion devolve -32602 e HTTP 400
PASS 05 _meta sem clientCapabilities devolve -32602 e HTTP 400
PASS 06 tool inexistente e recusada, por -32602 ou por isError
PASS 07 resources/read de politica://uso devolve a politica
PASS 08 resources/read de URI inexistente devolve -32602
PASS 09 sala inexistente devolve isError com a mensagem exata
PASS 10 fora da janela devolve isError com a mensagem exata
PASS 11 duracao acima de 2h devolve isError com a mensagem exata
PASS 12 intervalo invertido devolve isError com a mensagem exata
PASS 13 conflito devolve input_required com inputRequests e requestState
PASS 14 a elicitation e form mode e oferece as alternativas na ordem certa
PASS 15 conflito sem a capability elicitation devolve -32021 e HTTP 400
PASS 16 retry com inputResponses e requestState conclui a reserva
PASS 17 requestState adulterado e rejeitado com -32602
PASS 18 argumentos adulterados no retry nao tomam efeito
PASS 19 recusa conclui sem reservar e sem isError
PASS 20 conflito sem alternativa possivel devolve isError com a mensagem exata

PASS 21 agent card responde 200 no well-known com JSON
PASS 22 o card declara a interface JSON-RPC com url e versao 1.0
PASS 23 o card declara a skill reservar-sala
PASS 24 SendMessage com sala livre conclui a Task
PASS 25 o artifact chama reserva e traz a versao da politica
PASS 26 GetTask devolve id, contextId e estado corrente
PASS 27 SendMessage com sala ocupada pausa a Task
PASS 28 a Task pausada lista as alternativas na ordem certa
PASS 29 escolha fora do enum mantem a Task pausada
PASS 30 a continuacao conclui a Task na sala escolhida
PASS 31 SendMessage em Task terminal e recusado
PASS 32 a recusa termina a Task em CANCELED
PASS 33 duas Tasks pausadas ao mesmo tempo concluem cada uma com a sua reserva
PASS 34 nenhuma resposta A2A carrega o requestState
PASS 35 sala inexistente termina a Task em FAILED com a mensagem da tool
PASS 36 o agente e deterministico: o mesmo pedido produz a mesma pausa

resumo: 36 passaram, 0 falharam, de 36 verificacoes
```
