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
# multibbl: \bibliography{name}{files}{title}, \bibliographystyle{name}{style}, \cite{name}{keys}
_MULTIBBL = re.compile(r"(?<!\\)\\bibliography\s*\{(\w+)\}\s*\{([^{}]+)\}\s*\{([^{}]*)\}")
_NEWBIB = re.compile(r"(?<!\\)\\newbibliography\s*\{(\w+)\}")
_THEBIB = re.compile(r"(?<!\\)\\begin\s*\{thebibliography\}")
_DOTSLASH = re.compile(r"(?<!\\)(\\(?:bibliography|bibliographystyle|addbibresource)\s*(?:\{\w+\}\s*)?\{)\./")


def strip_dot_paths(text: str) -> str:
    """\\bibliography{./bibtex/refs} -> \\bibliography{bibtex/refs}: BibTeX runs in the
    output directory and resolves './' there, while BIBINPUTS/BSTINPUTS do find
    'bibtex/refs' under the document's directory."""
    return _DOTSLASH.sub(r"\1", text)


def multibbl_names(text: str) -> list[str]:
    return [m.group(1) for m in _NEWBIB.finditer(text)]


def is_bibtex(ctx: Context) -> bool:
    """BibTeX (\\bibliography, incl. multibbl) rather than biblatex: the list comes from
    the .bbl that LaTeX produced (formatted by the .bst, exactly as in the PDF)."""
    return (_BIBLIOGRAPHY.search(ctx.latex_tex) or _MULTIBBL.search(ctx.latex_tex)) \
        and not _ADDBIB.search(ctx.latex_tex)


def bbl_lists(ctx: Context) -> dict[str, str]:
    """Formatted thebibliography environments from the LaTeX run: name -> text.
    'main' for the standard \\bibliography, the multibbl name otherwise."""
    d = ctx.workdir / "latex"
    out: dict[str, str] = {}
    for bbl in sorted(d.glob("*.bbl")):
        text = bbl.read_text(encoding="utf-8", errors="replace")
        if "\\bibitem" in text:
            out[bbl.stem] = text
    return out

BIB_TITLES = {  # babel language -> heading, as \bibname / \refname of babel
    "russian": "Список литературы",
    "ukrainian": "Список літератури",
    "english": "References",
}
ABSTRACT_TITLES = {"russian": "Аннотация", "ukrainian": "Анотація", "english": "Abstract"}
KEYWORDS_TITLES = {"russian": "Ключевые слова", "ukrainian": "Ключові слова", "english": "Keywords"}


def bib_files(ctx: Context) -> list[Path]:
    """Existing .bib files the document loads, in order; missing ones are reported."""
    names: list[str] = []
    for m in _ADDBIB.finditer(ctx.latex_tex):
        names.append(m.group(1).strip())
    multi = {m.group(1) for m in _NEWBIB.finditer(ctx.latex_tex)}
    for m in _BIBLIOGRAPHY.finditer(ctx.latex_tex):
        if m.group(1).strip() in multi:
            continue  # multibbl: files are in the second argument
        names += [n.strip() for n in m.group(1).split(",") if n.strip()]
    for m in _MULTIBBL.finditer(ctx.latex_tex):
        names += [n.strip() for n in m.group(2).split(",") if n.strip()]
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
