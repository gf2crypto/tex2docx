"""Stage 4: collect \\newtheorem declarations and their amsthm styles.

Status: implemented (M0) for amsthm syntax. TODO: ntheorem/thmtools
(\\declaretheorem), see ROADMAP.md.

Sources, in order: local .sty/.cls next to the main file, then the document.
\\theoremstyle is sticky, as in LaTeX.
"""

from __future__ import annotations

import re

from ..context import Context, TheoremDecl
from ..texscan import read_group, read_optional, skip_ws

STAGE = "theorems"
_TOKEN = re.compile(r"(?<!\\)\\(theoremstyle|newtheorem)(\*?)")


def scan_decls(text: str, style: str = "plain") -> tuple[dict[str, TheoremDecl], str]:
    """Return (declarations, style in effect at the end of text)."""
    decls: dict[str, TheoremDecl] = {}
    for m in _TOKEN.finditer(text):
        try:
            pos = skip_ws(text, m.end())
            if m.group(1) == "theoremstyle":
                style, _ = read_group(text, pos)
                style = style.strip()
                continue
            env, pos = read_group(text, pos)
            counter, pos = read_optional(text, pos)
            pos = skip_ws(text, pos)
            title, pos = read_group(text, pos)
            within, pos = read_optional(text, pos) if counter is None else (None, pos)
            decls[env.strip()] = TheoremDecl(
                env=env.strip(), title=title.strip(), style=style,
                numbered=(m.group(2) != "*"), counter=counter, within=within,
            )
        except ValueError:
            continue
    return decls, style


def run(ctx: Context) -> None:
    style = "plain"
    for f in sorted(ctx.source_dir.glob("*.sty")) + sorted(ctx.source_dir.glob("*.cls")):
        found, style = scan_decls(f.read_text(encoding="utf-8", errors="replace"), style)
        ctx.theorems.update(found)
    found, _ = scan_decls(ctx.tex, style)
    ctx.theorems.update(found)
    if not ctx.theorems and "\\begin{proof}" in ctx.tex:
        ctx.report.warn(STAGE, "theorems.none-declared", "proof used, no \\newtheorem found")
