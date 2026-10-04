from mcp.types import TextContent

from servidor_mcp.resultados import erro_de_execucao


def test_erro_de_execucao_builds_single_text_block():
    r = erro_de_execucao("Sala inexistente: x")
    assert r.is_error is True
    assert len(r.content) == 1 and isinstance(r.content[0], TextContent)
    assert r.content[0].text == "Sala inexistente: x"
    assert r.structured_content is None


def test_erro_de_execucao_keeps_text_verbatim():
    texto = "Horario invalido: {x}\n  çã"
    assert erro_de_execucao(texto).content[0].text == texto
