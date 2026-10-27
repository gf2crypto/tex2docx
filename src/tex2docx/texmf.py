"""Packages and classes the document loads from the user's own texmf trees.

pandoc only reads .sty files lying next to the document. Anything LaTeX finds
elsewhere - a personal class in ~/texmf, a package in TEXMFLOCAL - is invisible
to it. We ask kpsewhich where every \\usepackage / \\documentclass / \\RequirePackage
file lives and keep those that are neither in the distribution (TEXMFDIST,
TEXMFMAIN) nor next to the source: their definitions are what pandoc misses.
"""

from __future__ import annotations

import re
from pathlib import Path

from .context import Context
from .tools import ToolError, kpsewhich, tex_env, texmf_var

_USE = re.compile(
    r"(?<!\\)\\(usepackage|RequirePackage|documentclass|LoadClass)\s*(?:\[[^\]]*\])?\s*\{([^{}]+)\}"
)
MAX_FILES = 50


def package_requests(text: str) -> list[tuple[str, str]]:
    """(file name with extension, source command) for every package/class the text loads."""
    out: list[tuple[str, str]] = []
    for m in _USE.finditer(text):
        ext = ".cls" if m.group(1) in ("documentclass", "LoadClass") else ".sty"
        for name in m.group(2).split(","):
            name = name.strip()
            if name and not name.startswith("#"):
                out.append((name + ext, m.group(1)))
    return out


def personal_packages(ctx: Context) -> dict[str, Path]:
    """Resolve once: file name -> path, for files outside the distribution and the source dir.

    Packages required by those files are followed recursively.
    """
    if ctx.packages is not None:
        return ctx.packages
    ctx.packages = {}
    env = tex_env(ctx.source_dir)
    try:
        dist = {texmf_var(v, cwd=ctx.source_dir, env=env) for v in ("TEXMFDIST", "TEXMFMAIN")}
    except ToolError as e:
        ctx.report.warn("macros", "macros.tool", str(e))
        return ctx.packages
    dist.discard("")

    def is_distribution(p: Path) -> bool:
        s = str(p)
        return any(s.startswith(d) for d in dist)

    queue = [name for name, _ in package_requests(ctx.tex)]
    seen: set[str] = set()
    while queue and len(seen) < MAX_FILES:
        batch = [n for n in queue if n not in seen]
        queue = []
        seen.update(batch)
        if not batch:
            break
        try:
            found = kpsewhich(batch, cwd=ctx.source_dir, env=env)
        except ToolError as e:
            ctx.report.warn("macros", "macros.tool", str(e))
            break
        for name, path in found.items():
            if is_distribution(path) or path.parent == ctx.source_dir:
                continue
            ctx.packages[name] = path
            text = path.read_text(encoding="utf-8", errors="replace")
            queue.extend(n for n, _ in package_requests(text))
    return ctx.packages
