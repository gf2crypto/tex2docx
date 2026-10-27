"""Stage 5: rewrite constructs pandoc misreads, in ctx.tex only.

Status: implemented (M0): babel shorthands of Russian/Ukrainian.
pandoc renders '"---' as a literal quote plus dash; LaTeX never shows the quote.
M1: alignat/flalign become align (pandoc leaves alignat's column count in the
formula text and does not know flalign at all); numbering is the same.
"""

from __future__ import annotations

import re

from ..context import Context

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
]


# \begin{alignat}{2} / \begin{flalign} -> \begin{align}; same for the starred forms.
MATH_ENVS: list[tuple[str, str]] = [
    (r"(?<!\\)\\(begin|end)\{alignat(\*?)\}(?:\{\d+\})?", r"\\\1{align\2}"),
    (r"(?<!\\)\\(begin|end)\{flalign(\*?)\}", r"\\\1{align\2}"),
]


def normalize_text(text: str) -> str:
    for pat, rep in BABEL_SHORTHANDS + MATH_ENVS:
        text = re.sub(pat, rep, text)
    return text


def run(ctx: Context) -> None:
    ctx.tex = normalize_text(ctx.tex)
