"""Stage 5: rewrite constructs pandoc misreads, in ctx.tex only.

Status: implemented (M0): babel shorthands of Russian/Ukrainian.
pandoc renders '"---' as a literal quote plus dash; LaTeX never shows the quote.
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


def normalize_text(text: str) -> str:
    for pat, rep in BABEL_SHORTHANDS:
        text = re.sub(pat, rep, text)
    return text


def run(ctx: Context) -> None:
    ctx.tex = normalize_text(ctx.tex)
