import pytest

from servidor_mcp.alternativas import calcular_alternativas
from servidor_mcp.dominio import CatalogoDeSalas, LivroDeReservas, Reserva, Sala
from servidor_mcp.loader import load_dominio
from servidor_mcp.regras import PedidoValidado, validar_pedido


def h(hora):
    return f"2026-11-03T{hora}:00-03:00"


@pytest.fixture
def dominio(repo_root):
    return load_dominio(repo_root / "dados")


def pedido(dominio, sala, ini, fim):
    p = validar_pedido(dominio.catalogo, sala, h(ini), h(fim))
    assert isinstance(p, PedidoValidado)
    return p


def test_garagem_conflict_offers_fusca_then_mirante(dominio):
    p = pedido(dominio, "sala-garagem", "14:00", "15:00")
    assert calcular_alternativas(dominio.catalogo, dominio.reservas, p) == ("sala-fusca", "sala-mirante")


def test_fusca_conflict_offers_garagem_then_mirante(dominio):
    p = pedido(dominio, "sala-fusca", "16:00", "17:00")
    assert calcular_alternativas(dominio.catalogo, dominio.reservas, p) == ("sala-garagem", "sala-mirante")


@pytest.mark.parametrize("sala", ["sala-aquario", "sala-porao", "sala-garagem", "sala-fusca", "sala-mirante"])
def test_requested_room_never_offered(dominio, sala):
    p = pedido(dominio, sala, "09:00", "10:00")
    assert sala not in calcular_alternativas(dominio.catalogo, dominio.reservas, p)


def test_smaller_rooms_never_offered(dominio):
    p = pedido(dominio, "sala-porao", "09:00", "10:00")
    ofertas = calcular_alternativas(dominio.catalogo, dominio.reservas, p)
    assert ofertas and all(dominio.catalogo.get(i).capacidade >= 6 for i in ofertas)
    assert "sala-aquario" not in ofertas


def test_capped_at_three_sorted_by_capacity_then_id(dominio):
    p = pedido(dominio, "sala-aquario", "09:00", "10:00")
    assert calcular_alternativas(dominio.catalogo, dominio.reservas, p) == ("sala-porao", "sala-fusca", "sala-garagem")


def test_busy_candidate_excluded(dominio):
    dominio.reservas.adicionar(Reserva("res-0003", "sala-fusca", h("14:30"), h("15:30"), "Biff"))
    p = pedido(dominio, "sala-garagem", "14:00", "15:00")
    assert calcular_alternativas(dominio.catalogo, dominio.reservas, p) == ("sala-mirante",)


def test_back_to_back_candidate_is_free(dominio):
    dominio.reservas.adicionar(Reserva("res-0003", "sala-fusca", h("15:00"), h("16:00"), "Biff"))
    p = pedido(dominio, "sala-garagem", "14:00", "15:00")
    assert "sala-fusca" in calcular_alternativas(dominio.catalogo, dominio.reservas, p)


def test_largest_room_has_no_alternatives(dominio):
    p = pedido(dominio, "sala-mirante", "11:00", "12:00")
    assert calcular_alternativas(dominio.catalogo, dominio.reservas, p) == ()


def test_custom_catalog_tie_break_by_id():
    catalogo = CatalogoDeSalas(
        [
            Sala("req", "Req", 10, ()),
            Sala("b", "B", 12, ()),
            Sala("a", "A", 12, ()),
            Sala("c", "C", 12, ()),
            Sala("d", "D", 12, ()),
        ]
    )
    p = validar_pedido(catalogo, "req", h("09:00"), h("10:00"))
    assert calcular_alternativas(catalogo, LivroDeReservas(), p) == ("a", "b", "c")
