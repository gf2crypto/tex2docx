"""Command line: tex2docx main.tex [-o out.docx] [--config cfg.yaml]."""

from __future__ import annotations

import argparse
from pathlib import Path

from . import __version__
from .config import Config
from .pipeline import convert


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="tex2docx", description="LaTeX -> Word (.docx)")
    p.add_argument("source", type=Path, help="main .tex file")
    p.add_argument("-o", "--output", type=Path, help="output .docx (default: next to source)")
    p.add_argument("-c", "--config", type=Path, help="YAML config")
    p.add_argument("--engine", choices=["pdflatex", "xelatex", "lualatex"],
                   help="override config.engine")
    p.add_argument("--workdir", type=Path, help="keep intermediate files in this directory")
    p.add_argument("--keep-workdir", action="store_true",
                   help="do not delete the temporary working directory")
    p.add_argument("--version", action="version", version=f"tex2docx {__version__}")
    a = p.parse_args(argv)

    config = Config.load(a.config)
    if a.engine:
        config.engine = a.engine
    output = a.output or a.source.with_suffix(".docx")

    report = convert(a.source, output, config, workdir=a.workdir, keep_workdir=a.keep_workdir)
    c = report.counts()
    status = "FAILED" if not output.exists() else "ok"
    print(f"{status}: {output}")
    print(f"report: {output.with_suffix('.report.md')} "
          f"(errors {c['error']}, warnings {c['warning']}, notes {c['info']})")
    return 1 if not output.exists() else 0
