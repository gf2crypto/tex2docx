"""Stage 10: write the companion file <out>.t2d.xml for the way back (docx2tex).

Status: implemented (M4 / ADR 0008). Labels get the bookmark names that
filters/numbers.lua uses, so that docx2tex can map bookmarks and REF fields back
to the author's labels even without live numbers.
"""

from __future__ import annotations

import re
from dataclasses import asdict

from ..context import Context
from ..sidecar import Sidecar, embed
from ..stages.pandoc_run import caption_names
from ..texscan import document_language, read_group

STAGE = "sidecar"


def bookmark_name(label: str) -> str:
    return ("t2d_" + re.sub(r"[^A-Za-z0-9]", "_", label))[:40]


_SIMPLE = re.compile(r"(?<!\\)\\(?:newcommand|renewcommand|providecommand)\*?\s*\{?(\\[A-Za-z]+)\}?\s*(?!\[)")
_OPERATOR = re.compile(r"(?<!\\)\\DeclareMathOperator(\*?)\s*\{(\\[A-Za-z]+)\}\s*")


def simple_macros(tex: str) -> dict[str, str]:
    """Zero-argument macros of the document (and of the personal packages injected into
    ctx.tex): \\newcommand{\\F}{\\mathbb{F}}, \\DeclareMathOperator{\\rank}{rank}. docx2tex folds
    their bodies back into the names (stages/normalize.py: fold_macros)."""
    out: dict[str, str] = {}
    for m in _SIMPLE.finditer(tex):
        try:
            body, _ = read_group(tex, m.end())
        except ValueError:  # not a braced body
            continue
        if "#" not in body and body.strip().startswith("\\"):
            out[m.group(1)] = body.strip()
    for m in _OPERATOR.finditer(tex):
        try:
            body, _ = read_group(tex, m.end())
        except ValueError:
            continue
        out[m.group(2)] = "\\operatorname" + m.group(1) + "{" + body.strip() + "}"
    return out


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
    sc.macros = {**simple_macros(ctx.tex), **ctx.config.macros}
    sc.cites = {num: key for key, num in ctx.bibcites.items()}
    path = Sidecar.path_for(ctx.output)
    sc.save(path)
    ctx.report.info(STAGE, "sidecar.written", path.name)
    if ctx.output.is_file():
        part = embed(ctx.output, sc)
        ctx.report.info(STAGE, "sidecar.embedded", part)
