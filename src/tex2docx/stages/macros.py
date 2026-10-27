"""Stage 6: make user macros visible to pandoc.

Status: implemented (M2).
- Definitions from personal packages and classes (found by kpsewhich outside
  the TeX distribution, see texmf.py) are inserted into ctx.tex right after the
  \\usepackage / \\documentclass that loads them, so later redefinitions in the
  document still win: \\newcommand, \\renewcommand, \\providecommand,
  \\DeclareMathOperator, \\newcommand-style \\def without parameters, and
  \\theoremstyle / \\newtheorem verbatim (pandoc builds theorem blocks from them).
  Definitions whose name or body uses internal names (with @) or #-parameters
  in \\def are not copied and go to the report (macros.skipped), so the author
  can override them in the config. A file with many definitions or mostly
  internal ones is a library, not the author's macros: skipped as a whole
  (macros.library).
- Manual overrides from config (`macros:`) are injected as \\renewcommand right
  after \\begin{document} and win over everything.
- pandoc itself reads \\newcommand from the document and from .sty files lying
  next to it.
"""

from __future__ import annotations

import re
from pathlib import Path

from ..context import Context
from ..texmf import package_requests, personal_packages
from ..texscan import read_group, read_optional, skip_ws

STAGE = "macros"
# A file with this many definitions, or mostly internal ones, is a library (biblatex,
# algorithmicx, ...) rather than the author's macros: nothing is copied from it.
LIBRARY_DEFS = 150
_NAME = re.compile(r"^\\[A-Za-z]+$")
_DEF = re.compile(
    r"(?<!\\)\\(newcommand|renewcommand|providecommand|DeclareMathOperator|def"
    r"|newtheorem|theoremstyle)(\*?)\s*"
)
_INTERNAL = re.compile(r"\\[A-Za-z]*@[A-Za-z@]*")


def extract_definitions(text: str) -> tuple[list[str], list[str]]:
    """(definitions to inject, names of skipped ones) from a .sty/.cls text."""
    defs: list[str] = []
    skipped: list[str] = []
    for m in _DEF.finditer(text):
        kind, star = m.group(1), m.group(2)
        pos = skip_ws(text, m.end())
        try:
            if kind in ("newtheorem", "theoremstyle"):
                _, pos = read_group(text, pos)
                if kind == "newtheorem":
                    opt, pos = read_optional(text, pos)
                    pos = skip_ws(text, pos)
                    _, pos = read_group(text, pos)
                    if opt is None:
                        _, pos = read_optional(text, pos)
                defs.append(text[m.start():pos])
                continue
            if kind == "def":
                nm = re.match(r"\\[A-Za-z]+", text[pos:])
                if not nm:
                    continue
                name = nm.group(0)
                pos += len(name)
                params = re.match(r"[^{]*", text[pos:]).group(0)
                if params.strip():  # \def\foo#1{...}: pandoc's \def has no parameters
                    skipped.append(name)
                    continue
                body, pos = read_group(text, pos)
                if "@" in name or _INTERNAL.search(body):
                    skipped.append(name)
                    continue
                defs.append(f"\\newcommand{{{name}}}{{{body}}}")
                continue
            if text[pos] == "{":
                name, pos = read_group(text, pos)
            else:
                nm = re.match(r"\\[A-Za-z@]+", text[pos:])
                if not nm:
                    continue
                name = nm.group(0)
                pos += len(name)
            name = name.strip()
            args, pos = read_optional(text, pos)
            default, pos = read_optional(text, pos) if args is not None else (None, pos)
            pos = skip_ws(text, pos)
            body, pos = read_group(text, pos)
            if "@" in name or _INTERNAL.search(body) or (default and "@" in default):
                skipped.append(name)
                continue
            head = f"\\{kind}{star}{{{name}}}"
            if args is not None:
                head += f"[{args}]"
                if default is not None:
                    head += f"[{default}]"
            defs.append(f"{head}{{{body}}}")
        except (ValueError, IndexError):
            continue
    return defs, skipped


_LOAD = re.compile(
    r"(?<!\\)\\(usepackage|documentclass)\s*(?:\[[^\]]*\])?\s*\{([^{}]+)\}"
)


def inject_definitions(text: str, packages: dict[str, Path], ctx: Context) -> str:
    """Insert each personal file's definitions after the command that loads it."""
    done: set[str] = set()

    def defs_for(name: str) -> list[str]:
        """Definitions of a file and, recursively, of the personal files it requires."""
        path = packages.get(name)
        if path is None or name in done:
            return []
        done.add(name)
        src = path.read_text(encoding="utf-8", errors="replace")
        out: list[str] = []
        for req, _ in package_requests(src):
            out.extend(defs_for(req))
        defs, skipped = extract_definitions(src)
        if len(defs) + len(skipped) > LIBRARY_DEFS or len(skipped) > len(defs):
            ctx.report.info(STAGE, "macros.library", f"{name}:{len(defs)}+{len(skipped)}")
            return out
        for s in skipped:
            ctx.report.warn(STAGE, "macros.skipped", f"{name}:{s}")
        if defs:
            ctx.report.info(STAGE, "macros.injected", f"{name}:{len(defs)}")
        out.extend(defs)
        return out

    def repl(m: re.Match[str]) -> str:
        ext = ".cls" if m.group(1) == "documentclass" else ".sty"
        defs: list[str] = []
        for name in m.group(2).split(","):
            defs.extend(defs_for(name.strip() + ext))
        if not defs:
            return m.group(0)
        return m.group(0) + " ".join(defs)  # same line: keeps ctx.line_map valid

    return _LOAD.sub(repl, text)


def run(ctx: Context) -> None:
    packages = personal_packages(ctx)
    if packages:
        ctx.tex = inject_definitions(ctx.tex, packages, ctx)

    overrides = ctx.config.macros
    if not overrides:
        return
    defs = []
    for name, repl in overrides.items():
        if not _NAME.match(name):
            ctx.report.warn(STAGE, "macros.bad-name", name)
            continue
        defs.append(f"\\renewcommand{{{name}}}{{{repl}}}")
    marker = "\\begin{document}"
    if marker in ctx.tex:
        ctx.tex = ctx.tex.replace(marker, marker + " ".join(defs), 1)
