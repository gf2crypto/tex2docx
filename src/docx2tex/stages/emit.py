"""Stage 4: write the fragment (and images), list what the main document must provide.

Status: implemented (M0). The fragment never carries \\usepackage or \\newtheorem:
needed packages go to the report (emit.package) and theorem environments used go to
emit.newtheorem, for the author to check against the main preamble.
--standalone additionally writes <out>.standalone.tex with a minimal preamble.
M2: pictures in formats LaTeX cannot include are converted (BMP/TIFF/GIF -> PNG with
Pillow; EMF/WMF -> PDF with LibreOffice when present, else images.unsupported).
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

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
    # macros folded back by normalize (the main document defines them; here we must)
    for name, body in sorted({**ctx.sidecar.macros, **ctx.config.macros}.items()):
        if re.search(re.escape(name) + r"(?![A-Za-z])", ctx.tex):
            head.append(f"\\newcommand{{{name}}}{{{body}}}")
    # the title block is commented out in the fragment (the main document has its own)
    body = re.sub(r"^% (\\(?:title|author|date)\{)", r"\1", ctx.tex, flags=re.M)
    return "\n".join(head) + "\n\\begin{document}\n" + body + "\\end{document}\n"


RASTER_TO_PNG = {".bmp", ".tif", ".tiff", ".gif", ".webp"}
VECTOR_TO_PDF = {".emf", ".wmf"}  # Word's own vector pictures: LibreOffice, if there is one


def convert_image(src: Path, dest: Path, ctx: Context) -> str:
    """Copy src into dest in a format LaTeX can include; returns the file name used."""
    ext = src.suffix.lower()
    if ext in RASTER_TO_PNG:
        from tex2docx.stages.figures import to_png

        target = dest / (src.stem + ".png")
        if to_png(src, target):
            ctx.report.info(STAGE, "images.converted", src.name)
            return target.name
    elif ext in VECTOR_TO_PDF:
        soffice = shutil.which("soffice") or shutil.which("libreoffice")
        if soffice:
            try:
                subprocess.run([soffice, "--headless", "--convert-to", "pdf", "--outdir", str(dest), str(src)],
                               capture_output=True, timeout=120, check=False)
            except (OSError, subprocess.TimeoutExpired):
                pass
            if (dest / (src.stem + ".pdf")).is_file():
                ctx.report.info(STAGE, "images.converted", src.name)
                return src.stem + ".pdf"
        ctx.report.warn(STAGE, "images.unsupported", src.name)
    shutil.copyfile(src, dest / src.name)
    return src.name


def run(ctx: Context) -> None:
    ctx.packages = needed_packages(ctx.tex)
    for p in ctx.packages:
        ctx.report.info(STAGE, "emit.package", p)
    for env, title in ctx.theorem_envs_used.items():
        ctx.report.info(STAGE, "emit.newtheorem", f"{env}:{title}")
    md = ctx.main_doc
    if md is not None:  # --into: what the main document's preamble still lacks
        for p in ctx.packages:
            if p not in md.packages and not (p == "amsthm" and "amsthm" in md.text):
                ctx.report.warn(STAGE, "into.missing-package", p)
        for env, title in ctx.theorem_envs_used.items():
            if env not in md.theorems:
                ctx.report.warn(STAGE, "into.missing-theorem", f"{env}:{title}")
        try:
            rel = ctx.output.relative_to(md.path.parent).with_suffix("").as_posix()
        except ValueError:
            rel = ctx.output.with_suffix("").as_posix()
        ctx.report.info(STAGE, "into.input", f"\\input{{{rel}}}")
    ctx.output.parent.mkdir(parents=True, exist_ok=True)
    ctx.output.write_text(ctx.tex, encoding="utf-8")
    media = ctx.workdir / "media"
    if media.is_dir():
        dest = ctx.output.parent / ctx.config.images_dir
        dest.mkdir(exist_ok=True)
        n = 0
        for f in sorted(media.rglob("*")):  # flat: normalize wrote <images_dir>/<name>
            if f.is_file():
                out_name = convert_image(f, dest, ctx)
                if out_name != f.name:
                    ctx.tex = ctx.tex.replace(f"{ctx.config.images_dir}/{f.name}", f"{ctx.config.images_dir}/{out_name}")
                n += 1
        if n:
            ctx.report.info(STAGE, "emit.images", str(n))
        ctx.output.write_text(ctx.tex, encoding="utf-8")
    if ctx.standalone:
        sa = ctx.output.with_suffix(".standalone.tex")
        sa.write_text(standalone(ctx), encoding="utf-8")
        ctx.report.info(STAGE, "emit.standalone", sa.name)
