"""Stage 3: Word/pandoc artefacts -> the LaTeX an author would write.

Status: implemented (M0):
- \\(x\\) -> $x$; \\[ \\] kept; pandoc's \\hypertarget wrappers and \\def\\labelenumi removed;
- media/<file> paths -> <images_dir>/<file>;
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


def run(ctx: Context) -> None:
    ctx.tex = normalize_text(ctx.tex, ctx.config.images_dir)
