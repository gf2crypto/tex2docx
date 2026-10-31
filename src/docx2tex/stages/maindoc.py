"""Stage 1b (--into main.tex, M3): learn from the main document what the fragment must
fit: theorem declarations (titles -> environments), simple macros to fold back, the
language, the .bib files for citation keys. Sidecar and config still win where they
say something; the main document fills the gaps."""

from __future__ import annotations

from ..context import Context
from ..maindoc import read_main
from . import StageError

STAGE = "maindoc"


def run(ctx: Context) -> None:
    if ctx.main is None:
        return
    if not ctx.main.is_file():
        raise StageError("into.no-main", str(ctx.main))
    md = read_main(ctx.main)
    ctx.main_doc = md
    for env, attrs in md.theorems.items():
        ctx.sidecar.theorems.setdefault(env, attrs)
    for name, body in md.macros.items():
        ctx.sidecar.macros.setdefault(name, body)
    if not ctx.config.language and not ctx.sidecar.language and md.language:
        ctx.language = md.language
    ctx.report.info(STAGE, "into.main", ctx.main.name)
    if md.theorems:
        ctx.report.info(STAGE, "into.theorems", str(len(md.theorems)))
    if md.macros:
        ctx.report.info(STAGE, "into.macros", str(len(md.macros)))
    for p in md.bib_paths:
        ctx.report.info(STAGE, "into.bib", p.name)
