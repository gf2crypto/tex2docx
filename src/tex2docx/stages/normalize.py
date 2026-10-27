"""Stage 5: rewrite constructs pandoc misreads, in ctx.tex only.

Status: implemented (M0): babel shorthands of Russian/Ukrainian.
pandoc renders '"---' as a literal quote plus dash; LaTeX never shows the quote.
M1: alignat/flalign become align (pandoc leaves alignat's column count in the
formula text and does not know flalign at all); numbering is the same.
\\cref/\\Cref become \\ref{cref:...} for crossref.lua (pandoc would lose the distinction).
Theorem declarations of thmtools and ntheorem are rewritten into plain amsthm
(stages/theorems.theorems_to_amsthm): pandoc knows only amsthm.
Bibliography commands become the marker \\label{t2d:refs}, thebibliography an
enumerate (ADR 0005).
The subequations wrapper is removed (pandoc folds it into one formula): the
inner environments keep their labels and LaTeX has already numbered them 2.3a,
2.3b; references to the wrapper's own label resolve through the .aux anyway.
"""

from __future__ import annotations

import re

from ..texscan import read_group
from ..bibliography import bbl_lists, is_bibtex, multibbl_names
from ..context import Context
from .theorems import theorems_to_amsthm

STAGE = "normalize"

# Order matters: longer shorthands first. (?<!\\) keeps the \" accent intact.
BABEL_SHORTHANDS: list[tuple[str, str]] = [
    (r'(?<!\\)"---', "---"),
    (r'(?<!\\)"--~', "--"),
    (r'(?<!\\)"--\*', "--"),
    (r'(?<!\\)"~', "-"),
    (r'(?<!\\)"=', "-"),
    (r'(?<!\\)"<', "«"),
    (r'(?<!\\)">', "»"),
    (r'(?<!\\)"`', "„"),
    (r"(?<!\\)\"'", "“"),
    (r'(?<!\\)""', ""),
    (r"(?<![<\\])<<(?!<)", "«"),  # T2A ligatures / fontspec Ligatures=TeX
    (r"(?<![>\\])>>(?!>)", "»"),
]


# \begin{alignat}{2} / \begin{flalign} -> \begin{align}; same for the starred forms.
MATH_ENVS: list[tuple[str, str]] = [
    (r"(?<!\\)\\(begin|end)\{alignat(\*?)\}(?:\{\d+\})?", r"\\\1{align\2}"),
    (r"(?<!\\)\\(begin|end)\{flalign(\*?)\}", r"\\\1{align\2}"),
    (r"(?<!\\)\\begin\{subequations\}(?:\s*\\label\s*\{[^{}]*\})?", ""),
    (r"(?<!\\)\\end\{subequations\}", ""),
]

# Bibliography (ADR 0005): the place of the list becomes a marker label that
# bibliography.lua turns into a heading + Div#refs; thebibliography becomes enumerate.
BIBLIOGRAPHY: list[tuple[str, str]] = [
    (r"(?<!\\)\\printbibliography\*?(?:\s*\[[^\]]*\])?", r"\\label{t2d:refs}"),
    (r"(?<!\\)\\bibliography\s*\{[^{}]*\}", r"\\label{t2d:refs}"),
    (r"(?<!\\)\\bibliographystyle\s*\{[^{}]*\}", ""),
    (r"(?<!\\)\\begin\s*\{thebibliography\}\s*\{[^{}]*\}", r"\\label{t2d:refs}\\begin{enumerate}"),
    (r"(?<!\\)\\end\s*\{thebibliography\}", r"\\end{enumerate}"),
    (r"(?<!\\)\\bibitem\s*(?:\[[^\]]*\])?\s*\{[^{}]*\}", r"\\item"),
]

# figure*/table* (two-column floats) are unknown to pandoc: plain floats for it
FLOATS: list[tuple[str, str]] = [
    (r"(?<!\\)\\(begin|end)\{(figure|table)\*\}", r"\\\1{\2}"),
    (r"(?<!\\)\\(begin|end)\{IEEEkeywords\}", r"\\\1{t2dkeywords}"),
]

# abstract: pandoc moves it into metadata (printed first, titled "Abstract");
# renamed so that it stays in place and gets the babel heading (lists.lua).
ABSTRACT: list[tuple[str, str]] = [
    (r"(?<!\\)\\(begin|end)\{abstract\}", r"\\\1{t2dabstract}"),
]

# cleveref: pandoc turns \cref into a plain \ref and drops \Cref; mark them so that
# crossref.lua can build "теорема 1.1" from the type recorded in the .aux.
CREF: list[tuple[str, str]] = [
    (r"(?<!\\)\\(cref|Cref)\*?\s*\{([^{}]+)\}", r"\\ref{\1:\2}"),
    (r"(?<!\\)\\(cref|Cref)range\*?\s*\{([^{}]+)\}\s*\{([^{}]+)\}", r"\\ref{\1range:\2,\3}"),
]


def normalize_text(text: str) -> str:
    for pat, rep in BABEL_SHORTHANDS + MATH_ENVS + CREF + BIBLIOGRAPHY + ABSTRACT + FLOATS:
        text = re.sub(pat, rep, text)
    return theorems_to_amsthm(text)


# gost*.bst / babel helpers that appear in .bbl files, for pandoc
BBL_MACROS: list[tuple[str, str]] = [
    (r"\\selectlanguageifdefined\s*\{\w+\}", ""),
    (r"\\BibEmph\b", r"\\emph"),
    (r"\\BibUrl\b", r"\\url"),
    (r"\\BibAnnote\s*\{[^{}]*\}", ""),
    (r"\\BibDash\b\s*", "— "),
    (r"\\cyrdash\b\s*", "— "),
    (r"\\newblock\b\s*", ""),
]


def _one_line(bbl: str) -> str:
    """A .bbl as one line (keeps ctx.line_map valid), without the macro preamble that
    .bst files put before the first \\bibitem; '%' line ends are continuations."""
    first = bbl.find("\\bibitem")
    head = re.search(r"\\begin\s*\{thebibliography\}\s*\{[^{}]*\}", bbl)
    if first >= 0 and head and head.end() < first:
        bbl = bbl[:head.end()] + "\n" + bbl[first:]
    for pat, rep in BBL_MACROS:
        bbl = re.sub(pat, rep, bbl)
    out = []
    for ln in bbl.splitlines():
        ln = ln.rstrip()
        out.append(ln[:-1] if ln.endswith("%") else ln + " ")
    return "".join(out)


def inline_bibtex_lists(ctx: Context) -> None:
    """BibTeX: put the formatted lists from the .bbl files where \\bibliography stands
    (ADR 0005). multibbl: \\bibliography{name}{files}{title} gets its own title,
    \\cite{name}{keys} becomes \\cite{keys}."""
    lists = bbl_lists(ctx)
    if not lists:
        ctx.report.warn(STAGE, "bibliography.no-bbl", "BibTeX list not produced by LaTeX")
        return
    names = multibbl_names(ctx.tex)

    def multi(m: re.Match[str]) -> str:
        name, title = m.group(1), m.group(3).strip()
        body = lists.get(name)
        if body is None:
            ctx.report.warn(STAGE, "bibliography.no-bbl", name)
            return m.group(0)
        body = _one_line(body)  # preamble of the .bst dropped first
        body = re.sub(r"\\begin\s*\{thebibliography\}\s*\{[^{}]*\}", r"\\begin{enumerate}", body)
        body = re.sub(r"\\end\s*\{thebibliography\}", r"\\end{enumerate}", body)
        body = re.sub(r"\\bibitem\s*(?:\[[^\]]*\])?\s*\{[^{}]*\}", r"\\item", body)
        head = f"\\section*{{{title}}} " if title else ""
        return head + body

    def single(m: re.Match[str]) -> str:
        body = lists.get("main")
        if body is None:
            ctx.report.warn(STAGE, "bibliography.no-bbl", "main")
            return m.group(0)
        return _one_line(body)  # thebibliography rules add the heading marker

    if names:
        alt = "|".join(map(re.escape, names))
        ctx.tex = re.sub(r"(?<!\\)\\bibliography\s*\{(" + alt + r")\}\s*\{([^{}]+)\}\s*\{([^{}]*)\}",
                         multi, ctx.tex)
        ctx.tex = re.sub(r"(?<!\\)\\(cite\w*)\s*\{(?:" + alt + r")\}\s*(\[[^\]]*\])?\s*\{", r"\\\1\2{", ctx.tex)
        ctx.tex = re.sub(r"(?<!\\)\\nocite\s*\{(?:" + alt + r")\}\s*\{[^{}]*\}", "", ctx.tex)
        ctx.tex = re.sub(r"(?<!\\)\\bibliographystyle\s*\{(?:" + alt + r")\}\s*\{[^{}]*\}", "", ctx.tex)
        ctx.tex = re.sub(r"(?<!\\)\\newbibliography\s*\{\w+\}", "", ctx.tex)
    else:
        ctx.tex = re.sub(r"(?<!\\)\\bibliography\s*\{[^{}]*\}", single, ctx.tex)
    ctx.report.info(STAGE, "bibliography.bbl", str(len(lists)))


def second_title_block(text: str) -> str:
    """A second \\title/\\author after \\maketitle (journal classes: \\maketitleeng, an
    English title block) would turn pandoc's title metadata into a list, which the
    docx writer drops. Those become centered paragraphs; \\maketitleeng goes."""
    first = re.search(r"(?<!\\)\\maketitle\b", text)
    if not first:
        return text
    head, body = text[:first.end()], text[first.end():]

    def block(m: re.Match[str]) -> str:
        try:
            inner, end = read_group(body, m.end())
        except ValueError:
            return m.group(0)
        bold = m.group(1) == "title"
        content = f"\\textbf{{{inner}}}" if bold else inner
        return f"\\begin{{center}}{content}\\end{{center}}"

    out = []
    pos = 0
    for m in re.finditer(r"(?<!\\)\\(title|author)\s*(?=\{)", body):
        if m.start() < pos:
            continue
        try:
            _, end = read_group(body, m.end())
        except ValueError:
            continue
        out.append(body[pos:m.start()])
        out.append(block(m))
        pos = end
    out.append(body[pos:])
    body = "".join(out)
    body = re.sub(r"(?<!\\)\\maketitle(eng|rus|en|ru)\b", "", body)
    return head + body


def run(ctx: Context) -> None:
    ctx.tex = second_title_block(ctx.tex)
    if is_bibtex(ctx):
        inline_bibtex_lists(ctx)
    ctx.tex = normalize_text(ctx.tex)
