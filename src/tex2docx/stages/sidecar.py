"""Stage 10: write the companion file <out>.t2d.xml for the way back (docx2tex).

Status: implemented (M4 / ADR 0008). Labels get the bookmark names that
filters/numbers.lua uses, so that docx2tex can map bookmarks and REF fields back
to the author's labels even without live numbers.
"""

from __future__ import annotations

import re
from dataclasses import asdict

from ..context import Context
from ..sidecar import Sidecar
from ..stages.pandoc_run import caption_names
from ..texscan import document_language

STAGE = "sidecar"


def bookmark_name(label: str) -> str:
    return ("t2d_" + re.sub(r"[^A-Za-z0-9]", "_", label))[:40]


def run(ctx: Context) -> None:
    lang, _ = document_language(ctx.tex)
    sc = Sidecar(source=ctx.source.name, language=lang, profile=ctx.config.profile or "")
    names = caption_names(ctx)
    names["proof"] = ctx.config.proof_name
    sc.names = names
    for env, d in ctx.theorems.items():
        attrs = {k: str(v).lower() if isinstance(v, bool) else str(v)
                 for k, v in asdict(d).items() if k != "env" and v not in (None, "")}
        sc.theorems[env] = attrs
    for name, lab in ctx.labels.items():
        if name.startswith("t2d:auto:"):
            continue
        sc.labels[bookmark_name(name)] = name
        if lab.cref_type:
            sc.label_kinds[name] = lab.cref_type
    sc.macros = dict(ctx.config.macros)
    sc.cites = {num: key for key, num in ctx.bibcites.items()}
    path = Sidecar.path_for(ctx.output)
    sc.save(path)
    ctx.report.info(STAGE, "sidecar.written", path.name)
