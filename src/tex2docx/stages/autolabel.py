"""Stage 2: give every numbered object a label, so LaTeX reports its number.

Status: implemented (M1).

Every numbered object without a \\label gets \\label{t2d:auto:N} (N counts in
source order), identically in ctx.latex_tex and ctx.tex, so that the .aux of
the real LaTeX run contains its number and the filters can print it:

- numbered theorem environments (from \\newtheorem, see stages/theorems.py):
  right after \\begin{env} and its optional argument;
- equation, subequations, multline: right after \\begin{env};
- align, alignat, flalign, gather, eqnarray: at the end of every line that
  carries no \\label, \\notag, \\nonumber or \\tag (before its \\\\);
- figure(*), table(*): right after the first \\caption{...}, when the float
  has no \\label anywhere;
- \\chapter, \\section, \\subsection, \\subsubsection, \\paragraph (not starred):
  right after the title, unless a \\label follows on the same line.

Starred math environments are unnumbered and untouched. Content of verbatim-like
environments is skipped. Labels with the prefix "t2d:auto:" are internal:
nothing refers to them, crossref never prints them, the report never lists them.

This is a scanner over \\begin/\\end tokens with a stack, not a TeX parser:
environments hidden inside user macros are not seen (then the theorem keeps
pandoc's number and the theorems filter reports theorem.unlabeled).
"""

from __future__ import annotations

import re

from ..context import Context
from ..texmf import personal_packages
from ..texscan import read_group, read_optional, skip_ws
from .theorems import collect_decls

STAGE = "autolabel"
PREFIX = "t2d:auto:"

AFTER_BEGIN = {"equation", "subequations", "multline"}
PER_LINE = {"align", "alignat", "flalign", "gather", "eqnarray"}
FLOATS = {"figure", "figure*", "table", "table*"}
VERBATIM = {"verbatim", "verbatim*", "lstlisting", "minted", "comment", "Verbatim"}

SECTIONING = {"chapter", "section", "subsection", "subsubsection", "paragraph"}
_SECTION = re.compile(r"(?<!\\)\\(chapter|section|subsection|subsubsection|paragraph)(\*?)\s*")

_TOKEN = re.compile(
    r"\\begin\s*\{([^{}]+)\}"            # 1: environment start
    r"|\\end\s*\{([^{}]+)\}"             # 2: environment end
    r"|\\\\\*?(?:\[[^\]]*\])?"           # line break with optional [skip]
    r"|\\(label|notag|nonumber|tag|caption)\b\*?"  # 3: service commands
    r"|\\[A-Za-z@]+|\\."                 # any other command (so \{ is not a brace)
    r"|([{}])"                           # 4: braces
)


class _Frame:
    __slots__ = ("env", "start", "depth", "has_label", "line_start", "line_flag",
                 "caption_end")

    def __init__(self, env: str, start: int) -> None:
        self.env = env
        self.start = start  # insertion point right after \begin{env}[opt]
        self.depth = 0  # brace depth inside this environment
        self.has_label = False
        self.line_start = start  # for PER_LINE environments
        self.line_flag = False  # current line already numbered/unnumbered explicitly
        self.caption_end: int | None = None  # for floats: end of the first \caption{}


def insert_labels(text: str, theorem_envs: set[str]) -> tuple[str, int]:
    """Return (text with auto labels, number of labels inserted)."""
    body_start = text.find("\\begin{document}")
    pos = body_start + len("\\begin{document}") if body_start >= 0 else 0
    stack: list[_Frame] = []
    inserts: list[int] = []  # positions, in source order

    def line_done(fr: _Frame, end: int, next_start: int) -> None:
        """A line of a PER_LINE environment ends at `end` (its \\\\ or \\end)."""
        # an empty line (trailing \\\\ before \\end) is numbered by amsmath too
        if not fr.line_flag:
            inserts.append(end)
        fr.line_start = next_start
        fr.line_flag = False

    def close(fr: _Frame, end: int) -> None:
        env = fr.env
        if env in PER_LINE:  # last line: put the label right after its content
            e = end
            while e > fr.line_start and text[e - 1] in " \t\n":
                e -= 1
            line_done(fr, e, end)
        elif env in FLOATS:
            if not fr.has_label and fr.caption_end is not None:
                inserts.append(fr.caption_end)
        elif (env in AFTER_BEGIN or env in theorem_envs) and not fr.has_label:
            inserts.append(fr.start)

    while True:
        m = _TOKEN.search(text, pos)
        if not m:
            break
        pos = m.end()
        tok = m.group(0)
        if m.group(1) is not None:  # \begin{env}
            env = m.group(1).strip()
            if env in VERBATIM:
                e = text.find(f"\\end{{{env}}}", pos)
                pos = len(text) if e < 0 else e
                continue
            if env == "document":
                continue
            if env in theorem_envs:
                _, pos = read_optional(text, pos)
            # other environments are only containers for nested ones
            stack.append(_Frame(env, pos))
        elif m.group(2) is not None:  # \end{env}
            env = m.group(2).strip()
            if env == "document":
                break
            # pop to the matching frame; tolerate unbalanced input
            for i in range(len(stack) - 1, -1, -1):
                if stack[i].env == env:
                    fr = stack.pop(i)
                    del stack[i:]
                    close(fr, m.start())
                    break
        elif not stack:
            continue
        elif tok.startswith("\\\\"):
            fr = stack[-1]
            if fr.env in PER_LINE and fr.depth == 0:
                line_done(fr, m.start(), m.end())
        elif m.group(3) is not None:
            cmd = m.group(3)
            fr = stack[-1]
            if cmd == "caption":
                p = pos
                while p < len(text) and text[p] in " \t":
                    p += 1
                if p < len(text) and text[p] == "[":
                    _, p = read_group(text, p, "[", "]")
                if p < len(text) and text[p] == "{":
                    inner, p = read_group(text, p)
                    has_label = "\\label" in inner
                    pos = p
                    for f in reversed(stack):
                        if f.env in FLOATS:
                            if f.caption_end is None:
                                f.caption_end = p
                            f.has_label |= has_label
                            break
                continue
            if cmd == "label":
                fr.has_label = True
            if fr.env in PER_LINE:
                fr.line_flag = True
        elif m.group(4) is not None:
            stack[-1].depth += 1 if tok == "{" else -1

    # sectioning commands: label right after the title
    for m in _SECTION.finditer(text, body_start if body_start >= 0 else 0):
        if m.group(2) == "*":
            continue
        try:
            p = m.end()
            _, p = read_optional(text, p)
            p = skip_ws(text, p)
            if p >= len(text) or text[p] != "{":
                continue
            _, p = read_group(text, p)
        except ValueError:
            continue
        rest = text[p:text.find("\n", p) if text.find("\n", p) >= 0 else len(text)]
        if "\\label" in rest:
            continue
        inserts.append(p)

    if not inserts:
        return text, 0
    # positions are collected when an environment closes, i.e. outer ones after
    # their nested ones: restore source order before numbering
    inserts.sort()
    out = []
    last = 0
    for n, p in enumerate(inserts, 1):
        out.append(text[last:p])
        out.append(f"\\label{{{PREFIX}{n}}}")
        last = p
    out.append(text[last:])
    return "".join(out), len(inserts)


def run(ctx: Context) -> None:
    if ctx.latex_tex != ctx.tex:
        ctx.report.error(STAGE, "autolabel.views-differ")
        return
    decls = collect_decls(ctx.source_dir, ctx.tex, list(personal_packages(ctx).values()))
    numbered = {env for env, d in decls.items() if d.numbered}
    text, n = insert_labels(ctx.tex, numbered)
    if n:
        ctx.latex_tex = ctx.tex = text
        (ctx.workdir / "flat.tex").write_text(text, encoding="utf-8")
    ctx.report.info(STAGE, "autolabel.inserted", str(n))
