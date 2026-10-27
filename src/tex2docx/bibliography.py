"""Where the document's bibliography comes from (ADR 0005).

biblatex: \\addbibresource{x.bib} + \\printbibliography; BibTeX: \\bibliography{a,b} +
\\bibliographystyle; manual: thebibliography. Resolution reads the untouched
ctx.latex_tex; the rewriting for pandoc is done in stages/normalize.py.
"""

from __future__ import annotations

import re
from pathlib import Path

from .context import Context

_ADDBIB = re.compile(r"(?<!\\)\\addbibresource\s*(?:\[[^\]]*\])?\s*\{([^{}]+)\}")
_BIBLIOGRAPHY = re.compile(r"(?<!\\)\\bibliography\s*\{([^{}]+)\}")
_THEBIB = re.compile(r"(?<!\\)\\begin\s*\{thebibliography\}")

BIB_TITLES = {  # babel language -> heading, as \bibname / \refname of babel
    "russian": "Список литературы",
    "ukrainian": "Список літератури",
    "english": "References",
}
ABSTRACT_TITLES = {"russian": "Аннотация", "ukrainian": "Анотація", "english": "Abstract"}


def bib_files(ctx: Context) -> list[Path]:
    """Existing .bib files the document loads, in order; missing ones are reported."""
    names: list[str] = []
    for m in _ADDBIB.finditer(ctx.latex_tex):
        names.append(m.group(1).strip())
    for m in _BIBLIOGRAPHY.finditer(ctx.latex_tex):
        names += [n.strip() for n in m.group(1).split(",") if n.strip()]
    out: list[Path] = []
    for name in names:
        cand = ctx.source_dir / name
        for p in (cand, cand.with_name(cand.name + ".bib")):
            if p.is_file():
                out.append(p)
                break
        else:
            ctx.report.warn("bibliography", "bibliography.missing-bib", name)
    return out


def has_thebibliography(ctx: Context) -> bool:
    return _THEBIB.search(ctx.latex_tex) is not None
