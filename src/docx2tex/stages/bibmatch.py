"""Stage 3b (M3): the reference list of the docx against the main document's .bib.

structures.lua wrote \\begin{thebibliography} with \\bibitem{bib:N} (or the sidecar's
keys) and \\cite{bib:N}. With --into and a .bib in the main document every item is
matched to an entry (bibtex.match_entry); when all of them match, the block goes away
(the main document prints the bibliography) and the citations get the real keys.
One unmatched item: nothing is changed, the report says which (bib.unmatched).
"""

from __future__ import annotations

import re

from ..bibtex import match_entry
from ..context import Context

STAGE = "bibmatch"
_BLOCK = re.compile(r"\\begin\{thebibliography\}\{[^}]*\}\n(.*?)\\end\{thebibliography\}\n?", re.S)
_ITEM = re.compile(r"\\bibitem\{([^}]+)\}\s*(.*?)(?=\\bibitem\{|\Z)", re.S)


def run(ctx: Context) -> None:
    md = ctx.main_doc
    if md is None or not getattr(md, "bib_entries", None):
        return
    m = _BLOCK.search(ctx.tex)
    if not m:
        return
    keys = {e.key for e in md.bib_entries}
    mapping: dict[str, str] = {}
    unmatched: list[str] = []
    for key, text in _ITEM.findall(m.group(1)):
        if key in keys:
            mapping[key] = key
            continue
        e = match_entry(text, md.bib_entries)
        if e is None:
            unmatched.append(key)
        else:
            mapping[key] = e.key
    if unmatched:
        for key in unmatched:
            ctx.report.warn(STAGE, "bib.unmatched", key)
        return
    tex = ctx.tex[:m.start()] + ctx.tex[m.end():]

    def cite(mm: re.Match) -> str:
        new = ",".join(mapping.get(k.strip(), k.strip()) for k in mm.group(2).split(","))
        return mm.group(1) + "{" + new + "}"

    tex = re.sub(r"(\\cite(?:\[[^\]]*\])?)\{([^}]*)\}", cite, tex)
    ctx.tex = re.sub(r"\n{3,}", "\n\n", tex).strip() + "\n"
    ctx.report.info(STAGE, "bib.matched", str(len(mapping)))
