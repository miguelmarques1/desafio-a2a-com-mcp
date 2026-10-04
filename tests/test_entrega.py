"""Static delivery checks (F10): README, helper scripts, secrets, pins and starter assets.

Stdlib + pytest only. Nothing here imports `servidor_mcp` or `agente`.
Run from the repo root: `python -m pytest tests`.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
STARTER_COMMIT = "263f17e202fd861d14aa7a5e6a539d13a62857c3"
STARTER_DIRS = ("dados", "validador", "exemplos")
PYPROJECTS = (ROOT / "servidor-mcp" / "pyproject.toml", ROOT / "agente" / "pyproject.toml")
SCRIPTS_SH = ("subir-servidor-mcp.sh", "subir-agente.sh")
SCRIPTS_PS1 = ("subir-servidor-mcp.ps1", "subir-agente.ps1")
VALIDATOR_COMMAND = "python3 validador/validar.py --agente http://localhost:7300 --mcp http://localhost:7301"
REQUIRED_SECTIONS = ("Como rodar", "Onde a ponte acontece", "Decisões técnicas", "Saída do validador")

HEX_RUN = re.compile(r"[0-9a-fA-F]{64,}")
SECRET_ASSIGNMENT = re.compile(r"REQUEST_STATE_SECRET[ \t]*=[ \t]*(\S[^\n]*)")
SECRET_VALUE_OK_MARKERS = ("$(", "<", "(python", "secrets.token_hex")
PINNED = re.compile(r"^[A-Za-z0-9_.\-]+(\[[A-Za-z0-9_,\-]+\])?==[^=<>!~;\s]+$")
LLM_DENY_EXACT = {
    "openai",
    "anthropic",
    "google-genai",
    "google-generativeai",
    "mistralai",
    "cohere",
    "ollama",
    "litellm",
    "groq",
    "transformers",
}
LLM_DENY_PREFIX = ("langchain", "llama-index")


def _git(*args: str) -> subprocess.CompletedProcess[str] | None:
    try:
        return subprocess.run(
            ["git", *args], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", check=False
        )
    except (FileNotFoundError, OSError):
        return None


def _require_git() -> None:
    result = _git("rev-parse", "--is-inside-work-tree")
    if result is None or result.returncode != 0:
        pytest.skip("git indisponivel ou fora de um repositorio")


def _readme() -> str:
    return README.read_text(encoding="utf-8")


def _sections(text: str) -> dict[str, str]:
    """Split on `## ` headings, ignoring lines inside fenced code blocks."""
    sections: dict[str, list[str]] = {}
    current: str | None = None
    in_fence = False
    for line in text.splitlines():
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
        if not in_fence and line.startswith("## "):
            current = line[3:].strip()
            sections[current] = []
        elif current is not None:
            sections[current].append(line)
    return {name: "\n".join(lines) for name, lines in sections.items()}


def _headings(text: str) -> list[str]:
    headings: list[str] = []
    in_fence = False
    for line in text.splitlines():
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
        elif not in_fence and line.startswith("## "):
            headings.append(line[3:].strip())
    return headings


def _requirement_strings(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    if sys.version_info >= (3, 11):
        import tomllib

        data = tomllib.loads(text)
        requirements = list(data.get("project", {}).get("dependencies", []))
        for extra in data.get("project", {}).get("optional-dependencies", {}).values():
            requirements.extend(extra)
        requirements.extend(data.get("build-system", {}).get("requires", []))
        return requirements
    requirements = []
    for key in ("dependencies", "dev", "requires"):
        for block in re.finditer(rf"^{key}\s*=\s*\[(.*?)\]", text, re.DOTALL | re.MULTILINE):
            requirements.extend(re.findall(r'"([^"]+)"', block.group(1)))
    return requirements


def _requirement_name(requirement: str) -> str:
    match = re.match(r"[A-Za-z0-9_.\-]+", requirement.strip())
    assert match, requirement
    return match.group(0).lower().replace("_", "-")


def test_readme_has_required_sections() -> None:
    headings = _headings(_readme())
    positions = []
    for section in REQUIRED_SECTIONS:
        assert section in headings, f"secao ausente: {section}"
        positions.append(headings.index(section))
    assert positions == sorted(positions), "secoes fora da ordem"


def test_readme_does_not_keep_starter_text() -> None:
    headings = _headings(_readme())
    assert not any("Critérios de Aceite" in h or "Fluxo do avaliador" in h for h in headings)


def test_como_rodar_has_required_commands() -> None:
    section = _sections(_readme())["Como rodar"]
    for needle in (
        "python3 -m venv .venv",
        "pip install -e ./servidor-mcp",
        "-e ./agente",
        "secrets.token_hex(32)",
        "REQUEST_STATE_SECRET",
        "python -m servidor_mcp",
        "python -m agente",
        VALIDATOR_COMMAND,
    ):
        assert needle in section, f"comando ausente em 'Como rodar': {needle}"


def test_como_rodar_documents_env_vars() -> None:
    section = _sections(_readme())["Como rodar"]
    for needle in ("MCP_PORT", "7301", "AGENT_PORT", "7300", "MCP_URL", "AGENT_PUBLIC_URL"):
        assert needle in section, f"variavel/valor ausente: {needle}"


def test_bridge_anchors_point_at_named_functions() -> None:
    section = _sections(_readme())["Onde a ponte acontece"]
    anchors = re.findall(r"agente/src/agente/skills/bridge\.py#L(\d+)", section)
    assert len(anchors) == 2, anchors
    lines = (ROOT / "agente" / "src" / "agente" / "skills" / "bridge.py").read_text(encoding="utf-8").splitlines()
    pause_line, retry_line = (lines[int(n) - 1] for n in anchors)
    assert pause_line.startswith("def pause_task"), pause_line
    assert retry_line.startswith("async def send_retry"), retry_line


def test_decisoes_tecnicas_states_required_facts() -> None:
    section = _sections(_readme())["Decisões técnicas"]
    for needle in ("REQUEST_STATE_SECRET", "AES-256-GCM", "HMAC", "10 minutos", "memória", "Limitações do SDK"):
        assert needle in section, f"fato ausente em 'Decisões técnicas': {needle}"


def test_validator_output_is_a_full_passing_run() -> None:
    section = _sections(_readme())["Saída do validador"]
    block = re.search(r"```text\n(.*?)\n```", section, re.DOTALL)
    assert block, "bloco de saida do validador ausente"
    output = block.group(1)
    assert re.search(r"trace-id desta execucao: [0-9a-f]{32}", output)
    for n in range(1, 37):
        assert len(re.findall(rf"^PASS {n:02d} ", output, re.MULTILINE)) == 1, f"PASS {n:02d}"
    assert not re.search(r"^FAIL ", output, re.MULTILINE)
    assert "resumo: 36 passaram, 0 falharam, de 36 verificacoes" in output


def _tracked_files() -> list[str]:
    _require_git()
    result = _git("ls-files")
    assert result is not None and result.returncode == 0
    return [
        f
        for f in result.stdout.splitlines()
        if f and not f.startswith(tuple(f"{d}/" for d in STARTER_DIRS)) and (ROOT / f).is_file()
    ]


def test_no_secret_in_tracked_files() -> None:
    offenders: list[str] = []
    for name in _tracked_files():
        try:
            text = (ROOT / name).read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if HEX_RUN.search(text):
            offenders.append(f"{name}: sequencia hexadecimal de 64+ caracteres")
        for match in SECRET_ASSIGNMENT.finditer(text):
            value = match.group(1)
            if value.startswith("`"):  # prose: `REQUEST_STATE_SECRET=` closes an inline code span
                continue
            if not any(marker in value for marker in SECRET_VALUE_OK_MARKERS):
                offenders.append(f"{name}: REQUEST_STATE_SECRET com valor literal")
    assert not offenders, offenders


def test_env_is_gitignored_and_example_is_tracked() -> None:
    _require_git()
    ignored = _git("check-ignore", "-q", ".env")
    assert ignored is not None and ignored.returncode == 0, ".env deveria estar no .gitignore"
    tracked = _git("ls-files", "--", ".env", ".env.example")
    assert tracked is not None
    assert tracked.stdout.split() == [".env.example"]


def test_env_example_secret_is_empty() -> None:
    lines = (ROOT / ".env.example").read_text(encoding="utf-8").splitlines()
    secret = [line for line in lines if line.startswith("REQUEST_STATE_SECRET")]
    assert secret == ["REQUEST_STATE_SECRET="]
    active = [line for line in lines if line.strip() and not line.lstrip().startswith("#")]
    assert active == ["REQUEST_STATE_SECRET="], "padroes devem ficar comentados"


def test_dependencies_are_pinned() -> None:
    for path in PYPROJECTS:
        requirements = _requirement_strings(path)
        assert requirements, path
        for requirement in requirements:
            assert PINNED.match(requirement), f"{path.parent.name}: {requirement} sem pin com =="


def test_no_llm_provider_sdk() -> None:
    for path in PYPROJECTS:
        for requirement in _requirement_strings(path):
            name = _requirement_name(requirement)
            assert name not in LLM_DENY_EXACT, f"{path.parent.name}: SDK de LLM {name}"
            assert not name.startswith(LLM_DENY_PREFIX), f"{path.parent.name}: SDK de LLM {name}"


def test_starter_dirs_unchanged() -> None:
    _require_git()
    known = _git("cat-file", "-e", f"{STARTER_COMMIT}^{{commit}}")
    if known is None or known.returncode != 0:
        pytest.skip("commit do starter ausente (clone raso?)")
    diff = _git("diff", "--quiet", STARTER_COMMIT, "--", *STARTER_DIRS)
    assert diff is not None and diff.returncode == 0, "dados/, validador/ ou exemplos/ mudaram"
    status = _git("status", "--porcelain", "--", *STARTER_DIRS)
    assert status is not None and status.stdout.strip() == ""


def test_scripts_exist_with_lf_and_exec_bit() -> None:
    for name in SCRIPTS_SH + SCRIPTS_PS1:
        assert (ROOT / name).is_file(), name
    for name in SCRIPTS_SH:
        data = (ROOT / name).read_bytes()
        assert b"\r" not in data, f"{name} com CRLF"
        assert data.startswith(b"#!/usr/bin/env bash\n"), name
    _require_git()
    staged = _git("ls-files", "-s", "--", *SCRIPTS_SH)
    assert staged is not None
    modes = {line.split()[-1]: line.split()[0] for line in staged.stdout.splitlines()}
    for name in SCRIPTS_SH:
        assert modes.get(name) == "100755", f"{name}: modo {modes.get(name)}"


def test_scripts_do_not_generate_or_embed_secrets() -> None:
    for name in SCRIPTS_SH + SCRIPTS_PS1:
        text = (ROOT / name).read_text(encoding="utf-8")
        assert "token_hex" not in text, name
        assert not HEX_RUN.search(text), name
        assert not re.search(r">>?\s*['\"]?\.env", text), f"{name} escreve no .env"
        assert not re.search(r"(Set-Content|Add-Content|Out-File)[^\n]*\.env", text), f"{name} escreve no .env"
