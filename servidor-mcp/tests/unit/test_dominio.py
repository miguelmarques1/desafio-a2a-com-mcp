import threading

import pytest

from servidor_mcp.dominio import Reserva
from servidor_mcp.loader import load_dominio


@pytest.fixture
def dominio(repo_root):
    return load_dominio(repo_root / "dados")


def nova(id, sala="sala-aquario"):
    return Reserva(id, sala, "2026-11-03T09:00:00-03:00", "2026-11-03T10:00:00-03:00", "Doc")


def test_catalog_lookup_and_order(dominio):
    assert dominio.catalogo.get("sala-porao").nome == "Porao"
    assert [s.id for s in dominio.catalogo][0] == "sala-aquario"
    assert len(dominio.catalogo) == 5
    assert "sala-fusca" in dominio.catalogo


def test_catalog_unknown_id_returns_none(dominio):
    assert dominio.catalogo.get("sala-delorean") is None
    assert "sala-delorean" not in dominio.catalogo


def test_ledger_append_is_visible_in_later_snapshots(dominio):
    dominio.reservas.adicionar(nova("res-0003"))
    assert "res-0003" in [r.id for r in dominio.reservas.todas()]
    assert [r.id for r in dominio.reservas.da_sala("sala-aquario")] == ["res-0003"]
    assert len(dominio.reservas) == 3


def test_ledger_rejects_duplicate_id_and_stays_unchanged(dominio):
    antes = dominio.reservas.todas()
    with pytest.raises(ValueError):
        dominio.reservas.adicionar(nova("res-0001"))
    assert dominio.reservas.todas() == antes


def test_ledger_snapshot_is_detached(dominio):
    snap = dominio.reservas.todas()
    assert isinstance(snap, tuple)
    dominio.reservas.adicionar(nova("res-0003"))
    assert len(snap) == 2 and len(dominio.reservas) == 3


def test_ledger_filter_by_room_keeps_insertion_order(dominio):
    for i, sala in enumerate(["sala-porao", "sala-aquario", "sala-porao", "sala-porao"], start=3):
        dominio.reservas.adicionar(nova(f"res-{i:04d}", sala))
    assert [r.id for r in dominio.reservas.da_sala("sala-porao")] == ["res-0003", "res-0005", "res-0006"]


def test_ledger_concurrent_appends_are_all_kept(dominio):
    threads = [
        threading.Thread(target=dominio.reservas.adicionar, args=(nova(f"res-x{i}"),))
        for i in range(50)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    ids = [r.id for r in dominio.reservas.todas()]
    assert len(ids) == 52 and len(set(ids)) == 52


def test_as_dict_key_order_matches_data_files(dominio):
    assert list(dominio.catalogo.get("sala-aquario").as_dict()) == ["id", "nome", "capacidade", "recursos"]
    assert list(dominio.reservas.todas()[0].as_dict()) == ["id", "sala", "inicio", "fim", "responsavel"]


def test_bloqueio_is_reentrant_with_ledger_methods(dominio):
    done = threading.Event()

    def work():
        with dominio.reservas.bloqueio():
            assert len(dominio.reservas.todas()) == 2
            assert len(dominio.reservas.da_sala("sala-garagem")) == 1
            dominio.reservas.adicionar(nova("res-0003"))
        done.set()

    t = threading.Thread(target=work, daemon=True)
    t.start()
    assert done.wait(timeout=5), "deadlock inside bloqueio()"
    assert [r.id for r in dominio.reservas.todas()][-1] == "res-0003"


def test_bloqueio_excludes_other_threads(dominio):
    order: list[str] = []
    entered = threading.Event()
    release = threading.Event()

    def holder():
        with dominio.reservas.bloqueio():
            entered.set()
            release.wait(timeout=5)
            order.append("A-exit")

    def other():
        dominio.reservas.adicionar(nova("res-0003"))
        order.append("B-done")

    a = threading.Thread(target=holder, daemon=True)
    a.start()
    assert entered.wait(timeout=5)
    b = threading.Thread(target=other, daemon=True)
    b.start()
    b.join(timeout=0.3)
    assert b.is_alive()
    release.set()
    a.join(timeout=5)
    b.join(timeout=5)
    assert order == ["A-exit", "B-done"]
