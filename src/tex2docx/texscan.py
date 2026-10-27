"""Minimal TeX scanning helpers: balanced groups, comments.

This is NOT a TeX parser and must not grow into one. Anything that needs real
TeX semantics is answered by running LaTeX (see docs/architecture.md).
"""

from __future__ import annotations

import re


def read_group(text: str, pos: int, open_: str = "{", close: str = "}") -> tuple[str, int]:
    """Read a balanced group starting at text[pos] == open_.

    Returns (inner_content, index_after_group). Skips escaped braces.
    """
    if pos >= len(text) or text[pos] != open_:
        raise ValueError(f"expected {open_!r} at {pos}")
    depth = 0
    i = pos
    while i < len(text):
        ch = text[i]
        if ch == "\\":
            i += 2
            continue
        if ch == open_:
            depth += 1
        elif ch == close:
            depth -= 1
            if depth == 0:
                return text[pos + 1 : i], i + 1
        i += 1
    raise ValueError(f"unbalanced {open_!r} starting at {pos}")


def skip_ws(text: str, pos: int) -> int:
    while pos < len(text) and text[pos] in " \t\n":
        pos += 1
    return pos


def read_optional(text: str, pos: int) -> tuple[str | None, int]:
    """Read an optional [..] argument if present (after whitespace)."""
    p = skip_ws(text, pos)
    if p < len(text) and text[p] == "[":
        content, end = read_group(text, p, "[", "]")
        return content, end
    return None, pos


_COMMENT_LINE = re.compile(r"^[ \t]*%")


def blank_comment_lines(text: str) -> str:
    """Reduce every full-line comment to a lone '%', keeping line numbering intact.

    Not an empty line: inside a macro argument an empty line is a \\par and breaks
    LaTeX ("Paragraph ended before ... was complete"); a lone '%' is invisible.
    Trailing comments are left alone: '%' inside verbatim/url makes that unsafe.
    """
    return "\n".join("%" if _COMMENT_LINE.match(ln) else ln for ln in text.split("\n"))


def line_of(text: str, pos: int) -> int:
    return text.count("\n", 0, pos) + 1


_BABEL = re.compile(r"(?<!\\)\\usepackage\s*(?:\[([^\]]*)\])?\s*\{babel\}")


def babel_languages(text: str) -> list[str]:
    """Languages from \\usepackage[...]{babel}, in order; the last one is the main one."""
    langs: list[str] = []
    for m in _BABEL.finditer(text):
        for opt in (m.group(1) or "").split(","):
            opt = opt.strip()
            if "=" in opt:  # main=russian, bidi=... etc.
                key, _, val = opt.partition("=")
                if key.strip() == "main":
                    langs.append(val.strip())
            elif opt:
                langs.append(opt)
    return langs


_CMD = re.compile(r"\\[A-Za-z@]+\*?\s*")


def strip_tex(s: str) -> str:
    """Turn a LaTeX-printed number like '\\textup {(i)}' or '\\relax 1.2' into plain text."""
    s = _CMD.sub("", s)
    return s.replace("{", "").replace("}", "").replace("~", " ").strip()
