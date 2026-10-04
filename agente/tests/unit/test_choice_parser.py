import pytest

from agente.skills.choice_parser import AcceptChoice, DeclineChoice, classify_choice, parse_choice_value

ALTS = ("sala-fusca", "sala-mirante")


def test_accepts_offered_alternative():
    assert classify_choice("escolha=sala-fusca", ALTS) == AcceptChoice("sala-fusca")


def test_surrounding_whitespace_is_stripped():
    assert classify_choice("  escolha=sala-mirante\n", ALTS) == AcceptChoice("sala-mirante")


def test_recusar_is_decline():
    assert classify_choice("escolha=recusar", ALTS) == DeclineChoice()


@pytest.mark.parametrize(
    "text",
    [
        "escolha=sala-aquario",
        "escolha=Sala-Fusca",
        "escolha=RECUSAR",
        "escolha = sala-fusca",
        "Escolha=sala-fusca",
        "escolha=",
        "escolha=sala-fusca extra",
        "sala-fusca",
        "reservar sala=sala-porao inicio=x fim=y responsavel=z",
        "",
    ],
)
def test_invalid_replies_return_none(text):
    assert classify_choice(text, ALTS) is None


def test_parse_choice_value_is_syntactic_only():
    assert parse_choice_value("escolha=anything") == "anything"
    assert parse_choice_value("nope") is None
