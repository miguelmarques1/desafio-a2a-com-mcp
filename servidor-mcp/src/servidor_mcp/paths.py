"""Repository root and dados/ resolution."""

from __future__ import annotations

from pathlib import Path


def find_repo_root(start: Path) -> Path | None:
    """First ancestor (including start) holding both dados/ and servidor-mcp/."""
    start = Path(start).resolve()
    for candidate in (start, *start.parents):
        if (candidate / "dados").is_dir() and (candidate / "servidor-mcp").is_dir():
            return candidate
    return None


def resolve_dados_dir(override: str | Path | None = None) -> Path:
    if override:
        return Path(override)
    root = find_repo_root(Path(__file__).parent)
    if root is None:
        root = find_repo_root(Path.cwd())
    if root is not None:
        return root / "dados"
    return Path.cwd() / "dados"
