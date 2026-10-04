import pytest

from agente.skills.request_parser import ReservationRequest, parse_reservation_request

CANONICAL = (
    "reservar sala=sala-porao inicio=2026-11-03T09:00:00-03:00 "
    "fim=2026-11-03T10:00:00-03:00 responsavel=Doc"
)


def test_parses_canonical_request():
    request = parse_reservation_request(CANONICAL)
    assert request == ReservationRequest(
        "sala-porao", "2026-11-03T09:00:00-03:00", "2026-11-03T10:00:00-03:00", "Doc"
    )
    assert list(request.arguments()) == ["sala", "inicio", "fim", "responsavel"]


def test_multiple_spaces_and_surrounding_whitespace_accepted():
    request = parse_reservation_request("  reservar   sala=a  inicio=b   fim=c  responsavel=d \n")
    assert request == ReservationRequest("a", "b", "c", "d")


def test_name_is_rest_of_line_trimmed():
    spaced = parse_reservation_request("reservar sala=a inicio=b fim=c responsavel=  Emmett  Brown  ")
    assert spaced.responsavel == "Emmett  Brown"
    extra = parse_reservation_request("reservar sala=a inicio=b fim=c responsavel=Doc extra=1")
    assert extra.responsavel == "Doc extra=1"


def test_values_are_not_validated():
    request = parse_reservation_request(
        "reservar sala=sala-delorean inicio=amanha fim=2026-11-03T14:00:00 responsavel=Doc"
    )
    assert (request.sala, request.inicio, request.fim) == ("sala-delorean", "amanha", "2026-11-03T14:00:00")


@pytest.mark.parametrize(
    "text",
    [
        "reservar sala=sala-porao",
        "reservar sala=a inicio=b fim=c",
        "reservar inicio=b sala=a fim=c responsavel=d",
        "Reservar sala=a inicio=b fim=c responsavel=d",
        "RESERVAR sala=a inicio=b fim=c responsavel=d",
        "reservar Sala=a inicio=b fim=c responsavel=d",
        "reservar sala= inicio=b fim=c responsavel=d",
        "reservar sala=a inicio= fim=c responsavel=d",
        "reservar sala=a inicio=b fim=c responsavel=",
        "reservar sala=a inicio=b fim=c responsavel=   ",
        "reservar\tsala=a inicio=b fim=c responsavel=d",
        "reservar sala=a inicio=b fim=c responsavel=Doc\nMarty",
        "reservar sala=a\ninicio=b fim=c responsavel=d",
        "sala=a inicio=b fim=c responsavel=d",
        "reservarsala=a inicio=b fim=c responsavel=d",
        "",
        "     ",
        "reservar sala=x",
    ],
)
def test_malformed_variants_return_none(text):
    assert parse_reservation_request(text) is None


def test_parts_joined_text_is_parsed():
    text = " ".join(["reservar sala=a", "inicio=b fim=c responsavel=d"])
    assert parse_reservation_request(text) == ReservationRequest("a", "b", "c", "d")


def test_arguments_returns_new_dict():
    request = parse_reservation_request(CANONICAL)
    request.arguments()["sala"] = "x"
    assert request.arguments()["sala"] == "sala-porao"
