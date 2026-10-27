"""Stage 7: render figure environments to PNG with the document's own preamble.

Status: implemented (M0) for environments listed in config.figure_envs.

How: insert the preview package before \\begin{document} in a copy of
ctx.latex_tex, compile -> one PDF page per environment (in source order),
rasterize with pdftoppm, then replace the i-th environment in ctx.tex by
\\includegraphics{figures/fig-i.png}. If page and match counts differ, nothing is
replaced and the report says so (wrong pictures are worse than none).
"""

from __future__ import annotations

import re

from ..context import Context
from ..tools import ToolError, latexmk, log_errors, require
from ..tools import run as run_tool

STAGE = "figures"


def _env_regex(envs: list[str]) -> re.Pattern[str]:
    alt = "|".join(re.escape(e) for e in envs)
    return re.compile(r"\\begin\{(" + alt + r")\}.*?\\end\{\1\}", re.S)


def run(ctx: Context) -> None:
    envs = ctx.config.figure_envs
    if not envs:
        return
    rx = _env_regex(envs)
    n = len(rx.findall(ctx.latex_tex))
    if n == 0:
        return
    d = ctx.workdir / "figures"
    d.mkdir(exist_ok=True)
    preamble = "\\usepackage[active,tightpage]{preview}\n" + "".join(
        f"\\PreviewEnvironment{{{e}}}\n" for e in envs
    )
    marker = "\\begin{document}"
    if marker not in ctx.latex_tex:
        ctx.report.error(STAGE, "figures.no-document-env")
        return
    tex = d / "figs.tex"
    tex.write_text(ctx.latex_tex.replace(marker, preamble + marker, 1), encoding="utf-8")
    try:
        proc = latexmk(tex, ctx.config.engine, search_dirs=[ctx.source_dir],
                       timeout=ctx.config.latex_timeout)
        pdf = d / "figs.pdf"
        if not pdf.exists():
            ctx.report.error(STAGE, "figures.compile-failed")
            for err in log_errors(d / "figs.log"):
                ctx.report.warn(STAGE, "latex.log", err)
            return
        if proc.returncode != 0:
            ctx.report.warn(STAGE, "figures.compile-errors")
        run_tool([require("pdftoppm"), "-r", str(ctx.config.figure_dpi), "-png",
                  pdf.name, "fig"], cwd=d)
    except ToolError as e:
        ctx.report.error(STAGE, "figures.tool", str(e))
        return

    pngs = sorted(d.glob("fig-*.png"), key=lambda p: int(p.stem.split("-")[-1]))
    if len(pngs) != n:
        ctx.report.error(STAGE, "figures.count-mismatch", f"envs={n} pages={len(pngs)}")
        return
    ctx.figures = pngs
    it = iter(pngs)
    # keep the line count (ctx.line_map, pandoc's line numbers): pad with the
    # newlines the environment occupied
    ctx.tex = rx.sub(
        lambda m: f"\\includegraphics{{figures/{next(it).name}}}" + "\n" * m.group(0).count("\n"),
        ctx.tex,
    )
    ctx.report.info(STAGE, "figures.rendered", str(n))
