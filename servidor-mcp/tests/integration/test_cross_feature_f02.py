"""F02 contracts consumed by F04, F06 and F08 (server side)."""

import json

import pytest


def policy_version(text: str) -> str:
    return text.splitlines()[0].split("versao:", 1)[1].strip()


def read_policy(client, mcp_post) -> str:
    r = mcp_post(client, "resources/read", {"uri": "politica://uso"})
    return r.json()["result"]["contents"][0]["text"]


def test_policy_version_read_from_resource_equals_foundation_version(fresh_app, mcp_post):
    client, _, dominio = fresh_app()
    assert policy_version(read_policy(client, mcp_post)) == dominio.politica.versao == "2026-11-01"


def test_reservation_politica_equals_version_read_from_resource(fresh_app, mcp_post):
    client, _, _ = fresh_app()
    names = {t["name"] for t in mcp_post(client, "tools/list").json()["result"]["tools"]}
    if "reservar_sala" not in names:
        pytest.skip("consumer feature not registered yet")
    version = policy_version(read_policy(client, mcp_post))
    args = {
        "sala": "sala-aquario",
        "inicio": "2026-11-03T09:00:00-03:00",
        "fim": "2026-11-03T10:00:00-03:00",
        "responsavel": "Doc",
    }
    r = mcp_post(client, "tools/call", {"name": "reservar_sala", "arguments": args})
    assert r.json()["result"]["structuredContent"]["politica"] == version


def test_agent_style_policy_read_is_accepted_and_logged(fresh_app, repo_root):
    client, log_lines, _ = fresh_app()
    wire = json.loads(
        (repo_root / "exemplos" / "wire" / "05-resources-read-politica.json").read_text(encoding="utf-8")
    )
    req = wire["request"]
    r = client.post("/mcp", json=req["body"], headers=req["headers"])
    assert r.status_code == 200
    (content,) = r.json()["result"]["contents"]
    (expected,) = wire["response"]["body"]["result"]["contents"]
    assert content["uri"] == expected["uri"] and content["mimeType"] == expected["mimeType"]
    assert content["text"].encode("utf-8") == (repo_root / "dados" / "politica-de-uso.md").read_bytes()
    assert log_lines() == [
        "mcp method=resources/read id=5 name=politica://uso "
        "traceparent=00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"
    ]
