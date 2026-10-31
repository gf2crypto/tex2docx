"""Stage 3: Word/pandoc artefacts -> the LaTeX an author would write.

Status: implemented (M0):
- \\(x\\) -> $x$; \\[ \\] kept; pandoc's \\hypertarget wrappers and \\def\\labelenumi removed;
- media/<file> paths -> <images_dir>/<file>;
- M2: macros of the main document (sidecar <macros>, config macros:) folded back:
  \\mathbf{G} -> \\matr{G}, see fold_macros;
- \\texorpdfstring, \\protect, \\tightlist, empty paragraphs, double blank lines;
- U+00A0 -> ~, trailing spaces. Idempotent: running it twice changes nothing (tested).
"""

from __future__ import annotations

import re

from ..context import Context

STAGE = "normalize"

RULES: list[tuple[str, str]] = [
    (r"\\hypertarget\{[^{}]*\}\{%\n", ""),          # \hypertarget{id}{%  ...}}
    (r"\\label\{ux[0-9a-z\-]*\}\}", ""),            # ...\label{ux...}} of the same wrapper
    (r"\\def\\labelenumi\{[^{}]*\}\n?", ""),
    (r"\\tightlist\n?", ""),
    (r"\\protect\\hyperlink\{[^{}]*\}\{([^{}]*)\}", r"\1"),
    (r"\\texorpdfstring\{([^{}]*)\}\{[^{}]*\}", r"\1"),
    (r"\\\((.+?)\\\)", r"$\1$"),
    (r"\u00a0", "~"),
    # our own environments: no blank line right after \\begin{...} and before \\end{...}
    (r"(\\begin\{[a-z*]+\}(?:\[[^\]\n]*\])?(?:\\label\{[^}]*\})*)\n\n", r"\1\n"),
    (r"\n\n(\\end\{[a-z*]+\})", r"\n\1"),
    (r"[ \t]+\n", "\n"),
    (r"\n{3,}", "\n\n"),
]


def normalize_text(text: str, images_dir: str = "images") -> str:
    for pat, rep in RULES:
        text = re.sub(pat, rep, text, flags=re.S if pat.startswith(r"\\\(") else 0)
    # pandoc extracts to media/media/<file> (its own subfolder inside ours)
    text = re.sub(r"\{(?:[^{}]*/)?media/(?:media/)?([^{}/]+)\}",
                  lambda m: "{" + images_dir + "/" + m.group(1) + "}", text)
    text = re.sub(r"\\includegraphics\[[^\]]*\]", r"\\includegraphics", text)
    return text.strip() + "\n"


def fold_macros(text: str, macros: dict[str, str]) -> tuple[str, int, list[str]]:
    """\\mathbf{G} -> \\matr{G} for macros {"\\matr": "\\mathbf"}: the author's own notation
    back. Only command-like bodies without parameters; a body shared by several names is
    left alone (ambiguous). Returns (text, replacements, ambiguous names)."""
    by_body: dict[str, list[str]] = {}
    for name, body in macros.items():
        body = body.strip()
        if re.fullmatch(r"\\[A-Za-z]+", name) and body.startswith("\\") and "#" not in body and len(body) > 1:
            by_body.setdefault(body, []).append(name)
    n = 0
    ambiguous: list[str] = []
    for body, names in sorted(by_body.items(), key=lambda kv: -len(kv[0])):  # longest first
        if len(names) > 1:
            ambiguous += names
            continue
        name = names[0]
        tail = r"(?![A-Za-z])" if body[-1].isalpha() else ""

        def repl(m: re.Match) -> str:
            nonlocal n
            n += 1
            nxt = text[m.end():m.end() + 1]
            return name + ("{}" if nxt.isalpha() else "")

        text = re.sub(re.escape(body) + tail, repl, text)
    return text, n, ambiguous


def run(ctx: Context) -> None:
    ctx.tex = normalize_text(ctx.tex, ctx.config.images_dir)
    macros = {**ctx.sidecar.macros, **ctx.config.macros}
    if macros:
        ctx.tex, n, ambiguous = fold_macros(ctx.tex, macros)
        if n:
            ctx.report.info(STAGE, "macros.folded", str(n))
        for name in ambiguous:
            ctx.report.info(STAGE, "macros.ambiguous", name)
