"""Stage 4: write the fragment (and images), list what the main document must provide.

Status: implemented (M0). The fragment never carries \\usepackage or \\newtheorem:
needed packages go to the report (emit.package) and theorem environments used go to
emit.newtheorem, for the author to check against the main preamble.
--standalone additionally writes <out>.standalone.tex with a minimal preamble.
"""

from __future__ import annotations

import re
import shutil

from ..context import Context

STAGE = "emit"
PACKAGE_HINTS: list[tuple[str, str]] = [
    (r"\\includegraphics", "graphicx"),
    (r"\\begin\{(align|gather|multline|equation\*|cases|split)", "amsmath"),
    (r"\\(mathbb|operatorname|text)\{", "amsmath"),
    (r"\\mathbb\{", "amssymb"),
    (r"\\(toprule|midrule|bottomrule)", "booktabs"),
    (r"\\begin\{proof\}|\\begin\{(theorem|lemma|definition|remark|corollary|proposition|example)\}", "amsthm"),
    (r"\\begin\{algorithmic\}", "algpseudocode"),
    (r"\\begin\{algorithm\}", "algorithm"),
    (r"\\url\{|\\href\{", "hyperref"),
    (r"\\begin\{longtable\}", "longtable"),
    (r"\\multirow", "multirow"),
]
BABEL = {"russian": "russian", "ukrainian": "ukrainian", "english": "english"}


def needed_packages(tex: str) -> list[str]:
    out: list[str] = []
    for pat, pkg in PACKAGE_HINTS:
        if re.search(pat, tex) and pkg not in out:
            out.append(pkg)
    return out


def standalone(ctx: Context) -> str:
    lang = BABEL.get(ctx.language, "english")
    pkgs = ["[T2A]{fontenc}", "[utf8]{inputenc}", f"[{lang}]{{babel}}"]
    pkgs += ["{" + p + "}" for p in ctx.packages]
    head = ["\\documentclass[12pt]{article}"] + ["\\usepackage" + p for p in pkgs]
    for env, title in sorted(ctx.theorem_envs_used.items()):
        head.append(f"\\newtheorem{{{env}}}{{{title}}}")
    return "\n".join(head) + "\n\\begin{document}\n" + ctx.tex + "\\end{document}\n"


def run(ctx: Context) -> None:
    ctx.packages = needed_packages(ctx.tex)
    for p in ctx.packages:
        ctx.report.info(STAGE, "emit.package", p)
    for env, title in ctx.theorem_envs_used.items():
        ctx.report.info(STAGE, "emit.newtheorem", f"{env}:{title}")
    ctx.output.parent.mkdir(parents=True, exist_ok=True)
    ctx.output.write_text(ctx.tex, encoding="utf-8")
    media = ctx.workdir / "media"
    if media.is_dir():
        dest = ctx.output.parent / ctx.config.images_dir
        dest.mkdir(exist_ok=True)
        n = 0
        for f in sorted(media.rglob("*")):  # flat: normalize wrote <images_dir>/<name>
            if f.is_file():
                shutil.copyfile(f, dest / f.name)
                n += 1
        if n:
            ctx.report.info(STAGE, "emit.images", str(n))
    if ctx.standalone:
        sa = ctx.output.with_suffix(".standalone.tex")
        sa.write_text(standalone(ctx), encoding="utf-8")
        ctx.report.info(STAGE, "emit.standalone", sa.name)
