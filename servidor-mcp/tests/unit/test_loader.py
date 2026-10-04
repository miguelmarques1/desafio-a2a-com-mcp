import hashlib
import os
import stat
import sys

import pytest

from servidor_mcp.loader import DataLoadError, PolicyVersionMissingError, load_dominio

ARQUIVOS = ["salas.json", "reservas.json", "politica-de-uso.md"]


def test_loads_five_rooms_in_file_order(repo_root):
    d = load_dominio(repo_root / "dados")
    assert [s.id for s in d.catalogo] == [
        "sala-aquario", "sala-porao", "sala-garagem", "sala-fusca", "sala-mirante"
    ]
    assert [s.capacidade for s in d.catalogo] == [4, 6, 12, 12, 20]
    assert d.catalogo.get("sala-mirante").recursos == ("tv", "quadro", "camera")


def test_loads_two_seeded_reservations_verbatim(repo_root):
    d = load_dominio(repo_root / "dados")
    r = d.reservas.todas()
    assert [x.id for x in r] == ["res-0001", "res-0002"]
    assert r[0].as_dict() == {
        "id": "res-0001", "sala": "sala-garagem",
        "inicio": "2026-11-03T14:00:00-03:00", "fim": "2026-11-03T15:00:00-03:00",
        "responsavel": "Marty",
    }


def test_policy_text_is_byte_identical_to_file(repo_root):
    d = load_dominio(repo_root / "dados")
    assert d.politica.texto.encode("utf-8") == (repo_root / "dados" / "politica-de-uso.md").read_bytes()


def test_policy_version_parsed_from_first_line(repo_root):
    assert load_dominio(repo_root / "dados").politica.versao == "2026-11-01"


@pytest.mark.parametrize("arquivo", ARQUIVOS)
def test_missing_file_reports_file_and_reason(dados_tmp, arquivo):
    (dados_tmp / arquivo).unlink()
    with pytest.raises(DataLoadError) as exc:
        load_dominio(dados_tmp)
    assert str(exc.value).startswith(f"Falha ao carregar dados/: {arquivo}")


@pytest.mark.skipif(
    sys.platform == "win32" or (hasattr(os, "geteuid") and os.geteuid() == 0),
    reason="chmod 000 not effective on Windows or as root",
)
def test_unreadable_file_reports_reason(dados_tmp):
    alvo = dados_tmp / "salas.json"
    alvo.chmod(0)
    try:
        with pytest.raises(DataLoadError) as exc:
            load_dominio(dados_tmp)
    finally:
        alvo.chmod(stat.S_IRUSR | stat.S_IWUSR)
    assert str(exc.value).startswith("Falha ao carregar dados/: salas.json ")
    assert "Permission denied" in str(exc.value)


def test_invalid_json_reports_reason(dados_tmp):
    (dados_tmp / "reservas.json").write_text('[{"id": "res-1"', encoding="utf-8")
    with pytest.raises(DataLoadError) as exc:
        load_dominio(dados_tmp)
    assert str(exc.value).startswith("Falha ao carregar dados/: reservas.json JSON invalido")


def test_non_utf8_reports_reason(dados_tmp):
    (dados_tmp / "salas.json").write_bytes(b"\xff\xfe[]")
    with pytest.raises(DataLoadError) as exc:
        load_dominio(dados_tmp)
    assert "nao esta em UTF-8" in str(exc.value)


SALA_OK = {"id": "a", "nome": "A", "capacidade": 2, "recursos": []}


@pytest.mark.parametrize(
    "conteudo",
    [
        '[{"id": "a", "nome": "A", "capacidade": "4", "recursos": []}]',
        '[{"id": "a", "nome": "A", "capacidade": true, "recursos": []}]',
        '[{"id": "a", "nome": "A", "capacidade": 4, "recursos": []},'
        ' {"id": "a", "nome": "B", "capacidade": 4, "recursos": []}]',
        '{"id": "a"}',
    ],
)
def test_wrong_shape_reports_reason_salas(dados_tmp, conteudo):
    (dados_tmp / "salas.json").write_text(conteudo, encoding="utf-8")
    with pytest.raises(DataLoadError) as exc:
        load_dominio(dados_tmp)
    assert "formato invalido" in str(exc.value) and "salas.json" in str(exc.value)


@pytest.mark.parametrize(
    "conteudo",
    [
        '[{"id": "r", "sala": "a", "inicio": "x", "fim": "y", "responsavel": "z"},'
        ' {"id": "r", "sala": "a", "inicio": "x", "fim": "y", "responsavel": "z"}]',
        '{"id": "r"}',
        '[{"id": "r", "sala": "a"}]',
    ],
)
def test_wrong_shape_reports_reason_reservas(dados_tmp, conteudo):
    (dados_tmp / "reservas.json").write_text(conteudo, encoding="utf-8")
    with pytest.raises(DataLoadError) as exc:
        load_dominio(dados_tmp)
    assert "formato invalido" in str(exc.value) and "reservas.json" in str(exc.value)


@pytest.mark.parametrize(
    "texto",
    ["", "\nversao: 1\n", "Versao: x\n", "versao:\n", "versao:   \n", "x\nversao: 1\n"],
)
def test_policy_without_version_raises(dados_tmp, texto):
    (dados_tmp / "politica-de-uso.md").write_bytes(texto.encode("utf-8"))
    with pytest.raises(PolicyVersionMissingError) as exc:
        load_dominio(dados_tmp)
    assert str(exc.value) == "Politica de uso sem versao declarada"


def test_policy_version_is_trimmed_and_crlf_tolerant(dados_tmp):
    texto = "versao:   2026-11-01  \r\n- regra\r\n"
    (dados_tmp / "politica-de-uso.md").write_bytes(texto.encode("utf-8"))
    d = load_dominio(dados_tmp)
    assert d.politica.versao == "2026-11-01"
    assert d.politica.texto == texto


def test_load_order_first_failure_wins(dados_tmp):
    (dados_tmp / "salas.json").write_text("nao json", encoding="utf-8")
    (dados_tmp / "politica-de-uso.md").write_text("sem versao", encoding="utf-8")
    with pytest.raises(DataLoadError) as exc:
        load_dominio(dados_tmp)
    assert exc.value.arquivo == "salas.json"


def test_loader_does_not_modify_files(repo_root):
    def snap():
        return {
            n: (hashlib.sha256((repo_root / "dados" / n).read_bytes()).hexdigest(),
                (repo_root / "dados" / n).stat().st_mtime_ns)
            for n in ARQUIVOS
        }

    antes = snap()
    load_dominio(repo_root / "dados")
    assert snap() == antes
