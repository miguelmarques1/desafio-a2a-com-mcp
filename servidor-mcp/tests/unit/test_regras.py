from datetime import datetime, timedelta, timezone

import pytest

from servidor_mcp import mensagens
from servidor_mcp.dominio import LivroDeReservas, Reserva
from servidor_mcp.loader import load_dominio
from servidor_mcp.regras import (
    POLITICA_OFFSET,
    FalhaDeValidacao,
    Intervalo,
    PedidoValidado,
    conflitos_no_intervalo,
    interpretar_horario,
    validar_pedido,
)

DIA = "2026-11-03"


def h(hora, dia=DIA, offset="-03:00"):
    return f"{dia}T{hora}{offset}"


@pytest.fixture
def dominio(repo_root):
    return load_dominio(repo_root / "dados")


def validar(dominio, inicio, fim, sala="sala-aquario"):
    return validar_pedido(dominio.catalogo, sala, inicio, fim)


def intervalo(inicio, fim):
    return Intervalo(interpretar_horario(inicio), interpretar_horario(fim))


def consulta(dominio, sala, inicio, fim, reservas=None):
    return conflitos_no_intervalo((reservas or dominio.reservas), sala, intervalo(inicio, fim))


# --- interpretar_horario -------------------------------------------------


@pytest.mark.parametrize(
    "valor, esperado",
    [
        ("2026-11-03T14:00:00-03:00", datetime(2026, 11, 3, 14, tzinfo=POLITICA_OFFSET)),
        ("2026-11-03T17:00:00Z", datetime(2026, 11, 3, 14, tzinfo=POLITICA_OFFSET)),
        ("2026-11-03T17:00:00+00:00", datetime(2026, 11, 3, 14, tzinfo=POLITICA_OFFSET)),
        ("2026-11-03T17:00:00-00:00", datetime(2026, 11, 3, 14, tzinfo=POLITICA_OFFSET)),
        ("2026-11-03T12:00:00-05:00", datetime(2026, 11, 3, 14, tzinfo=POLITICA_OFFSET)),
        ("2026-11-03T14:00-03:00", datetime(2026, 11, 3, 14, tzinfo=POLITICA_OFFSET)),
        ("2026-11-03T14:00:00.5-03:00", datetime(2026, 11, 3, 14, 0, 0, 500000, tzinfo=POLITICA_OFFSET)),
        ("2026-11-03T14:00:00.123456-03:00", datetime(2026, 11, 3, 14, 0, 0, 123456, tzinfo=POLITICA_OFFSET)),
    ],
)
def test_interpretar_horario_accepts_explicit_offset_forms(valor, esperado):
    got = interpretar_horario(valor)
    assert got == esperado
    assert got.utcoffset() == timedelta(hours=-3)


@pytest.mark.parametrize(
    "valor",
    [
        "2026-11-03T14:00:00",
        "2026-11-03",
        "2026-11-03 14:00:00-03:00",
        "2026-11-03t14:00:00-03:00",
        "2026-11-03T14:00:00z",
        "2026-11-03T14:00:00-0300",
        "2026-11-03T14:00:00-03",
        "2026-11-03T14:00:00.1234567-03:00",
        "20261103T140000-0300",
        " 2026-11-03T14:00:00-03:00",
        "2026-11-03T14:00:00-03:00 ",
        "2026-11-03T14:00:00-03:00\n",
        "",
        "amanha",
        "２０２６-11-03T14:00:00-03:00",
    ],
)
def test_interpretar_horario_rejects_invalid_forms(valor):
    assert interpretar_horario(valor) is None


@pytest.mark.parametrize(
    "valor",
    [
        "2026-13-03T10:00:00-03:00",
        "2026-02-30T10:00:00-03:00",
        "2026-02-29T10:00:00-03:00",
        "2026-11-03T24:00:00-03:00",
        "2026-11-03T10:60:00-03:00",
        "2026-11-03T10:00:60-03:00",
        "2026-11-03T14:00:00+24:00",
        "2026-11-03T14:00:00-03:60",
        "0000-11-03T10:00:00-03:00",
    ],
)
def test_interpretar_horario_rejects_impossible_calendar_values(valor):
    assert interpretar_horario(valor) is None


def test_interpretar_horario_accepts_leap_day():
    assert interpretar_horario("2028-02-29T10:00:00-03:00") is not None


def test_interpretar_horario_out_of_range_after_conversion_is_none():
    assert interpretar_horario("0001-01-01T00:30:00+01:00") is None
    assert interpretar_horario("9999-12-31T23:59:59-23:59") is None


# --- validar_pedido ------------------------------------------------------


def test_valid_request_returns_validated_request(dominio):
    r = validar(dominio, h("09:00:00"), h("10:00:00"))
    assert isinstance(r, PedidoValidado)
    assert r.sala.capacidade == 4
    assert (r.inicio, r.fim) == (h("09:00:00"), h("10:00:00"))
    assert r.intervalo.inicio == datetime(2026, 11, 3, 9, tzinfo=POLITICA_OFFSET)
    assert r.intervalo.fim == datetime(2026, 11, 3, 10, tzinfo=POLITICA_OFFSET)


def test_unknown_room_returns_exact_message(dominio):
    r = validar(dominio, h("09:00:00"), h("10:00:00"), sala="sala-delorean")
    assert r == FalhaDeValidacao("sala_inexistente", "Sala inexistente: sala-delorean")


@pytest.mark.parametrize("sala", ["Sala-Aquario", " sala-aquario", ""])
def test_room_match_is_exact(dominio, sala):
    r = validar(dominio, h("09:00:00"), h("10:00:00"), sala=sala)
    assert r.regra == "sala_inexistente" and r.mensagem == f"Sala inexistente: {sala}"


def test_timestamp_without_offset_returns_exact_message(dominio):
    r = validar(dominio, "2026-11-03T14:00:00", h("15:00:00"))
    assert r == FalhaDeValidacao("horario_invalido", "Horario invalido: 2026-11-03T14:00:00")


def test_inicio_is_checked_before_fim(dominio):
    assert validar(dominio, "ruim-1", "ruim-2").mensagem == "Horario invalido: ruim-1"
    assert validar(dominio, h("09:00:00"), "ruim-2").mensagem == "Horario invalido: ruim-2"


@pytest.mark.parametrize("inicio, fim", [("10:00:00", "09:00:00"), ("10:00:00", "10:00:00")])
def test_inverted_or_empty_interval(dominio, inicio, fim):
    r = validar(dominio, h(inicio), h(fim))
    assert r == FalhaDeValidacao("intervalo_invalido", "Intervalo invalido: fim deve ser posterior a inicio")


def test_interval_compares_instants_not_strings(dominio):
    r = validar(dominio, h("10:00:00"), f"{DIA}T12:30:00Z")
    assert r.regra == "intervalo_invalido"


@pytest.mark.parametrize(
    "inicio, fim",
    [
        ("07:00:00", "08:00:00"),
        ("07:59:59.999999", "08:30:00"),
        ("19:30:00", "20:01:00"),
        ("19:00:00", "20:00:00.000001"),
    ],
)
def test_window_violations(dominio, inicio, fim):
    assert validar(dominio, h(inicio), h(fim)).regra == "fora_da_janela"


@pytest.mark.parametrize("inicio, fim", [("08:00:00", "10:00:00"), ("18:00:00", "20:00:00")])
def test_window_boundaries_are_inclusive(dominio, inicio, fim):
    assert isinstance(validar(dominio, h(inicio), h(fim)), PedidoValidado)


def test_window_is_evaluated_in_policy_offset(dominio):
    assert validar(dominio, f"{DIA}T10:00:00Z", f"{DIA}T12:00:00Z").regra == "fora_da_janela"
    assert isinstance(validar(dominio, f"{DIA}T11:00:00Z", f"{DIA}T13:00:00Z"), PedidoValidado)
    assert isinstance(validar(dominio, f"{DIA}T22:00:00Z", f"{DIA}T23:00:00Z"), PedidoValidado)


def test_interval_spanning_two_policy_days_is_window_violation(dominio):
    r = validar(dominio, h("19:00:00"), h("09:00:00", dia="2026-11-04"))
    assert r.regra == "fora_da_janela"


@pytest.mark.parametrize(
    "inicio, fim, regra",
    [
        ("09:00:00", "11:00:00", None),
        ("09:00:00", "11:00:01", "duracao_acima_do_limite"),
        ("09:00:00", "11:00:00.000001", "duracao_acima_do_limite"),
        ("09:00:00", "12:00:00", "duracao_acima_do_limite"),
    ],
)
def test_duration_limit(dominio, inicio, fim, regra):
    r = validar(dominio, h(inicio), h(fim))
    if regra is None:
        assert isinstance(r, PedidoValidado)
    else:
        assert r == FalhaDeValidacao(regra, "Duracao acima do limite: a politica permite no maximo 2 horas")


@pytest.mark.parametrize(
    "sala, inicio, fim, regra",
    [
        ("sala-delorean", "ruim", h("09:00:00"), "sala_inexistente"),
        ("sala-aquario", "ruim", h("09:00:00"), "horario_invalido"),
        ("sala-aquario", h("10:00:00"), "ruim", "horario_invalido"),
        ("sala-aquario", "ruim", h("08:00:00"), "horario_invalido"),
        ("sala-aquario", h("07:00:00"), h("06:00:00"), "intervalo_invalido"),
        ("sala-aquario", h("07:00:00"), h("10:00:00"), "fora_da_janela"),
    ],
)
def test_first_failure_wins(dominio, sala, inicio, fim, regra):
    assert validar(dominio, inicio, fim, sala=sala).regra == regra


@pytest.mark.parametrize("dia", ["2001-01-02", "2099-12-30"])
def test_past_and_future_dates_are_valid(dominio, dia):
    assert isinstance(validar(dominio, h("09:00:00", dia=dia), h("10:00:00", dia=dia)), PedidoValidado)


def test_validation_is_deterministic(dominio):
    for inicio, fim in [(h("09:00:00"), h("10:00:00")), (h("07:00:00"), h("08:00:00"))]:
        assert validar(dominio, inicio, fim) == validar(dominio, inicio, fim)


def test_messages_match_prd_text(dominio):
    assert mensagens.SALA_INEXISTENTE.format(sala="sala-delorean") == "Sala inexistente: sala-delorean"
    assert mensagens.HORARIO_INVALIDO.format(valor="x") == "Horario invalido: x"
    assert mensagens.INTERVALO_INVALIDO == "Intervalo invalido: fim deve ser posterior a inicio"
    assert mensagens.FORA_DA_JANELA == "Fora da janela de uso: a politica permite reservas entre 08:00 e 20:00"
    assert mensagens.DURACAO_ACIMA_DO_LIMITE == "Duracao acima do limite: a politica permite no maximo 2 horas"


def test_messages_match_validator_constants(repo_root):
    import importlib.util

    spec = importlib.util.spec_from_file_location("validar", repo_root / "validador" / "validar.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert mod.ERRO_SALA == mensagens.SALA_INEXISTENTE.format(sala="sala-delorean")
    assert mod.ERRO_JANELA == mensagens.FORA_DA_JANELA
    assert mod.ERRO_DURACAO == mensagens.DURACAO_ACIMA_DO_LIMITE
    assert mod.ERRO_INTERVALO == mensagens.INTERVALO_INVALIDO


def test_braces_in_user_values_are_copied_literally(dominio):
    assert validar(dominio, "{x}", h("10:00:00")).mensagem == "Horario invalido: {x}"
    assert validar(dominio, h("09:00:00"), h("10:00:00"), sala="{sala}").mensagem == "Sala inexistente: {sala}"


# --- Intervalo / conflicts ----------------------------------------------


@pytest.mark.parametrize(
    "a, b, esperado",
    [
        (("14:00", "15:00"), ("15:00", "16:00"), False),
        (("15:00", "16:00"), ("14:00", "15:00"), False),
        (("14:00", "15:00"), ("14:00", "15:00"), True),
        (("14:00", "15:00"), ("14:30", "15:30"), True),
        (("13:00", "16:00"), ("14:00", "15:00"), True),
        (("14:00", "15:00"), ("13:00", "16:00"), True),
        (("09:00", "10:00"), ("14:00", "15:00"), False),
    ],
)
def test_intervalo_sobrepoe_is_half_open(a, b, esperado):
    ia, ib = intervalo(h(f"{a[0]}:00"), h(f"{a[1]}:00")), intervalo(h(f"{b[0]}:00"), h(f"{b[1]}:00"))
    assert ia.sobrepoe(ib) is esperado and ib.sobrepoe(ia) is esperado


def test_intervalo_sobrepoe_same_instant_in_different_offsets():
    a = intervalo(h("14:00:00"), h("15:00:00"))
    b = intervalo(f"{DIA}T17:00:00Z", f"{DIA}T18:00:00Z")
    assert a.sobrepoe(b) and b.sobrepoe(a)
    assert not a.sobrepoe(intervalo(f"{DIA}T18:00:00Z", f"{DIA}T19:00:00Z"))


@pytest.mark.parametrize("inicio, fim", [("15:00:00", "16:00:00"), ("13:00:00", "14:00:00")])
def test_back_to_back_is_not_a_conflict(dominio, inicio, fim):
    assert consulta(dominio, "sala-garagem", h(inicio), h(fim)) == ()


@pytest.mark.parametrize(
    "inicio, fim",
    [("14:00:00", "15:00:00"), ("14:30:00", "15:30:00"), ("13:30:00", "14:01:00"), ("13:00:00", "15:00:00"), ("14:15:00", "14:45:00")],
)
def test_overlaps_with_seeded_reservation(dominio, inicio, fim):
    assert [r.id for r in consulta(dominio, "sala-garagem", h(inicio), h(fim))] == ["res-0001"]


def test_only_the_requested_room_is_considered(dominio):
    assert consulta(dominio, "sala-porao", h("14:00:00"), h("15:00:00")) == ()


def test_overlap_detected_across_offsets(dominio):
    assert [r.id for r in consulta(dominio, "sala-garagem", f"{DIA}T17:30:00Z", f"{DIA}T18:30:00Z")] == ["res-0001"]
    assert consulta(dominio, "sala-garagem", f"{DIA}T18:00:00Z", f"{DIA}T19:00:00Z") == ()


def test_conflicts_sorted_by_instant_then_id():
    livro = LivroDeReservas(
        [
            Reserva("res-0005", "sala-x", f"{DIA}T16:30:00Z", f"{DIA}T17:00:00Z", "A"),  # 13:30 local
            Reserva("res-0007", "sala-x", h("14:00:00"), h("14:30:00"), "B"),
            Reserva("res-0004", "sala-x", f"{DIA}T17:00:00Z", f"{DIA}T17:30:00Z", "C"),  # 14:00 local
        ]
    )
    achados = conflitos_no_intervalo(livro, "sala-x", intervalo(h("13:00:00"), h("15:00:00")))
    assert [r.id for r in achados] == ["res-0005", "res-0004", "res-0007"]


def test_conflicts_are_ledger_entries_verbatim(dominio, repo_root):
    import json

    (achado,) = consulta(dominio, "sala-garagem", h("14:00:00"), h("15:00:00"))
    esperado = json.loads((repo_root / "dados" / "reservas.json").read_text(encoding="utf-8"))[0]
    assert achado == dominio.reservas.da_sala("sala-garagem")[0]
    assert achado.as_dict() == esperado


def test_appended_reservation_becomes_a_conflict(dominio):
    nova = Reserva("res-0003", "sala-aquario", h("09:00:00"), h("10:00:00"), "Doc")
    dominio.reservas.adicionar(nova)
    assert consulta(dominio, "sala-aquario", h("09:30:00"), h("10:30:00")) == (nova,)


def test_uninterpretable_ledger_entry_is_ignored():
    livro = LivroDeReservas(
        [
            Reserva("res-0001", "sala-x", "ontem", h("10:00:00"), "A"),
            Reserva("res-0002", "sala-x", h("09:00:00"), "amanha", "B"),
            Reserva("res-0003", "sala-x", h("09:00:00"), h("10:00:00"), "C"),
        ]
    )
    achados = conflitos_no_intervalo(livro, "sala-x", intervalo(h("09:00:00"), h("10:00:00")))
    assert [r.id for r in achados] == ["res-0003"]


def test_conflict_detection_does_not_modify_ledger(dominio):
    antes = dominio.reservas.todas()
    consulta(dominio, "sala-garagem", h("14:00:00"), h("15:00:00"))
    assert dominio.reservas.todas() == antes
