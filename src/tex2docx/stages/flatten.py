"""Stage 1: inline \\input / \\include into one source text.

Status: implemented (M0); M2: every line of the result remembers its origin
(file, line) in ctx.line_map, so the report can point at the author's files.
A macro whose body is made of \\input/\\include (\\newcommand*{\\Source}{...} of
university templates) is expanded where it is used.

Invariant for later stages: whatever they do to ctx.tex / ctx.latex_tex must
keep the number of lines, or the map (and pandoc's line numbers) go stale.
"""

from __future__ import annotations

import re
from pathlib import Path

from ..context import Context
from ..report import Report
from ..texscan import blank_comment_lines, read_group
from . import StageError

STAGE = "flatten"
MAX_DEPTH = 20
_INPUT = re.compile(r"(?<!\\)\\(input|include|subfile)\s*\{([^{}]+)\}")

Origin = tuple[str, int]  # (path relative to the main file's dir, 1-based line)
# \newcommand*{\Source}{\include{a}\include{b}}: templates often gather the body in a macro
_DEF = re.compile(r"(?<!\\)\\(?:re)?newcommand\*?\s*\{?\\([A-Za-z]+)\}?\s*(?=\{)")


def hoist_include_macros(text: str, macros: dict[str, str]) -> str:
    """Record macros whose body contains \\input/\\include and empty their bodies
    (same line count). Their uses are expanded by flatten_lines at the call site,
    so the included files land where LaTeX puts them, not inside the definition."""
    out: list[str] = []
    last = 0
    for m in _DEF.finditer(text):
        try:
            body, end = read_group(text, m.end())
        except ValueError:
            continue
        if not _INPUT.search(body):
            continue
        macros[m.group(1)] = body
        out.append(text[last:m.end()])
        out.append("{}" + "\n" * body.count("\n"))
        last = end
    out.append(text[last:])
    return "".join(out)


def _resolve(name: str, base: Path) -> Path | None:
    cand = base / name.strip()
    for p in (cand, cand.with_name(cand.name + ".tex")):
        if p.is_file():
            return p
    return None


def flatten_lines(text: str, base: Path, report: Report, origin_name: str,
                  depth: int = 0, macros: dict[str, str] | None = None) -> tuple[list[str], list[Origin]]:
    """Inline included files line by line. Returns (lines, origin of each line).

    An \\input in the middle of a line splits it: the text before stays on the
    original line, the included file follows, the text after starts a new line
    (TeX reads it the same way). Paths resolve against the main file's dir, as LaTeX does.
    """
    if depth > MAX_DEPTH:
        report.error(STAGE, "flatten.too-deep", str(MAX_DEPTH))
        return [text], [(origin_name, 1)]
    if macros is None:
        macros = {}
    out: list[str] = []
    origins: list[Origin] = []
    text = hoist_include_macros(blank_comment_lines(text), macros)
    for n, line in enumerate(text.split("\n"), 1):
        for name, body in macros.items():
            if "\\" + name in line and not _DEF.search(line):  # not its own definition
                line = re.sub(r"(?<!\\)\\" + name + r"(?![A-Za-z])", lambda _: body.replace("\n", " "), line)
        pos = 0
        for m in _INPUT.finditer(line):
            path = _resolve(m.group(2), base)
            before = line[pos:m.start()]
            if path is None:
                report.warn(STAGE, "flatten.missing-input", m.group(2), line=len(out) + 1)
                continue  # the command stays in the text; LaTeX will complain too
            out.append(line[pos:m.start()])
            origins.append((origin_name, n))
            inner = path.read_text(encoding="utf-8", errors="replace")
            rel = str(path.relative_to(base)) if path.is_relative_to(base) else str(path)
            sub, sub_orig = flatten_lines(inner, base, report, rel, depth + 1, macros)
            out.extend(sub)
            origins.extend(sub_orig)
            pos = m.end()
        out.append(line[pos:])
        origins.append((origin_name, n))
    return out, origins


def flatten_text(text: str, base: Path, report: Report) -> str:
    return "\n".join(flatten_lines(text, base, report, "main")[0])


def run(ctx: Context) -> None:
    if not ctx.source.is_file():
        raise StageError("flatten.no-source", str(ctx.source))
    text = ctx.source.read_text(encoding="utf-8", errors="replace")
    if "\\documentclass" not in text:
        raise StageError("flatten.not-a-document", "no \\documentclass in main file")
    lines, origins = flatten_lines(text, ctx.source_dir, ctx.report, ctx.source.name)
    flat = "\n".join(lines)
    ctx.latex_tex = flat
    ctx.tex = flat
    ctx.line_map = origins
    ctx.report.line_map = origins
    ctx.report.main_file = ctx.source.name
    (ctx.workdir / "flat.tex").write_text(flat, encoding="utf-8")
