"""Stage 4: collect \\newtheorem declarations and their amsthm styles.

Status: implemented (M0 amsthm; M2 thmtools \\declaretheorem and ntheorem's
\\newframedtheorem / \\newshadedtheorem). thmtools styles other than
plain/definition/remark and ntheorem's own styles fall back to "plain".

Sources, in order: local .sty/.cls next to the main file, then the document.
\\theoremstyle is sticky, as in LaTeX.
"""

from __future__ import annotations

import re
from pathlib import Path

from ..context import Context, TheoremDecl
from ..texmf import personal_packages
from ..texscan import read_group, read_optional, skip_ws

STAGE = "theorems"
_TOKEN = re.compile(
    r"(?<!\\)\\(theoremstyle|newtheorem|newframedtheorem|newshadedtheorem|declaretheorem)(\*?)"
)
_KV = re.compile(r"\s*([A-Za-z]+)\s*(?:=\s*(\{[^{}]*\}|[^,]*))?\s*(?:,|$)")


def parse_keyvals(opts: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for m in _KV.finditer(opts):
        key, val = m.group(1), m.group(2)
        if not key:
            continue
        val = (val or "").strip()
        if val.startswith("{") and val.endswith("}"):
            val = val[1:-1]
        out[key] = val
    return out


def amsthm_style(style: str) -> tuple[str, bool]:
    """Map a \\theoremstyle name to (amsthm style, numbered). ntheorem: nonumberplain,
    break, change, margin, ...; thmtools: user-defined names fall back to plain."""
    numbered = not style.startswith("nonumber")
    base = style[len("nonumber"):] if not numbered else style
    if base in ("plain", "definition", "remark"):
        return base, numbered
    return "plain", numbered


def _declaretheorem(opts: str | None, env: str) -> TheoremDecl:
    """thmtools: \\declaretheorem[name=..., style=..., numberwithin=..., sibling=..., numbered=no]{env}."""
    kv = parse_keyvals(opts or "")
    name = kv.get("name") or kv.get("title") or env[:1].upper() + env[1:]
    style = kv.get("style", "plain")
    within = kv.get("numberwithin") or kv.get("within") or kv.get("parent") or None
    sibling = kv.get("sibling") or kv.get("sharecounter") or kv.get("numberlike") or None
    numbered = kv.get("numbered", "yes") not in ("no", "false")
    return TheoremDecl(env=env, title=name, style=style, numbered=numbered,
                       counter=sibling, within=within)


def theorems_to_amsthm(text: str) -> str:
    """Rewrite theorem declarations into plain amsthm for pandoc (same line count):
    thmtools' \\declaretheorem -> \\theoremstyle + \\newtheorem; ntheorem's
    \\theoremstyle{nonumberplain} -> \\theoremstyle{plain} with the following
    \\newtheorem starred; other ntheorem/thmtools styles -> plain."""
    out: list[str] = []
    last = 0
    numbered_style = True
    for m in _TOKEN.finditer(text):
        kind, star = m.group(1), m.group(2)
        try:
            pos = skip_ws(text, m.end())
            if kind == "theoremstyle":
                style, pos = read_group(text, pos)
                ams, numbered_style = amsthm_style(style.strip())
                repl = f"\\theoremstyle{{{ams}}}"
            elif kind == "declaretheorem":
                opts, pos = read_optional(text, pos)
                env, pos = read_group(text, skip_ws(text, pos))
                d = _declaretheorem(opts, env.strip())
                ams, _ = amsthm_style(d.style)
                repl = f"\\theoremstyle{{{ams}}}\\newtheorem{'' if d.numbered else '*'}{{{d.env}}}"
                if d.counter:
                    repl += f"[{d.counter}]"
                repl += f"{{{d.title}}}"
                if d.within and not d.counter:
                    repl += f"[{d.within}]"
            else:  # newtheorem and ntheorem's framed/shaded variants
                env, pos = read_group(text, pos)
                counter, pos = read_optional(text, pos)
                pos = skip_ws(text, pos)
                title, pos = read_group(text, pos)
                within, pos = read_optional(text, pos) if counter is None else (None, pos)
                star = "*" if (star == "*" or not numbered_style) else ""
                repl = f"\\newtheorem{star}{{{env.strip()}}}"
                if counter is not None:
                    repl += f"[{counter}]"
                repl += f"{{{title}}}"
                if within is not None:
                    repl += f"[{within}]"
        except ValueError:
            continue
        repl += "\n" * text[m.start():pos].count("\n")  # keep the line count
        out.append(text[last:m.start()])
        out.append(repl)
        last = pos
    out.append(text[last:])
    return "".join(out)


def scan_decls(text: str, style: str = "plain") -> tuple[dict[str, TheoremDecl], str]:
    """Return (declarations, style in effect at the end of text)."""
    decls: dict[str, TheoremDecl] = {}
    for m in _TOKEN.finditer(text):
        try:
            pos = skip_ws(text, m.end())
            if m.group(1) == "theoremstyle":
                style, _ = read_group(text, pos)
                style = style.strip()
                continue
            if m.group(1) == "declaretheorem":
                opts, pos = read_optional(text, pos)
                env, pos = read_group(text, skip_ws(text, pos))
                d = _declaretheorem(opts, env.strip())
                decls[d.env] = d
                continue
            env, pos = read_group(text, pos)
            counter, pos = read_optional(text, pos)
            pos = skip_ws(text, pos)
            title, pos = read_group(text, pos)
            within, pos = read_optional(text, pos) if counter is None else (None, pos)
            ams, numbered = amsthm_style(style)
            decls[env.strip()] = TheoremDecl(
                env=env.strip(), title=title.strip(), style=ams,
                numbered=(m.group(2) != "*") and numbered, counter=counter, within=within,
            )
        except ValueError:
            continue
    return decls, style


def collect_decls(source_dir: Path, tex: str,
                  extra: list[Path] | None = None) -> dict[str, TheoremDecl]:
    """Declarations from personal packages, local .sty/.cls next to the main file,
    then from the document."""
    decls: dict[str, TheoremDecl] = {}
    style = "plain"
    files = list(extra or []) + sorted(source_dir.glob("*.sty")) + sorted(source_dir.glob("*.cls"))
    for f in files:
        found, style = scan_decls(f.read_text(encoding="utf-8", errors="replace"), style)
        decls.update(found)
    found, _ = scan_decls(tex, style)
    decls.update(found)
    return decls


def run(ctx: Context) -> None:
    ctx.theorems.update(collect_decls(ctx.source_dir, ctx.tex, list(personal_packages(ctx).values())))
    if not ctx.theorems and "\\begin{proof}" in ctx.tex:
        ctx.report.warn(STAGE, "theorems.none-declared", "proof used, no \\newtheorem found")
