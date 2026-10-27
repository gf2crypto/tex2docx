"""Render formulas texmath cannot convert as pictures, with the document's preamble.

Status: implemented (M2). Called from stages/pandoc_run.py between its two passes.

The first pandoc pass (filters/mathimg.lua in "collect" mode) lists the failing
formulas. Here each one is typeset by real LaTeX inside the preview package,
one page per formula, in a copy of ctx.latex_tex whose body is replaced; pages
are rasterized by pdftoppm at config.figure_dpi. The second pandoc pass
replaces those formulas by the images. If the number of pages differs from the
number of formulas nothing is replaced (a wrong picture is worse than raw TeX).
config.math_fallback = "text" turns this off.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from ..context import Context
from ..tools import ToolError, latexmk, log_errors, require
from ..tools import run as run_tool

STAGE = "mathimg"
_BODY = re.compile(r"\\begin\{document\}.*\\end\{document\}", re.S)


def render(ctx: Context, failed: list[dict]) -> dict[str, str]:
    """Return {formula text: image path relative to ctx.workdir}; empty on any failure."""
    if not failed:
        return {}
    d = ctx.workdir / "mathimg"
    d.mkdir(exist_ok=True)
    body = ["\\begin{document}"]
    for f in failed:
        tex = f["text"].strip()
        inner = f"$\\displaystyle {tex}$" if f.get("display") else f"${tex}$"
        body.append(f"\\begin{{preview}}{inner}\\end{{preview}}")
    body.append("\\end{document}")
    src = ctx.latex_tex
    if not _BODY.search(src):
        ctx.report.error(STAGE, "mathimg.no-document-env")
        return {}
    src = src.replace("\\begin{document}",
                      "\\usepackage[active,tightpage]{preview}\n\\begin{document}", 1)
    src = _BODY.sub(lambda _: "\n".join(body), src)
    tex = d / "math.tex"
    tex.write_text(src, encoding="utf-8")
    try:
        latexmk(tex, ctx.config.engine, search_dirs=[ctx.source_dir],
                timeout=ctx.config.latex_timeout)
        pdf = d / "math.pdf"
        if not pdf.exists():
            ctx.report.error(STAGE, "mathimg.compile-failed")
            for err in log_errors(d / "math.log"):
                ctx.report.warn(STAGE, "latex.log", err)
            return {}
        run_tool([require("pdftoppm"), "-r", str(ctx.config.figure_dpi), "-png",
                  pdf.name, "m"], cwd=d)
    except ToolError as e:
        ctx.report.error(STAGE, "mathimg.tool", str(e))
        return {}
    pngs = sorted(d.glob("m-*.png"), key=lambda p: int(p.stem.split("-")[-1]))
    if len(pngs) != len(failed):
        ctx.report.error(STAGE, "mathimg.count-mismatch", f"formulas={len(failed)} pages={len(pngs)}")
        return {}
    images = {f["text"]: f"mathimg/{p.name}" for f, p in zip(failed, pngs)}
    ctx.report.info(STAGE, "mathimg.rendered", str(len(images)))
    return images


def load_failed(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        return []
