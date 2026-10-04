# Sobe o servidor MCP (porta 7301 por padrao).
# Ativa o .venv da raiz, carrega o .env (sem sobrescrever variaveis ja
# definidas) e inicia o processo em primeiro plano.
$ErrorActionPreference = 'Stop'

Set-Location -LiteralPath $PSScriptRoot

$ativar = Join-Path $PSScriptRoot '.venv\Scripts\Activate.ps1'
if (-not (Test-Path -LiteralPath $ativar)) {
    [Console]::Error.WriteLine('Ambiente virtual .venv nao encontrado. Siga "Como rodar" no README.')
    exit 1
}
. $ativar

$arquivoEnv = Join-Path $PSScriptRoot '.env'
if (Test-Path -LiteralPath $arquivoEnv) {
    foreach ($linha in Get-Content -LiteralPath $arquivoEnv) {
        $linha = $linha.Trim()
        if ($linha -eq '' -or $linha.StartsWith('#') -or -not $linha.Contains('=')) { continue }
        $indice = $linha.IndexOf('=')
        $chave = $linha.Substring(0, $indice).Trim()
        $valor = $linha.Substring($indice + 1).Trim()
        if ($chave -notmatch '^[A-Za-z_][A-Za-z0-9_]*$') { continue }
        if ($valor.Length -ge 2) {
            $primeiro = $valor.Substring(0, 1)
            $ultimo = $valor.Substring($valor.Length - 1)
            if ($primeiro -eq $ultimo -and ($primeiro -eq '"' -or $primeiro -eq "'")) {
                $valor = $valor.Substring(1, $valor.Length - 2)
            }
        }
        $caminhoEnv = 'Env:' + $chave
        if (-not (Test-Path -LiteralPath $caminhoEnv)) {
            Set-Item -LiteralPath $caminhoEnv -Value $valor
        }
    }
}

& python -m servidor_mcp
exit $LASTEXITCODE
