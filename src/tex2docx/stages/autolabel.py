"""Stage 2: give every numbered object a label, so LaTeX reports its number.

Status: NOT IMPLEMENTED (M1). See ROADMAP.md.

Spec:
- For every environment whose name is a numbered theorem (needs a pre-scan of
  \\newtheorem, i.e. run theorems.scan_decls first), equation, align (per line
  without \\notag/\\nonumber), gather, multline, figure, table: if it has no
  \\label, insert \\label{t2d:auto:N} right after \\begin{env}[opt] (for align -
  before each \\\\ of a numbered line).
- Apply the identical insertion to ctx.latex_tex and ctx.tex.
- Labels with prefix "t2d:auto:" are internal: crossref never prints them and
  the report never mentions them.
- Without this stage unlabeled theorems keep pandoc's own (wrong) numbers and
  the theorems filter reports "theorem.unlabeled".
"""

from __future__ import annotations

from ..context import Context

STAGE = "autolabel"


def run(ctx: Context) -> None:
    ctx.report.info(STAGE, "stage.not-implemented", STAGE)
