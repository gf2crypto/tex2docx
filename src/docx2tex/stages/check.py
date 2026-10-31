"""Stage 5 (--standalone only): compile the standalone document as a self-check.

Status: implemented (M0). Errors go to the report (check.compile-errors + log lines).
"""

from __future__ import annotations

import shutil

from tex2docx.tools import ToolError, latexmk, log_errors

from ..context import Context

STAGE = "check"


def run(ctx: Context) -> None:
    if not ctx.standalone:
        return
    d = ctx.workdir / "check"
    d.mkdir(exist_ok=True)
    tex = d / "main.tex"
    tex.write_text(ctx.output.with_suffix(".standalone.tex").read_text(encoding="utf-8"),
                   encoding="utf-8")
    images = ctx.output.parent / ctx.config.images_dir
    if images.is_dir():
        shutil.copytree(images, d / ctx.config.images_dir, dirs_exist_ok=True)
    try:
        proc = latexmk(tex, ctx.config.engine, search_dirs=[d], timeout=600)
    except ToolError as e:
        ctx.report.warn(STAGE, "check.tool", str(e))
        return
    if proc.returncode != 0 or not (d / "main.pdf").exists():
        ctx.report.error(STAGE, "check.compile-errors", ctx.config.engine)
        for err in log_errors(d / "main.log"):
            ctx.report.warn(STAGE, "latex.log", err)
    else:
        ctx.report.info(STAGE, "check.compiled", "")
