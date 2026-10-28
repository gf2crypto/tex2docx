"""Stage: pseudocode (algorithmic / algpseudocode) as editable text in a box.

Status: implemented (M3). config.algorithms = "text" (default) | "image" (pictures
via preview, the old way).

\\begin{algorithm} floats and bare algorithmic environments are rewritten in ctx.tex
into a t2dalgo environment (pandoc: a Div) whose paragraphs are the lines:

    \\begin{t2dalgo} T2DALGCAP: \\label{alg:x} Caption \\par
      T2DALG:<number>:<level>: \\textbf{function} \\textsc{Gen}() \\par ... \\end{t2dalgo}

Keywords are those algpseudocode prints (if ... then, end if, for ... do, function,
return, ...); [noend] of the package drops the end lines; [n] of the environment
numbers every n-th line. Formulas stay formulas. filters/algorithms.lua turns the
markers into Word paragraphs of the Algorithm styles (a bordered box; the number of
the caption comes from the .aux). The line count of ctx.tex is preserved.
"""

from __future__ import annotations

import re

from ..context import Context
from ..texscan import read_group, read_optional, skip_ws
from .figures import outermost_spans

STAGE = "algorithms"

# statement -> (keyword text, level change before, level change after, takes {arg})
STATEMENTS: dict[str, tuple[str, int, int, bool]] = {
    "State": ("", 0, 0, False),
    "Statex": ("", 0, 0, False),
    "Require": ("\\textbf{Require:}", 0, 0, False),
    "Ensure": ("\\textbf{Ensure:}", 0, 0, False),
    "If": ("\\textbf{if} {ARG} \\textbf{then}", 0, 1, True),
    "ElsIf": ("\\textbf{else if} {ARG} \\textbf{then}", -1, 1, True),
    "Else": ("\\textbf{else}", -1, 1, False),
    "EndIf": ("\\textbf{end if}", -1, 0, False),
    "For": ("\\textbf{for} {ARG} \\textbf{do}", 0, 1, True),
    "ForAll": ("\\textbf{for all} {ARG} \\textbf{do}", 0, 1, True),
    "EndFor": ("\\textbf{end for}", -1, 0, False),
    "While": ("\\textbf{while} {ARG} \\textbf{do}", 0, 1, True),
    "EndWhile": ("\\textbf{end while}", -1, 0, False),
    "Repeat": ("\\textbf{repeat}", 0, 1, False),
    "Until": ("\\textbf{until} {ARG}", -1, 0, True),
    "Loop": ("\\textbf{loop}", 0, 1, False),
    "EndLoop": ("\\textbf{end loop}", -1, 0, False),
    "Function": ("\\textbf{function} \\textsc{{ARG}}({ARG2})", 0, 1, True),
    "EndFunction": ("\\textbf{end function}", -1, 0, False),
    "Procedure": ("\\textbf{procedure} \\textsc{{ARG}}({ARG2})", 0, 1, True),
    "EndProcedure": ("\\textbf{end procedure}", -1, 0, False),
}
END_LINES = {"EndIf", "EndFor", "EndWhile", "EndLoop", "EndFunction", "EndProcedure"}
TWO_ARGS = {"Function", "Procedure"}
UNNUMBERED = {"Require", "Ensure", "Statex"}
_STMT = re.compile(r"(?<!\\)\\(" + "|".join(STATEMENTS) + r")\b")
_INLINE = [
    (re.compile(r"(?<!\\)\\Return\b\s*"), r"\\textbf{return} "),
    (re.compile(r"(?<!\\)\\Call\s*\{([^{}]*)\}\s*\{([^{}]*)\}"), r"\\textsc{\1}(\2)"),
    (re.compile(r"(?<!\\)\\Comment\s*\{([^{}]*)\}"), r"$\\triangleright$ \1"),
    (re.compile(r"(?<!\\)\\\\(?:\[[^\]]*\])?"), " "),
]
_NOEND = re.compile(r"(?<!\\)\\usepackage\s*\[[^\]]*\bnoend\b[^\]]*\]\s*\{algpseudocode\}")
_CAPTION = re.compile(r"(?<!\\)\\caption\s*")
_LABEL = re.compile(r"(?<!\\)\\label\s*\{([^{}]*)\}")


def _strip_comments(text: str) -> str:
    return re.sub(r"(?<!\\)%[^\n]*", "", text)


def parse_lines(body: str, noend: bool, step: int) -> list[tuple[str, int, str]]:
    """algorithmic body -> [(line number or '', level, LaTeX text)]."""
    body = _strip_comments(body)
    out: list[tuple[str, int, str]] = []
    level = 0
    n = 0
    matches = list(_STMT.finditer(body))
    for i, m in enumerate(matches):
        name = m.group(1)
        keyword, before, after, takes = STATEMENTS[name]
        pos = m.end()
        args: list[str] = []
        if takes:
            for _ in range(2 if name in TWO_ARGS else 1):
                p = skip_ws(body, pos)
                if p < len(body) and body[p] == "{":
                    try:
                        arg, pos = read_group(body, p)
                    except ValueError:
                        arg = ""
                    args.append(arg.strip())
                else:
                    args.append("")
        rest = body[pos:matches[i + 1].start() if i + 1 < len(matches) else len(body)]
        rest = " ".join(rest.split())
        for rx, rep in _INLINE:
            rest = rx.sub(rep, rest)
        text = keyword
        if args:
            text = text.replace("{ARG2}", args[1] if len(args) > 1 else "").replace("{ARG}", args[0])
        text = (text + " " + rest).strip() if rest else text
        level = max(0, level + before)
        if name in END_LINES and noend:
            level = max(0, level + after)
            continue
        if not text and name == "Statex":
            out.append(("", level, ""))
        else:
            number = ""
            if name not in UNNUMBERED:
                n += 1
                if step and n % step == 0:
                    number = str(n)
            out.append((number, level, text))
        level = max(0, level + after)
    return out


def render_block(lines: list[tuple[str, int, str]], caption: str | None, label: str | None) -> str:
    parts = ["\\begin{t2dalgo}"]
    if caption is not None:
        lab = "\\label{" + label + "} " if label else ""
        parts.append(f"T2DALGCAP: {lab}{caption} \\par")
    for number, level, text in lines:
        parts.append(f"T2DALG:{number}:{level}: {text} \\par")
    parts.append("\\end{t2dalgo}")
    return " ".join(parts)


def _algorithmic_blocks(text: str) -> list[tuple[int, int, int, str]]:
    """(start, end, step, body) of every algorithmic environment."""
    out = []
    for m in re.finditer(r"(?<!\\)\\begin\s*\{algorithmic\}", text):
        opt, pos = read_optional(text, m.end())
        end = text.find("\\end{algorithmic}", pos)
        if end < 0:
            continue
        step = 0
        if opt and opt.strip().isdigit():
            step = int(opt.strip())
        out.append((m.start(), end + len("\\end{algorithmic}"), step, text[pos:end]))
    return out


def rewrite(text: str) -> tuple[str, int]:
    """Rewrite algorithm floats and algorithmic environments; returns (text, count)."""
    noend = _NOEND.search(text) is not None
    count = 0
    out = []
    last = 0
    # algorithm floats first (they contain algorithmic); bare algorithmic after
    floats = outermost_spans(text, ["algorithm"])
    consumed: list[tuple[int, int]] = []
    pieces: list[tuple[int, int, str]] = []
    for a, b in floats:
        chunk = text[a:b]
        caption = None
        label = None
        m = _CAPTION.search(chunk)
        if m:
            p = skip_ws(chunk, m.end())
            if p < len(chunk) and chunk[p] == "[":
                _, p = read_group(chunk, p, "[", "]")
            p = skip_ws(chunk, p)
            if p < len(chunk) and chunk[p] == "{":
                caption, _ = read_group(chunk, p)
                caption = " ".join(_strip_comments(caption).split())
        lm = _LABEL.search(chunk)
        if lm:
            label = lm.group(1)
        lines: list[tuple[str, int, str]] = []
        for _, _, step, body in _algorithmic_blocks(chunk):
            lines += parse_lines(body, noend, step)
        if caption is None and not lines:
            continue
        pieces.append((a, b, render_block(lines, caption if caption is not None else "", label)
                       if caption is not None else render_block(lines, None, None)))
        consumed.append((a, b))
    for a, b, step, body in _algorithmic_blocks(text):
        if any(x <= a < y for x, y in consumed):
            continue
        pieces.append((a, b, render_block(parse_lines(body, noend, step), None, None)))
    for a, b, repl in sorted(pieces):
        out.append(text[last:a])
        out.append(repl + "\n" * text[a:b].count("\n"))
        last = b
        count += 1
    out.append(text[last:])
    return "".join(out), count


def run(ctx: Context) -> None:
    if ctx.config.algorithms != "text":
        return
    ctx.tex, n = rewrite(ctx.tex)
    if n:
        ctx.report.info(STAGE, "algorithms.text", str(n))
