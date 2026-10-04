import json
import secrets
import time

import pytest

from servidor_mcp.dominio import Reserva
from servidor_mcp.primitives import reservar_sala as modulo_reservar_sala
from servidor_mcp.seguranca import politica_de_estado

TOOL = "reservar_sala"
CHAVE = "reservar_sala:escolha_de_sala"
SEM_ALTERNATIVAS = "Sem alternativas disponiveis no intervalo"


def h(hora, dia="2026-11-03"):
    return f"{dia}T{hora}:00-03:00"


def argumentos(sala, inicio, fim, responsavel="Doc"):
    return {"sala": sala, "inicio": inicio, "fim": fim, "responsavel": responsavel}


def reservar(client, mcp_post, sala, inicio, fim, responsavel="Doc", **options):
    options.setdefault("id", secrets.token_hex(6))
    return mcp_post(
        client, "tools/call", {"name": TOOL, "arguments": argumentos(sala, inicio, fim, responsavel)}, **options
    )


def retomar(client, mcp_post, args, chave, resposta, estado, **options):
    options.setdefault("id", secrets.token_hex(6))
    params = {"name": TOOL, "arguments": args, "requestState": estado}
    if resposta is not None:
        params["inputResponses"] = {chave: resposta}
    return mcp_post(client, "tools/call", params, **options)


def chave_e_estado(result):
    (chave,) = result["inputRequests"]
    return chave, result["requestState"]


def aceitar(sala):
    return {"action": "accept", "content": {"sala": sala}}


def conflito_garagem(client, mcp_post, responsavel="Marty", **options):
    args = argumentos("sala-garagem", h("14:00"), h("15:00"), responsavel)
    r = reservar(client, mcp_post, **args, **options)
    assert r.status_code == 200
    chave, estado = chave_e_estado(r.json()["result"])
    return args, chave, estado, r.json()["result"]


def enum_de(result):
    return result["inputRequests"][CHAVE]["params"]["requestedSchema"]["properties"]["sala"]["enum"]


def erro(r):
    return r.json()["error"]


def wire(repo_root, name):
    return json.loads((repo_root / "exemplos" / "wire" / name).read_text(encoding="utf-8"))


def test_conflict_returns_input_required_matching_wire_capture(fresh_app, mcp_post, repo_root):
    client, _, _ = fresh_app()
    captured = wire(repo_root, "03-tools-call-conflito-input-required.json")
    r = client.post("/mcp", json=captured["request"]["body"], headers=captured["request"]["headers"])
    assert r.status_code == 200
    result = r.json()["result"]
    assert result["resultType"] == "input_required"
    assert "content" not in result and "structuredContent" not in result and "isError" not in result
    (chave, pedido) = next(iter(result["inputRequests"].items()))
    assert len(result["inputRequests"]) == 1 and chave == CHAVE
    (capturado,) = captured["response"]["body"]["result"]["inputRequests"].values()
    assert pedido == capturado
    assert result["requestState"].startswith("v1.")


def test_enum_is_fusca_then_mirante(fresh_app, mcp_post):
    client, _, _ = fresh_app()
    *_, result = conflito_garagem(client, mcp_post)
    esquema = result["inputRequests"][CHAVE]["params"]["requestedSchema"]
    assert list(esquema["properties"]) == ["sala"]
    assert esquema["properties"]["sala"]["type"] == "string"
    assert enum_de(result) == ["sala-fusca", "sala-mirante"]
    assert esquema["required"] == ["sala"]


def test_retry_accept_books_chosen_room_with_sealed_values(fresh_app, mcp_post):
    client, _, dominio = fresh_app()
    args, chave, estado, _ = conflito_garagem(client, mcp_post)
    r = retomar(client, mcp_post, args, chave, aceitar("sala-fusca"), estado)
    assert r.status_code == 200
    result = r.json()["result"]
    assert result["resultType"] == "complete" and result["isError"] is False
    sc = result["structuredContent"]
    assert (sc["sala"], sc["reserva"], sc["reservado"]) == ("sala-fusca", "res-0003", True)
    assert (sc["inicio"], sc["fim"], sc["responsavel"]) == (h("14:00"), h("15:00"), "Marty")
    assert sc["politica"] == "2026-11-01" and sc["motivo"] is None
    assert json.loads(result["content"][0]["text"]) == sc
    assert len(dominio.reservas) == 3


def test_validator_check_16_fusca_conflict_accept_garagem(fresh_app, mcp_post):
    client, _, _ = fresh_app()
    args = argumentos("sala-fusca", h("16:00"), h("17:00"), "Jennifer")
    r = reservar(client, mcp_post, **args)
    chave, estado = chave_e_estado(r.json()["result"])
    r2 = retomar(client, mcp_post, args, chave, aceitar("sala-garagem"), estado)
    result = r2.json()["result"]
    assert result["resultType"] == "complete" and result["isError"] is False
    assert result["structuredContent"]["sala"] == "sala-garagem"


def test_retry_with_new_id_is_logged_twice_with_different_ids(fresh_app, mcp_post):
    client, log_lines, _ = fresh_app()
    args, chave, estado, _ = conflito_garagem(client, mcp_post, id="a1")
    retomar(client, mcp_post, args, chave, aceitar("sala-fusca"), estado, id="b2")
    linhas = [ln for ln in log_lines() if "method=tools/call" in ln and "name=reservar_sala" in ln]
    assert [ln.split()[2] for ln in linhas] == ["id=a1", "id=b2"]


def decline_setup(client, mcp_post):
    args = argumentos("sala-fusca", h("16:00"), h("17:00"), "Jennifer")
    r = reservar(client, mcp_post, **args)
    chave, estado = chave_e_estado(r.json()["result"])
    return args, chave, estado


def test_decline_returns_recusado_and_matches_wire_11(fresh_app, mcp_post, repo_root):
    client, _, dominio = fresh_app()
    args, chave, estado = decline_setup(client, mcp_post)
    r = retomar(client, mcp_post, args, chave, {"action": "decline"}, estado)
    assert r.status_code == 200
    result = r.json()["result"]
    esperado = wire(repo_root, "11-tools-call-retry-recusa.json")["response"]["body"]["result"]
    assert result["structuredContent"] == esperado["structuredContent"]
    assert result["content"] == esperado["content"]
    assert result["isError"] is False and result["resultType"] == "complete"
    assert len(dominio.reservas) == 2


def test_cancel_returns_cancelado(fresh_app, mcp_post):
    client, _, _ = fresh_app()
    args, chave, estado = decline_setup(client, mcp_post)
    sc = retomar(client, mcp_post, args, chave, {"action": "cancel"}, estado).json()["result"]["structuredContent"]
    assert sc == {
        "reserva": None, "reservado": False, "sala": None, "inicio": None,
        "fim": None, "responsavel": None, "politica": None, "motivo": "cancelado",
    }


def test_decline_replay_is_idempotent(fresh_app, mcp_post):
    client, _, dominio = fresh_app()
    args, chave, estado = decline_setup(client, mcp_post)
    primeira = retomar(client, mcp_post, args, chave, {"action": "decline"}, estado).json()["result"]
    segunda = retomar(client, mcp_post, args, chave, {"action": "decline"}, estado).json()["result"]
    assert primeira == segunda
    assert len(dominio.reservas) == 2


def test_accept_replay_cannot_double_book(fresh_app, mcp_post):
    client, _, dominio = fresh_app()
    args, chave, estado, _ = conflito_garagem(client, mcp_post)
    primeira = retomar(client, mcp_post, args, chave, aceitar("sala-fusca"), estado).json()["result"]
    assert primeira["structuredContent"]["reserva"] == "res-0003"
    segunda = retomar(client, mcp_post, args, chave, aceitar("sala-fusca"), estado).json()["result"]
    assert segunda["resultType"] == "input_required"
    assert enum_de(segunda) == ["sala-mirante"]
    assert len(dominio.reservas) == 3


def test_accept_outside_offer_starts_new_round(fresh_app, mcp_post):
    client, _, dominio = fresh_app()
    args, chave, estado, primeiro = conflito_garagem(client, mcp_post)
    result = retomar(client, mcp_post, args, chave, aceitar("sala-aquario"), estado).json()["result"]
    assert result["resultType"] == "input_required"
    assert list(result["inputRequests"]) == [chave]
    assert enum_de(result) == enum_de(primeiro)
    assert result["requestState"] != estado
    assert len(dominio.reservas) == 2


@pytest.mark.parametrize(
    "resposta",
    [
        {"action": "accept"},
        {"action": "accept", "content": {"sala": 5}},
        {"action": "accept", "content": {}},
    ],
)
def test_accept_bad_content_starts_new_round(fresh_app, mcp_post, resposta):
    client, _, _ = fresh_app()
    args, chave, estado, _ = conflito_garagem(client, mcp_post)
    result = retomar(client, mcp_post, args, chave, resposta, estado).json()["result"]
    assert result["resultType"] == "input_required"


def test_new_round_state_is_usable_for_the_next_retry(fresh_app, mcp_post):
    client, _, _ = fresh_app()
    args, chave, estado, _ = conflito_garagem(client, mcp_post)
    novo = retomar(client, mcp_post, args, chave, aceitar("sala-aquario"), estado).json()["result"]
    final = retomar(client, mcp_post, args, chave, aceitar("sala-mirante"), novo["requestState"]).json()["result"]
    assert final["structuredContent"]["sala"] == "sala-mirante"


def test_chosen_room_booked_meanwhile_starts_new_round(fresh_app, mcp_post):
    client, _, dominio = fresh_app()
    args, chave, estado, _ = conflito_garagem(client, mcp_post)
    dominio.reservas.adicionar(Reserva("res-0003", "sala-fusca", h("14:00"), h("15:00"), "Biff"))
    result = retomar(client, mcp_post, args, chave, aceitar("sala-fusca"), estado).json()["result"]
    assert result["resultType"] == "input_required"
    assert enum_de(result) == ["sala-mirante"]
    no_horario = [r for r in dominio.reservas.da_sala("sala-fusca") if r.inicio == h("14:00")]
    assert len(no_horario) == 1 and len(dominio.reservas) == 3


def test_new_round_without_alternatives_returns_sem_alternativas(fresh_app, mcp_post):
    client, _, dominio = fresh_app()
    args, chave, estado, _ = conflito_garagem(client, mcp_post)
    dominio.reservas.adicionar(Reserva("res-0003", "sala-fusca", h("14:00"), h("15:00"), "Biff"))
    dominio.reservas.adicionar(Reserva("res-0004", "sala-mirante", h("14:00"), h("15:00"), "Biff"))
    result = retomar(client, mcp_post, args, chave, aceitar("sala-fusca"), estado).json()["result"]
    assert result["isError"] is True
    assert result["content"] == [{"type": "text", "text": SEM_ALTERNATIVAS}]
    assert "inputRequests" not in result and "requestState" not in result


def test_new_round_requires_form_capability(fresh_app, mcp_post):
    client, _, _ = fresh_app()
    args, chave, estado, _ = conflito_garagem(client, mcp_post)
    r = retomar(client, mcp_post, args, chave, aceitar("sala-aquario"), estado, caps={})
    assert r.status_code == 400 and erro(r)["code"] == -32021


def test_accept_and_decline_retries_do_not_require_capability(fresh_app, mcp_post):
    client, _, dominio = fresh_app()
    args, chave, estado, _ = conflito_garagem(client, mcp_post)
    recusa = retomar(client, mcp_post, args, chave, {"action": "decline"}, estado, caps={})
    assert recusa.json()["result"]["structuredContent"]["motivo"] == "recusado"
    aceite = retomar(client, mcp_post, args, chave, aceitar("sala-fusca"), estado, caps={})
    assert aceite.json()["result"]["structuredContent"]["reservado"] is True
    assert len(dominio.reservas) == 3


@pytest.mark.parametrize("caps", [{}, {"elicitation": {}}])
def test_conflict_without_capability_returns_32021(fresh_app, mcp_post, caps):
    client, _, dominio = fresh_app()
    r = reservar(client, mcp_post, "sala-garagem", h("14:00"), h("15:00"), "Marty", caps=caps)
    assert r.status_code == 400
    e = erro(r)
    assert e["code"] == -32021
    assert e["data"] == {"requiredCapabilities": {"elicitation": {"form": {}}}}
    assert len(dominio.reservas) == 2


def test_32021_matches_wire_capture(fresh_app, repo_root):
    client, _, _ = fresh_app()
    captured = wire(repo_root, "06-erro-32021-sem-elicitation.json")
    r = client.post("/mcp", json=captured["request"]["body"], headers=captured["request"]["headers"])
    assert r.status_code == 400
    assert r.json()["error"]["data"] == captured["response"]["body"]["error"]["data"]


def test_free_booking_without_capability_succeeds(fresh_app, mcp_post):
    client, _, _ = fresh_app()
    result = reservar(client, mcp_post, "sala-aquario", h("09:00"), h("10:00"), caps={}).json()["result"]
    assert result["resultType"] == "complete" and result["structuredContent"]["reservado"] is True


def test_tampered_state_last_six_chars_rejected(fresh_app, mcp_post):
    client, _, dominio = fresh_app()
    args, chave, estado, _ = conflito_garagem(client, mcp_post)
    for sufixo in ("AAAAAA", "BBBBBB"):
        r = retomar(client, mcp_post, args, chave, aceitar("sala-fusca"), estado[:-6] + sufixo)
        assert r.status_code == 400 and erro(r)["code"] == -32602
    assert len(dominio.reservas) == 2


def test_ten_mutations_rejected(fresh_app, mcp_post):
    client, _, dominio = fresh_app()
    args, chave, estado, _ = conflito_garagem(client, mcp_post)
    n = len(estado)
    for posicao in (3, 4, 20, n // 4, n // 2, 3 * n // 4, n - 10, n - 7, n - 3, n - 1):
        troca = "A" if estado[posicao] != "A" else "B"
        mutado = estado[:posicao] + troca + estado[posicao + 1 :]
        r = retomar(client, mcp_post, args, chave, aceitar("sala-fusca"), mutado)
        assert r.status_code == 400 and erro(r)["code"] == -32602, posicao
    assert len(dominio.reservas) == 2


def test_tampered_arguments_never_take_effect(fresh_app, mcp_post):
    client, _, dominio = fresh_app()
    dominio.reservas.adicionar(Reserva("res-0003", "sala-garagem", h("09:00"), h("10:00"), "Ocupante"))
    r = reservar(client, mcp_post, "sala-garagem", h("09:00"), h("10:00"), "Doc")
    chave, estado = chave_e_estado(r.json()["result"])
    adulterados = argumentos("sala-mirante", h("13:00"), h("14:00"), "Biff")
    resposta = retomar(client, mcp_post, adulterados, chave, aceitar("sala-fusca"), estado)
    corpo = resposta.json()
    if "error" in corpo:
        assert corpo["error"]["code"] == -32602
    else:
        sc = corpo["result"]["structuredContent"]
        assert (sc["inicio"], sc["responsavel"]) == (h("09:00"), "Doc")
    assert not any(r.responsavel == "Biff" for r in dominio.reservas.todas())


def test_state_presented_to_other_tool_rejected(fresh_app, mcp_post):
    client, _, _ = fresh_app()
    args, chave, estado, _ = conflito_garagem(client, mcp_post)
    consulta = {k: args[k] for k in ("sala", "inicio", "fim")}
    r = mcp_post(
        client,
        "tools/call",
        {"name": "consultar_disponibilidade", "arguments": consulta, "requestState": estado},
        id=secrets.token_hex(6),
    )
    assert r.status_code == 400 and erro(r)["code"] == -32602


def test_expired_state_rejected(fresh_app, mcp_post, monkeypatch):
    client, _, dominio = fresh_app()
    args, chave, estado, _ = conflito_garagem(client, mcp_post)
    real = time.time
    monkeypatch.setattr(time, "time", lambda: real() + 601)
    r = retomar(client, mcp_post, args, chave, aceitar("sala-fusca"), estado)
    assert r.status_code == 400 and erro(r)["code"] == -32602
    assert len(dominio.reservas) == 2


def test_state_from_other_secret_rejected(fresh_app, mcp_post):
    app_a, _, _ = fresh_app(request_state_security=politica_de_estado(secrets.token_hex(32)))
    args, chave, estado, _ = conflito_garagem(app_a, mcp_post)
    app_b, _, dominio_b = fresh_app(request_state_security=politica_de_estado(secrets.token_hex(32)))
    r = retomar(app_b, mcp_post, args, chave, aceitar("sala-fusca"), estado)
    assert r.status_code == 400 and erro(r)["code"] == -32602
    assert len(dominio_b.reservas) == 2


def test_retry_on_new_app_with_same_secret_succeeds(fresh_app, mcp_post):
    segredo = secrets.token_hex(32)
    app_a, _, _ = fresh_app(request_state_security=politica_de_estado(segredo))
    args, chave, estado, _ = conflito_garagem(app_a, mcp_post)
    app_b, _, dominio_b = fresh_app(request_state_security=politica_de_estado(segredo))
    result = retomar(app_b, mcp_post, args, chave, aceitar("sala-fusca"), estado).json()["result"]
    assert result["resultType"] == "complete" and result["structuredContent"]["sala"] == "sala-fusca"
    assert len(dominio_b.reservas) == 3


def test_missing_input_response_key_rejected(fresh_app, mcp_post):
    client, _, _ = fresh_app()
    args, chave, estado, _ = conflito_garagem(client, mcp_post)
    casos = [
        {"inputResponses": {}},
        {"inputResponses": {"outra-chave": aceitar("sala-fusca")}},
        {},
    ]
    for extra in casos:
        params = {"name": TOOL, "arguments": args, "requestState": estado, **extra}
        r = mcp_post(client, "tools/call", params, id=secrets.token_hex(6))
        assert r.status_code == 400
        e = erro(r)
        assert e["code"] == -32602
        assert e["message"] == "inputResponses sem resposta para reservar_sala:escolha_de_sala"


def test_zero_alternatives_conflict(fresh_app, mcp_post):
    client, _, dominio = fresh_app()
    primeira = reservar(client, mcp_post, "sala-mirante", h("11:00"), h("12:00")).json()["result"]
    assert primeira["structuredContent"]["reservado"] is True
    result = reservar(client, mcp_post, "sala-mirante", h("11:00"), h("12:00")).json()["result"]
    assert result["isError"] is True and result["resultType"] == "complete"
    assert result["content"] == [{"type": "text", "text": SEM_ALTERNATIVAS}]
    assert "inputRequests" not in result and "requestState" not in result
    assert len(dominio.reservas) == 3


def test_validation_still_runs_before_conflict_logic(fresh_app, mcp_post):
    client, _, _ = fresh_app()
    result = reservar(client, mcp_post, "sala-garagem", h("14:00"), h("13:00")).json()["result"]
    assert result["isError"] is True
    assert result["content"][0]["text"] == "Intervalo invalido: fim deve ser posterior a inicio"


def test_no_state_kept_between_rounds():
    capturado = {}

    class Falso:
        def tool(self, **_):
            def decorar(fn):
                capturado["fn"] = fn
                return fn

            return decorar

    sentinela = object()
    modulo_reservar_sala.register(Falso(), sentinela)
    fn = capturado["fn"]
    assert fn.__code__.co_freevars == ("dominio",)
    assert fn.__closure__[0].cell_contents is sentinela


def test_same_conflict_twice_gives_same_offer_and_different_tokens(fresh_app, mcp_post):
    client, _, _ = fresh_app()
    *_, a = conflito_garagem(client, mcp_post)
    *_, b = conflito_garagem(client, mcp_post)
    assert a["inputRequests"] == b["inputRequests"]
    assert a["requestState"] != b["requestState"]

