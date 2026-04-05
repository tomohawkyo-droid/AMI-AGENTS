"""Dynamic ASCII art banner generation using the art library."""

from __future__ import annotations

import sys
from pathlib import Path

import tomllib
from art import text2art


def _find_pyproject(start: Path) -> Path:
    """Walk up from *start* to find pyproject.toml."""
    for parent in (start, *start.parents):
        candidate = parent / "pyproject.toml"
        if candidate.is_file():
            return candidate
    msg = "pyproject.toml not found"
    raise FileNotFoundError(msg)


def get_project_version(project_root: Path | None = None) -> str:
    """Read the project version from pyproject.toml."""
    start = project_root or Path(__file__).resolve().parent
    pyproject = _find_pyproject(start)
    with pyproject.open("rb") as f:
        data = tomllib.load(f)
    return str(data["project"]["version"])


def generate_banner_text(
    font: str = "standard",
    project_root: Path | None = None,
) -> str:
    """Generate ASCII art for 'OpenAMI v{version}'."""
    version = get_project_version(project_root)
    text = f"OpenAMI v{version}"
    raw = text2art(text, font=font)
    lines = [line.rstrip() for line in raw.splitlines()]
    # Strip trailing empty lines
    while lines and not lines[-1]:
        lines.pop()
    return "\n".join(lines)


def generate_banner_lines(
    font: str = "standard",
    project_root: Path | None = None,
) -> list[str]:
    """Generate ASCII art as a list of lines (for box-drawing)."""
    return generate_banner_text(font=font, project_root=project_root).splitlines()


if __name__ == "__main__":
    root = None
    if "--project-root" in sys.argv:
        idx = sys.argv.index("--project-root")
        if idx + 1 < len(sys.argv):
            root = Path(sys.argv[idx + 1]).resolve()
    print(generate_banner_text(project_root=root))
