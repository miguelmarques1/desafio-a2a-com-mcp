import asyncio
import json

import pytest
from mcp.server.mcpserver.exceptions import ResourceNotFoundError

from servidor_mcp.loader import load_dominio
from servidor_mcp.primitives import REGISTRARS, catalogo
from servidor_mcp.server import build_server

POLITICA = "politica://uso"


def make_server(dominio):
    return build_server(dominio, registrars=(catalogo.register,))


@pytest.fixture
def dominio(repo_root):
    return load_dominio(repo_root / "dados")


def run(coro):
    return asyncio.run(coro)



def test_register_adds_one_tool_and_one_resource(dominio):
    server = make_server(dominio)
    assert [t.name for t in run(server.list_tools())] == ["listar_salas"]
    assert [str(r.uri) for r in run(server.list_resources())] == [POLITICA]
    assert run(server.list_resource_templates()) == []


def test_output_schema_shape(dominio):
    (tool,) = run(make_server(dominio).list_tools())
    schema = tool.output_schema
    assert schema["title"] == "ListaDeSalas"
    assert schema["required"] == ["salas"]
    sala = schema["$defs"]["SalaOut"]
    assert sala["required"] == ["id", "nome", "capacidade", "recursos"]
    props = sala["properties"]
    assert [props[k]["type"] for k in ("id", "nome", "capacidade", "recursos")] == [
        "string", "string", "integer", "array",
    ]
    assert props["recursos"]["items"] == {"type": "string"}


def call(server, arguments=None):
    return run(server.call_tool("listar_salas", arguments or {}))


def test_listar_salas_returns_rooms_in_file_order(dominio):
    result = call(make_server(dominio))
    salas = result.structured_content["salas"]
    assert [s["id"] for s in salas] == [
        "sala-aquario", "sala-porao", "sala-garagem", "sala-fusca", "sala-mirante",
    ]
    assert [s["capacidade"] for s in salas] == [4, 6, 12, 12, 20]
    assert salas == [s.as_dict() for s in dominio.catalogo]


def test_listar_salas_has_single_text_block_equal_to_structured_content(dominio):
    result = call(make_server(dominio))
    assert not result.is_error
    assert len(result.content) == 1 and result.content[0].type == "text"
    assert json.loads(result.content[0].text) == result.structured_content


def _rewrite_salas(dados_tmp, salas):
    (dados_tmp / "salas.json").write_text(json.dumps(salas), encoding="utf-8")


def test_listar_salas_reflects_the_injected_dominio(dados_tmp):
    original = json.loads((dados_tmp / "salas.json").read_text(encoding="utf-8"))
    salas = original["salas"] if isinstance(original, dict) else original
    novas = [salas[4], salas[0], salas[2]]
    _rewrite_salas(dados_tmp, {"salas": novas} if isinstance(original, dict) else novas)
    result = call(make_server(load_dominio(dados_tmp)))
    assert result.structured_content["salas"] == novas


def test_register_keeps_no_module_level_state(repo_root, dados_tmp):
    (dados_tmp / "politica-de-uso.md").write_text("versao: 1999-01-01\n\nx\n", encoding="utf-8", newline="")
    base, outro = load_dominio(repo_root / "dados"), load_dominio(dados_tmp)
    s1, s2 = make_server(base), make_server(outro)
    assert run(s1.read_resource(POLITICA))[0].content == base.politica.texto
    assert run(s2.read_resource(POLITICA))[0].content == "versao: 1999-01-01\n\nx\n"
    assert call(s1).structured_content == call(s2).structured_content


def test_listar_salas_does_not_mutate_dominio(dominio):
    antes = [s.as_dict() for s in dominio.catalogo]
    server = make_server(dominio)
    call(server)
    call(server)
    assert [s.as_dict() for s in dominio.catalogo] == antes
    assert len(dominio.reservas) == 2


def test_politica_resource_returns_dominio_text_as_markdown(dominio):
    items = run(make_server(dominio).read_resource(POLITICA))
    assert len(items) == 1
    assert items[0].content == dominio.politica.texto
    assert items[0].mime_type == "text/markdown"


@pytest.mark.parametrize("eol", ["\n", "\r\n"])
def test_politica_text_is_byte_identical_for_lf_and_crlf_files(dados_tmp, eol):
    conteudo = f"versao: 2026-11-01{eol}{eol}- regra um{eol}"
    arquivo = dados_tmp / "politica-de-uso.md"
    arquivo.write_bytes(conteudo.encode("utf-8"))
    items = run(make_server(load_dominio(dados_tmp)).read_resource(POLITICA))
    assert items[0].content.encode("utf-8") == arquivo.read_bytes()


@pytest.mark.parametrize(
    "uri",
    ["politica://inexistente", "politica://uso/", "politica://USO", "POLITICA://uso", "politica:uso"],
)
def test_unknown_uri_raises_resource_not_found(dominio, uri):
    with pytest.raises(ResourceNotFoundError):
        run(make_server(dominio).read_resource(uri))


def test_registry_places_catalogo_first():
    assert REGISTRARS[0] is catalogo.register
