"""Stage 3: compile with real LaTeX and read numbering from .aux.

Status: implemented (M0). Failure is not fatal: conversion continues with
pandoc's own numbering, and the report says so.
"""

from __future__ import annotations

import re

from ..aux import parse_aux
from ..context import Context
from ..tools import ToolError, latexmk, log_errors

STAGE = "latex"
_FLAT_LINE = re.compile(r"^\./main\.tex:(\d+):")


def located(err: str, ctx: Context) -> tuple[str, int | None]:
    """'./main.tex:20: ...' (a line of the flattened text) -> ('...', 20)."""
    m = _FLAT_LINE.match(err)
    if not m:
        return err, None
    return err[m.end():].strip(), int(m.group(1))


def run(ctx: Context) -> None:
    d = ctx.workdir / "latex"
    d.mkdir(exist_ok=True)
    tex = d / "main.tex"
    tex.write_text(ctx.latex_tex, encoding="utf-8")
    try:
        proc = latexmk(tex, ctx.config.engine, search_dirs=[ctx.source_dir],
                       timeout=ctx.config.latex_timeout)
    except ToolError as e:
        ctx.report.error(STAGE, "latex.tool", str(e))
        return
    if proc.returncode != 0:
        ctx.report.warn(STAGE, "latex.compile-errors", ctx.config.engine)
        for err in log_errors(d / "main.log"):
            msg, line = located(err, ctx)
            ctx.report.warn(STAGE, "latex.log", msg, line=line)
    ctx.labels = parse_aux(d / "main.aux")
    if not ctx.labels:
        ctx.report.warn(STAGE, "latex.no-labels", "numbering falls back to pandoc")
