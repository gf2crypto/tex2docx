"""Stage 8: pandoc LaTeX -> docx with our Lua filters.

Status: implemented (M0).

Data for the filters goes through a JSON file whose path is passed as metadata
't2d-meta' (see filters/t2d.lua). Filters report problems by printing lines
'[t2d] <level> <code> <detail>' to stderr; they are collected into the report.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import asdict
from importlib import resources
from pathlib import Path

from ..context import Context
from ..tools import ToolError, require
from ..tools import run as run_tool
from . import StageError

STAGE = "pandoc"
FILTERS = ["crossref.lua", "theorems.lua", "equations.lua"]  # order matters

_SKIPPED = re.compile(r"Skipped '(.+?)' at (.+?) line (\d+)")
_MATH_FAIL = re.compile(r"^\[WARNING\] Could not convert TeX math")
_UNEXPECTED = re.compile(r"unexpected control sequence (\\[A-Za-z@]+)")
_T2D = re.compile(r"^\[t2d\] (info|warning|error) (\S+) ?(.*)$")

# Skipped by pandoc but irrelevant for the output (handled elsewhere or cosmetic).
HARMLESS_SKIPS = {
    "\\maketitle", "\\centering", "\\numberwithin", "\\theoremstyle",
    "\\NeedsTeXFormat", "\\ProvidesPackage", "\\ProvidesFile", "\\noindent",
    "\\bigskip", "\\medskip", "\\smallskip", "\\newpage", "\\clearpage",
}


def _pkg_path(*parts: str) -> Path:
    return Path(str(resources.files("tex2docx").joinpath(*parts)))


def _skipped_command(snippet: str) -> str:
    m = re.match(r"\\[A-Za-z@]+\*?|\\begin\{[^}]+\}", snippet)
    return m.group(0) if m else snippet[:20]


def collect_pandoc_messages(stderr: str, input_name: str, ctx: Context) -> None:
    """Turn pandoc/filter stderr into report items. Math text is never copied."""
    lines = stderr.splitlines()
    for i, line in enumerate(lines):
        if m := _SKIPPED.search(line):
            if not m.group(2).endswith(input_name):
                continue  # skipped inside a .sty pandoc read: package internals
            cmd = _skipped_command(m.group(1))
            if cmd not in HARMLESS_SKIPS:
                ctx.report.warn(STAGE, "pandoc.skipped", cmd, line=int(m.group(3)))
        elif _MATH_FAIL.match(line):
            culprit = "?"
            for follow in lines[i + 1 : i + 6]:
                if u := _UNEXPECTED.search(follow):
                    culprit = u.group(1)
                    break
            ctx.report.warn(STAGE, "pandoc.math-as-text", culprit)
        elif m := _T2D.match(line.strip()):
            ctx.report.add(m.group(1), "filter", m.group(2), m.group(3))


def run(ctx: Context) -> None:
    pandoc = require("pandoc")
    inp = ctx.workdir / "pandoc_input.tex"
    inp.write_text(ctx.tex, encoding="utf-8")
    meta = ctx.workdir / "t2d-meta.json"
    meta.write_text(json.dumps({
        "labels": {k: v.number for k, v in ctx.labels.items()},
        "theorems": {k: asdict(v) for k, v in ctx.theorems.items()},
        "proof_name": ctx.config.proof_name,
        "styles": ctx.config.theorem_styles,
    }, ensure_ascii=False), encoding="utf-8")

    ref = ctx.config.reference_docx or _pkg_path("data", "reference.docx")
    out = ctx.workdir / "pandoc.docx"
    # cwd = source dir: pandoc reads \usepackage'd .sty files relative to cwd
    # (not --resource-path), and that is how it sees local macro packages.
    cmd = [
        pandoc, str(inp), "-f", "latex", "-t", "docx", "-o", str(out),
        "--reference-doc", str(ref),
        "--resource-path", os.pathsep.join([str(ctx.workdir), str(ctx.source_dir)]),
        "-M", f"t2d-meta={meta}",
        "--verbose",
    ]
    for f in FILTERS:
        cmd += ["--lua-filter", str(_pkg_path("filters", f))]
    try:
        proc = run_tool(cmd, cwd=ctx.source_dir)
    except ToolError as e:
        raise StageError("pandoc.tool", str(e)) from e

    collect_pandoc_messages(proc.stderr, inp.name, ctx)
    if proc.returncode != 0 or not out.exists():
        tail = proc.stderr.strip().splitlines()[-1:] or ["no output"]
        raise StageError("pandoc.failed", tail[0][:200])
    ctx.docx = out
