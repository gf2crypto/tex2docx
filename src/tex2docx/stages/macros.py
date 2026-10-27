"""Stage 6: make user macros visible to pandoc.

Status: PARTIAL.
- done: manual overrides from config (`macros:`), injected as \\renewcommand
  right after \\begin{document}, so they win over earlier definitions;
- pandoc itself already reads \\newcommand from the document and from .sty
  files lying next to it (checked on pandoc 3.1);
- TODO (M2): styles found only via kpsewhich (personal texmf, e.g. a private
  class) are invisible to pandoc. Collect their \\newcommand/\\DeclareMathOperator
  definitions and inject them the same way. Never inject package internals
  (names with @).
"""

from __future__ import annotations

import re

from ..context import Context

STAGE = "macros"
_NAME = re.compile(r"^\\[A-Za-z]+$")


def run(ctx: Context) -> None:
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
        ctx.tex = ctx.tex.replace(marker, marker + "\n" + "\n".join(defs) + "\n", 1)
