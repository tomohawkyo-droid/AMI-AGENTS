#!/usr/bin/env python3
"""AMI Document Production CLI.

Passthrough facade for bootstrapped document tools.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

TOOLS = {
    "pandoc": "Document converter (Markdown, HTML, DOCX, PDF, etc.)",
    "wkhtmltopdf": "HTML to PDF renderer",
    "wkhtmltoimage": "HTML to image renderer",
    "pdflatex": "LaTeX to PDF (pdfTeX engine)",
    "xelatex": "LaTeX to PDF (XeTeX engine, Unicode)",
    "lualatex": "LaTeX to PDF (LuaTeX engine)",
    "pdfjam": "PDF page manipulation (n-up, merge, crop)",
}


def _boot_bin() -> str:
    ami_root = os.environ.get("AMI_ROOT")
    if not ami_root:
        print("Error: AMI_ROOT not set", file=sys.stderr)
        sys.exit(1)
    return str(Path(ami_root) / ".boot-linux" / "bin")


def _find_tool(name: str) -> str | None:
    boot = Path(_boot_bin()) / name
    if boot.exists():
        return str(boot)
    return shutil.which(name)


def _print_help() -> None:
    print("ami-docs: Document production tools\n")
    print("Usage: ami-docs <tool> [tool-args...]\n")
    print("Tools:")
    for name, desc in TOOLS.items():
        installed = "installed" if _find_tool(name) else "not found"
        print(f"  {name:<16} {desc} ({installed})")
    print("\nExamples:")
    print("  ami-docs pandoc README.md -o README.pdf")
    print("  ami-docs pandoc README.md -t docx -o README.docx")
    print("  ami-docs wkhtmltopdf report.html report.pdf")
    print("  ami-docs pdflatex paper.tex")
    print("  ami-docs xelatex paper.tex")
    print("  ami-docs pdfjam --nup 2x2 slides.pdf --outfile handout.pdf")


_MIN_ARGS = 2


def main() -> int:
    if len(sys.argv) < _MIN_ARGS or sys.argv[1] in ("-h", "--help"):
        _print_help()
        return 0

    tool = sys.argv[1]
    if tool not in TOOLS:
        print(f"Unknown tool: {tool}", file=sys.stderr)
        print(f"Available: {', '.join(TOOLS)}", file=sys.stderr)
        return 1

    binary = _find_tool(tool)
    if not binary:
        print(f"Error: {tool} not found. Run bootstrap to install it.", file=sys.stderr)
        return 1

    return subprocess.run([binary, *sys.argv[2:]], check=False).returncode


if __name__ == "__main__":
    sys.exit(main())
