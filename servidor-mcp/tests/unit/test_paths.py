from pathlib import Path

from servidor_mcp import paths
from servidor_mcp.paths import find_repo_root, resolve_dados_dir


def test_override_is_used_verbatim():
    assert resolve_dados_dir("/qualquer/lugar") == Path("/qualquer/lugar")


def test_finds_repo_root_from_package_location(repo_root):
    result = resolve_dados_dir(None)
    assert result == repo_root / "dados"
    assert (result / "salas.json").is_file()


def test_falls_back_to_cwd_ancestors(tmp_path, monkeypatch):
    fake = tmp_path / "repo"
    (fake / "dados").mkdir(parents=True)
    (fake / "servidor-mcp").mkdir()
    sub = fake / "servidor-mcp"
    elsewhere = tmp_path / "outside" / "pkg"
    elsewhere.mkdir(parents=True)
    monkeypatch.setattr(paths, "__file__", str(elsewhere / "paths.py"))
    monkeypatch.chdir(sub)
    assert resolve_dados_dir(None) == fake.resolve() / "dados"


def test_last_resort_is_cwd_dados(tmp_path, monkeypatch):
    elsewhere = tmp_path / "pkg"
    elsewhere.mkdir()
    monkeypatch.setattr(paths, "__file__", str(elsewhere / "paths.py"))
    monkeypatch.chdir(tmp_path)
    assert resolve_dados_dir(None) == Path.cwd() / "dados"
    assert find_repo_root(tmp_path) is None
