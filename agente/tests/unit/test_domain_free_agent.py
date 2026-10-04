import re
from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / "src" / "agente"
DOMAIN_IDENTIFIERS = (
    "capacidade",
    "datetime",
    "timedelta",
    "fromisoformat",
    "08:00",
    "20:00",
    "salas.json",
    "reservas.json",
)
SERVER_IMPORT = re.compile(r"^\s*(from|import)\s+servidor_mcp")


def scan(predicate):
    hits = []
    for path in sorted(SRC.rglob("*.py")):
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if predicate(line):
                hits.append(f"{path.relative_to(SRC)}:{number}: {line.strip()}")
    return hits


def test_agent_source_has_no_domain_rules():
    assert SRC.is_dir()
    hits = scan(lambda line: any(word in line for word in DOMAIN_IDENTIFIERS))
    assert hits == []


def test_agent_does_not_import_server_code():
    assert scan(lambda line: SERVER_IMPORT.match(line) is not None) == []
