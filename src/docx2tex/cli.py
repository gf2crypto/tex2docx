"""Command line: docx2tex chapter.docx [-o chapter.tex] [--standalone] [-c cfg.yaml]."""

from __future__ import annotations

import argparse
from pathlib import Path

from . import __version__
from .config import Config
from .pipeline import convert


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="docx2tex", description="Word (.docx) -> LaTeX fragment")
    p.add_argument("source", type=Path, help=".docx file")
    p.add_argument("-o", "--output", type=Path, help="output .tex (default: next to source)")
    p.add_argument("-c", "--config", type=Path, help="YAML config (docx2tex: section)")
    p.add_argument("--standalone", action="store_true",
                   help="also write <out>.standalone.tex with a preamble and compile it as a check")
    p.add_argument("--engine", choices=["pdflatex", "xelatex", "lualatex"])
    p.add_argument("--workdir", type=Path)
    p.add_argument("--version", action="version", version=f"docx2tex {__version__}")
    a = p.parse_args(argv)
    config = Config.load(a.config)
    if a.engine:
        config.engine = a.engine
    output = a.output or a.source.with_suffix(".tex")
    report = convert(a.source, output, config, standalone=a.standalone, workdir=a.workdir)
    c = report.counts()
    print(f"{'ok' if output.exists() else 'FAILED'}: {output}")
    print(f"report: {output.with_suffix('.report.md')} "
          f"(errors {c['error']}, warnings {c['warning']}, notes {c['info']})")
    return 0 if output.exists() else 1
