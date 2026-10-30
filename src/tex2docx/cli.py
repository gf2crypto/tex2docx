"""Command line: tex2docx main.tex [-o out.docx] [--config cfg.yaml]."""

from __future__ import annotations

import argparse
from pathlib import Path

from . import __version__
from .config import Config
from .pipeline import convert


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="tex2docx", description="LaTeX -> Word (.docx)")
    p.add_argument("source", type=Path, nargs="?", help="main .tex file")
    p.add_argument("--check", action="store_true",
                   help="check that pandoc, TeX Live, poppler and Python packages are in place")
    p.add_argument("-o", "--output", type=Path, help="output .docx (default: next to source)")
    p.add_argument("-c", "--config", type=Path, help="YAML config")
    p.add_argument("--engine", choices=["pdflatex", "xelatex", "lualatex"],
                   help="override config.engine")
    p.add_argument("--profile", choices=["default", "standard"],
                   help="bundled Word template: standard = Times New Roman 14, 1.5 spacing, "
                        "no paragraph spacing, black headings")
    p.add_argument("--workdir", type=Path, help="keep intermediate files in this directory")
    p.add_argument("--keep-workdir", action="store_true",
                   help="do not delete the temporary working directory")
    p.add_argument("--version", action="version", version=f"tex2docx {__version__}")
    a = p.parse_args(argv)
    if a.check:
        from .check import main as check_main

        return check_main()
    if a.source is None:
        p.error("source .tex file is required (or --check)")

    config = Config.load(a.config)
    if a.engine:
        config.engine = a.engine
    if a.profile:
        config.profile = a.profile
    output = a.output or a.source.with_suffix(".docx")

    report = convert(a.source, output, config, workdir=a.workdir, keep_workdir=a.keep_workdir)
    c = report.counts()
    status = "FAILED" if not output.exists() else "ok"
    print(f"{status}: {output}")
    print(f"report: {output.with_suffix('.report.md')} "
          f"(errors {c['error']}, warnings {c['warning']}, notes {c['info']})")
    return 1 if not output.exists() else 0
