import threading

import pytest

from servidor_mcp import regras
from servidor_mcp.dominio import LivroDeReservas, Reserva
from servidor_mcp.loader import load_dominio
from servidor_mcp.reservas import SalaOcupada, proximo_id, registrar_se_livre


@pytest.fixture
def dominio(repo_root):
    return load_dominio(repo_root / "dados")


def h(hora, dia="2026-11-03"):
    return f"{dia}T{hora}:00-03:00"


def pedido(dominio, sala, inicio, fim):
    p = regras.validar_pedido(dominio.catalogo, sala, inicio, fim)
    assert isinstance(p, regras.PedidoValidado)
    return p


def res(id):
    return Reserva(id, "sala-aquario", h("09:00"), h("10:00"), "Doc")


def test_proximo_id_continues_seeded_ledger(dominio):
    assert proximo_id(dominio.reservas.todas()) == "res-0003"


def test_proximo_id_uses_highest_suffix_not_count():
    assert proximo_id([res("res-0001"), res("res-0007")]) == "res-0008"


def test_proximo_id_empty_ledger():
    assert proximo_id([]) == "res-0001"


def test_proximo_id_ignores_non_matching_ids():
    ids = ["res-0002", "abc", "res-x9", "res-0010b"]
    assert proximo_id([res(i) for i in ids]) == "res-0003"


def test_proximo_id_widens_past_9999():
    assert proximo_id([res("res-9999")]) == "res-10000"


def test_registrar_se_livre_appends_verbatim(dominio):
    r = registrar_se_livre(dominio.reservas, pedido(dominio, "sala-aquario", h("09:00"), h("10:00")), "Doc")
    assert r == Reserva("res-0003", "sala-aquario", h("09:00"), h("10:00"), "Doc")
    assert len(dominio.reservas) == 3


def test_registrar_se_livre_keeps_original_offset_strings(dominio):
    ini, fim = "2026-11-03T12:00:00Z", "2026-11-03T13:00:00Z"
    r = registrar_se_livre(dominio.reservas, pedido(dominio, "sala-aquario", ini, fim), "Doc")
    assert isinstance(r, Reserva) and (r.inicio, r.fim) == (ini, fim)
    assert dominio.reservas.todas()[-1].inicio == ini


def test_registrar_se_livre_returns_sala_ocupada_on_conflict(dominio):
    r = registrar_se_livre(dominio.reservas, pedido(dominio, "sala-garagem", h("14:00"), h("15:00")), "Doc")
    assert isinstance(r, SalaOcupada)
    assert [c.id for c in r.conflitos] == ["res-0001"]
    assert len(dominio.reservas) == 2


def test_back_to_back_booking_is_allowed(dominio):
    r = registrar_se_livre(dominio.reservas, pedido(dominio, "sala-garagem", h("15:00"), h("16:00")), "Doc")
    assert isinstance(r, Reserva)


def test_second_booking_of_same_slot_conflicts_with_first(dominio):
    p = pedido(dominio, "sala-aquario", h("09:00"), h("10:00"))
    first = registrar_se_livre(dominio.reservas, p, "Doc")
    second = registrar_se_livre(dominio.reservas, p, "Marty")
    assert isinstance(second, SalaOcupada) and second.conflitos == (first,)


def test_exception_during_append_leaves_ledger_unchanged(dominio, monkeypatch):
    p = pedido(dominio, "sala-aquario", h("09:00"), h("10:00"))
    with monkeypatch.context() as m:
        m.setattr(dominio.reservas, "adicionar", lambda r: (_ for _ in ()).throw(RuntimeError("boom")))
        with pytest.raises(RuntimeError):
            registrar_se_livre(dominio.reservas, p, "Doc")
    assert len(dominio.reservas) == 2
    assert registrar_se_livre(dominio.reservas, p, "Doc").id == "res-0003"


def _run_threads(fn, n):
    barrier = threading.Barrier(n)
    out = [None] * n

    def work(i):
        barrier.wait(timeout=10)
        out[i] = fn(i)

    threads = [threading.Thread(target=work, args=(i,)) for i in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=20)
    return out


def test_concurrent_same_slot_books_exactly_once(dominio):
    p = pedido(dominio, "sala-aquario", h("09:00"), h("10:00"))
    out = _run_threads(lambda i: registrar_se_livre(dominio.reservas, p, f"u{i}"), 20)
    assert sum(isinstance(o, Reserva) for o in out) == 1
    assert sum(isinstance(o, SalaOcupada) for o in out) == 19
    assert len(dominio.reservas) == 3


def test_concurrent_distinct_slots_get_distinct_consecutive_ids(dominio):
    salas = ["sala-aquario", "sala-porao", "sala-mirante", "sala-fusca", "sala-garagem"]
    slots = [(s, h("08:00"), h("09:00")) for s in salas] + [(s, h("10:00"), h("11:00")) for s in salas]
    pedidos = [pedido(dominio, *s) for s in slots]
    out = _run_threads(lambda i: registrar_se_livre(dominio.reservas, pedidos[i], "Doc"), 10)
    assert all(isinstance(o, Reserva) for o in out)
    assert sorted(o.id for o in out) == [f"res-{n:04d}" for n in range(3, 13)]


def test_ledger_without_seed_starts_at_one():
    livro = LivroDeReservas()
    assert proximo_id(livro.todas()) == "res-0001"
