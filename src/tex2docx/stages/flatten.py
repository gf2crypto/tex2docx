"""Stage 1: inline \\input / \\include into one source text.

Status: implemented (M0).
"""

from __future__ import annotations

import re
from pathlib import Path

from ..context import Context
from ..report import Report
from ..texscan import blank_comment_lines, line_of
from . import StageError

STAGE = "flatten"
MAX_DEPTH = 20
_INPUT = re.compile(r"(?<!\\)\\(input|include|subfile)\s*\{([^{}]+)\}")


def _resolve(name: str, base: Path) -> Path | None:
    cand = base / name.strip()
    for p in (cand, cand.with_name(cand.name + ".tex")):
        if p.is_file():
            return p
    return None


def flatten_text(text: str, base: Path, report: Report, depth: int = 0) -> str:
    """Recursively inline included files. Paths resolve against the main file's dir,
    as LaTeX does."""
    if depth > MAX_DEPTH:
        report.error(STAGE, "flatten.too-deep", str(MAX_DEPTH))
        return text
    text = blank_comment_lines(text)

    def repl(m: re.Match[str]) -> str:
        name = m.group(2)
        path = _resolve(name, base)
        if path is None:
            report.warn(STAGE, "flatten.missing-input", name, line=line_of(text, m.start()))
            return ""
        inner = path.read_text(encoding="utf-8", errors="replace")
        return flatten_text(inner, base, report, depth + 1)

    return _INPUT.sub(repl, text)


def run(ctx: Context) -> None:
    if not ctx.source.is_file():
        raise StageError("flatten.no-source", str(ctx.source))
    text = ctx.source.read_text(encoding="utf-8", errors="replace")
    if "\\documentclass" not in text:
        raise StageError("flatten.not-a-document", "no \\documentclass in main file")
    flat = flatten_text(text, ctx.source_dir, ctx.report)
    ctx.latex_tex = flat
    ctx.tex = flat
    (ctx.workdir / "flat.tex").write_text(flat, encoding="utf-8")
