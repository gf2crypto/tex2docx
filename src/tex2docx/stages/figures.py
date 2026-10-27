"""Stage 7: render figure environments to PNG with the document's own preamble.

Status: implemented (M0) for environments listed in config.figure_envs;
M2: algorithm/algorithmic by default (pseudocode has no Word counterpart),
\\includegraphics without extension or in \\graphicspath resolved the way
LaTeX does, PDF/EPS images rasterized (Word cannot show them).

How: insert the preview package before \\begin{document} in a copy of
ctx.latex_tex, compile -> one PDF page per environment (in source order),
rasterize with pdftoppm, then replace the i-th environment in ctx.tex by
\\includegraphics{figures/fig-i.png}. If page and match counts differ, nothing is
replaced and the report says so (wrong pictures are worse than none).
"""

from __future__ import annotations

import re
from pathlib import Path

from ..context import Context
from ..tools import ToolError, latexmk, log_errors, require
from ..tools import run as run_tool

STAGE = "figures"


def outermost_spans(text: str, envs: list[str]) -> list[tuple[int, int]]:
    """(start, end) of every outermost environment from envs, in source order.
    Nested ones (algorithmic inside algorithm, procedure inside pcvstack) belong to
    the picture of their outer environment."""
    alt = "|".join(re.escape(e) for e in envs)
    tok = re.compile(r"\\(begin|end)\s*\{(" + alt + r")\}")
    spans: list[tuple[int, int]] = []
    depth = 0
    start = 0
    for m in tok.finditer(text):
        if m.group(1) == "begin":
            if depth == 0:
                start = m.start()
            depth += 1
        elif depth > 0:
            depth -= 1
            if depth == 0:
                spans.append((start, m.end()))
    return spans


def _wrap_preview(text: str, spans: list[tuple[int, int]]) -> str:
    out, last = [], 0
    for a, b in spans:
        out += [text[last:a], "\\begin{preview}", text[a:b], "\\end{preview}"]
        last = b
    out.append(text[last:])
    return "".join(out)


_GRAPHICSPATH = re.compile(r"(?<!\\)\\graphicspath\s*\{((?:\s*\{[^{}]*\}\s*)+)\}")
_EXTENSIONS = re.compile(r"(?<!\\)\\DeclareGraphicsExtensions\s*\{([^{}]*)\}")
_INCLUDE = re.compile(r"(?<!\\)\\includegraphics\s*(\[[^\]]*\])?\s*\{([^{}]+)\}")
DEFAULT_EXTS = [".pdf", ".png", ".jpg", ".jpeg", ".eps", ".PNG", ".JPG"]
# formats Word cannot show (or pandoc cannot embed): converted to PNG
CONVERT_EXTS = {".bmp", ".tif", ".tiff", ".gif", ".webp"}
FALLBACK_EXTS = DEFAULT_EXTS + sorted(CONVERT_EXTS) + [".BMP", ".TIF", ".TIFF", ".GIF"]


def to_png(src: Path, dst: Path) -> bool:
    """Convert a raster image to PNG with Pillow or ImageMagick, whichever is around."""
    try:
        from PIL import Image

        Image.open(src).convert("RGB").save(dst)
        return True
    except ImportError:
        pass
    except Exception:  # noqa: BLE001 - a broken file: fall through to ImageMagick
        pass
    import shutil

    tool = shutil.which("magick") or shutil.which("convert")
    if tool is None:
        return False
    run_tool([tool, str(src), str(dst)], cwd=dst.parent)
    return dst.is_file()


def resolve_graphics(ctx: Context) -> None:
    """Rewrite \\includegraphics{name} in ctx.tex to a path pandoc can open."""
    paths = [""]
    for m in _GRAPHICSPATH.finditer(ctx.tex):
        paths += re.findall(r"\{([^{}]*)\}", m.group(1))
    exts = DEFAULT_EXTS
    m = _EXTENSIONS.search(ctx.tex)
    if m:
        exts = [e.strip() for e in m.group(1).split(",") if e.strip()] + exts
    d = ctx.workdir / "figures"
    cache: dict[str, str] = {}

    def find(name: str) -> tuple[Path | None, bool]:
        """(path, substituted): substituted when the file was found under another extension."""
        for base in paths:
            cand = ctx.source_dir / base / name
            if cand.is_file():
                return cand, False
            if not cand.suffix or cand.suffix not in exts:
                for e in exts:
                    if (p := Path(str(cand) + e)).is_file():
                        return p, False
        # the named file is absent (LaTeX would fail too): same stem, another format
        for base in paths:
            stem = ctx.source_dir / base / name
            stem = stem.with_suffix("") if stem.suffix in FALLBACK_EXTS else stem
            for e in FALLBACK_EXTS:
                if (p := Path(str(stem) + e)).is_file():
                    return p, True
        return None, False

    def repl(m: re.Match[str]) -> str:
        name = m.group(2).strip()
        if name.startswith("figures/"):
            return m.group(0)  # our own rendered picture
        if name not in cache:
            path, substituted = find(name)
            if substituted:
                ctx.report.warn(STAGE, "figures.substituted", f"{name} -> {path.name}")
            if path is None:
                ctx.report.warn(STAGE, "figures.missing", name)
                cache[name] = name
            elif path.suffix.lower() in CONVERT_EXTS:
                d.mkdir(exist_ok=True)
                out = d / f"img-{len(cache)}.png"
                if to_png(path, out):
                    cache[name] = f"figures/{out.name}"
                    ctx.report.info(STAGE, "figures.converted", path.name)
                else:
                    ctx.report.warn(STAGE, "figures.unsupported-format", path.name)
                    cache[name] = name
            elif path.suffix.lower() in (".pdf", ".eps"):
                d.mkdir(exist_ok=True)
                out = d / f"img-{len(cache)}"
                try:
                    run_tool([require("pdftoppm"), "-r", str(ctx.config.figure_dpi), "-png",
                              "-singlefile", str(path), str(out)], cwd=ctx.workdir)
                    cache[name] = f"figures/{out.name}.png"
                    ctx.report.info(STAGE, "figures.rasterized", name)
                except ToolError as e:
                    ctx.report.warn(STAGE, "figures.tool", str(e))
                    cache[name] = name
            else:
                cache[name] = str(path.relative_to(ctx.source_dir)) \
                    if path.is_relative_to(ctx.source_dir) else str(path)
        return f"\\includegraphics{m.group(1) or ''}{{{cache[name]}}}"

    ctx.tex = _INCLUDE.sub(repl, ctx.tex)


def run(ctx: Context) -> None:
    render_environments(ctx)
    resolve_graphics(ctx)


def render_environments(ctx: Context) -> None:
    envs = ctx.config.figure_envs
    if not envs:
        return
    latex_spans = outermost_spans(ctx.latex_tex, envs)
    tex_spans = outermost_spans(ctx.tex, envs)
    n = len(latex_spans)
    if n == 0:
        return
    if len(tex_spans) != n:
        ctx.report.error(STAGE, "figures.views-differ", f"latex={n} pandoc={len(tex_spans)}")
        return
    d = ctx.workdir / "figures"
    d.mkdir(exist_ok=True)
    preamble = "\\usepackage[active,tightpage]{preview}\n"
    marker = "\\begin{document}"
    body_at = ctx.latex_tex.find(marker)
    if body_at < 0:
        ctx.report.error(STAGE, "figures.no-document-env")
        return
    # explicit preview environments around the outermost occurrences only:
    # \PreviewEnvironment would also typeset nested ones as extra pages
    tex = d / "figs.tex"
    wrapped = ctx.latex_tex[:body_at] + preamble + _wrap_preview(ctx.latex_tex, latex_spans)[body_at:]
    tex.write_text(wrapped, encoding="utf-8")
    try:
        proc = latexmk(tex, ctx.config.engine, search_dirs=[ctx.source_dir],
                       timeout=ctx.config.latex_timeout)
        pdf = d / "figs.pdf"
        if not pdf.exists():
            ctx.report.error(STAGE, "figures.compile-failed")
            for err in log_errors(d / "figs.log"):
                ctx.report.warn(STAGE, "latex.log", err)  # lines are off by the preview preamble
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
    # keep the line count (ctx.line_map, pandoc's line numbers): pad with the
    # newlines the environment occupied
    out, last = [], 0
    for (a, b), png in zip(tex_spans, pngs):
        out += [ctx.tex[last:a], f"\\includegraphics{{figures/{png.name}}}" + "\n" * ctx.tex[a:b].count("\n")]
        last = b
    out.append(ctx.tex[last:])
    ctx.tex = "".join(out)
    ctx.report.info(STAGE, "figures.rendered", str(n))
