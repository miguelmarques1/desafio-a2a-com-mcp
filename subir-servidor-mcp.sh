#!/usr/bin/env bash
# Sobe o servidor MCP (porta 7301 por padrao).
# Ativa o .venv da raiz, carrega o .env (sem sobrescrever variaveis ja
# exportadas) e inicia o processo em primeiro plano.
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")"

if [ -f .venv/bin/activate ]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
elif [ -f .venv/Scripts/activate ]; then
  # shellcheck disable=SC1091
  source .venv/Scripts/activate
else
  echo 'Ambiente virtual .venv nao encontrado. Siga "Como rodar" no README.' >&2
  exit 1
fi

recortar() {
  local s="$1"
  s="${s#"${s%%[![:space:]]*}"}"
  s="${s%"${s##*[![:space:]]}"}"
  printf '%s' "$s"
}

if [ -f .env ]; then
  while IFS= read -r linha || [ -n "$linha" ]; do
    linha="$(recortar "${linha%$'\r'}")"
    case "$linha" in
      '' | '#'*) continue ;;
      *=*) ;;
      *) continue ;;
    esac
    chave="$(recortar "${linha%%=*}")"
    valor="$(recortar "${linha#*=}")"
    [[ "$chave" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]] || continue
    if [ "${#valor}" -ge 2 ]; then
      primeiro="${valor:0:1}"
      ultimo="${valor: -1}"
      if [ "$primeiro" = "$ultimo" ] && { [ "$primeiro" = '"' ] || [ "$primeiro" = "'" ]; }; then
        valor="${valor:1:${#valor}-2}"
      fi
    fi
    if [ -z "${!chave+x}" ]; then
      export "$chave=$valor"
    fi
  done < .env
fi

exec python -m servidor_mcp
