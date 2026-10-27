"""Stage 8: pandoc LaTeX -> docx with our Lua filters.

Status: implemented (M0).

Data for the filters goes through a JSON file whose path is passed as metadata
't2d-meta' (see filters/t2d.lua). Filters report problems by printing lines
'[t2d] <level> <code> <detail>' to stderr; they are collected into the report.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import asdict
from importlib import resources
from pathlib import Path

from ..context import Context
from ..texmf import personal_packages
from ..texscan import babel_languages
from ..tools import ToolError, require
from ..tools import run as run_tool
from . import StageError, mathimg

STAGE = "pandoc"
FILTERS = ["crossref.lua", "theorems.lua", "captions.lua", "equations.lua", "mathimg.lua"]  # order matters

CAPTION_NAMES = {  # babel language -> (figure, table, separator after the number)
    "russian": ("Рис.", "Таблица", "."),
    "ukrainian": ("Рис.", "Таблиця", "."),
    "english": ("Figure", "Table", ":"),
}


_CREFNAME = re.compile(r"(?<!\\)\\(crefname|Crefname)\s*\{(\w+)\}\s*\{([^{}]*)\}\s*\{([^{}]*)\}")


def cref_names(ctx: Context) -> dict:
    """cleveref names: the language defaults (data/cleveref-names.json, extracted from
    cleveref.sty) overridden by \\crefname/\\Crefname of the document and personal packages."""
    langs = babel_languages(ctx.tex)
    lang = langs[-1] if langs else "english"
    table = json.loads(_pkg_path("data", "cleveref-names.json").read_text(encoding="utf-8"))
    base = table.get(lang) or table["english"]
    names = {k: dict(v) for k, v in base["names"].items()}
    sources = [p.read_text(encoding="utf-8", errors="replace")
               for p in personal_packages(ctx).values()] + [ctx.tex]
    for src in sources:
        for m in _CREFNAME.finditer(src):
            kind, typ, sg, pl = m.groups()
            d = names.setdefault(typ, {})
            if kind == "crefname":
                d["sg"], d["pl"] = sg.strip(), pl.strip()
                d.setdefault("Sg", sg.strip()[:1].upper() + sg.strip()[1:])
                d.setdefault("Pl", pl.strip()[:1].upper() + pl.strip()[1:])
            else:
                d["Sg"], d["Pl"] = sg.strip(), pl.strip()
                d.setdefault("sg", sg.strip()[:1].lower() + sg.strip()[1:])
                d.setdefault("pl", pl.strip()[:1].lower() + pl.strip()[1:])
    return {"names": names, "conjunctions": base["conjunctions"]}


def caption_names(ctx: Context) -> dict[str, str]:
    langs = babel_languages(ctx.tex)
    fig, tab, sep = CAPTION_NAMES.get(langs[-1] if langs else "english", CAPTION_NAMES["english"])
    c = ctx.config
    return {"figure": c.figure_name or fig, "table": c.table_name or tab,
            "sep": c.caption_sep if c.caption_sep is not None else sep}

_SKIPPED = re.compile(r"Skipped '(.+?)' at (.+?) line (\d+)")
_MATH_FAIL = re.compile(r"^\[WARNING\] Could not convert TeX math")
_UNEXPECTED = re.compile(r"unexpected control sequence (\\[A-Za-z@]+)")
_T2D = re.compile(r"^\[t2d\] (info|warning|error) (\S+) ?(.*)$")

# Skipped by pandoc but irrelevant for the output (handled elsewhere or cosmetic).
HARMLESS_SKIPS = {
    "\\maketitle", "\\centering", "\\numberwithin", "\\theoremstyle",
    "\\NeedsTeXFormat", "\\ProvidesPackage", "\\ProvidesFile", "\\noindent",
    "\\bigskip", "\\medskip", "\\smallskip", "\\newpage", "\\clearpage",
}


def _pkg_path(*parts: str) -> Path:
    return Path(str(resources.files("tex2docx").joinpath(*parts)))


def _skipped_command(snippet: str) -> str:
    m = re.match(r"\\[A-Za-z@]+\*?|\\begin\{[^}]+\}", snippet)
    return m.group(0) if m else snippet[:20]


def collect_pandoc_messages(stderr: str, input_name: str, ctx: Context) -> None:
    """Turn pandoc/filter stderr into report items. Math text is never copied."""
    lines = stderr.splitlines()
    for i, line in enumerate(lines):
        if m := _SKIPPED.search(line):
            if not m.group(2).endswith(input_name):
                continue  # skipped inside a .sty pandoc read: package internals
            cmd = _skipped_command(m.group(1))
            if cmd not in HARMLESS_SKIPS:
                ctx.report.warn(STAGE, "pandoc.skipped", cmd, line=int(m.group(3)))
        elif _MATH_FAIL.match(line):
            culprit = "?"
            for follow in lines[i + 1 : i + 6]:
                if u := _UNEXPECTED.search(follow):
                    culprit = u.group(1)
                    break
            ctx.report.warn(STAGE, "pandoc.math-as-text", culprit)
        elif m := _T2D.match(line.strip()):
            ctx.report.add(m.group(1), "filter", m.group(2), m.group(3))


def _pandoc(ctx: Context, inp: Path, meta: Path, out: Path):
    pandoc = require("pandoc")
    ref = ctx.config.reference_docx or _pkg_path("data", "reference.docx")
    # cwd = source dir: pandoc reads \usepackage'd .sty files relative to cwd
    # (not --resource-path), and that is how it sees local macro packages.
    cmd = [
        pandoc, str(inp), "-f", "latex", "-t", "docx", "-o", str(out),
        "--reference-doc", str(ref),
        "--resource-path", os.pathsep.join([str(ctx.workdir), str(ctx.source_dir)]),
        "-M", f"t2d-meta={meta}",
        "--verbose",
    ]
    for f in FILTERS:
        cmd += ["--lua-filter", str(_pkg_path("filters", f))]
    try:
        return run_tool(cmd, cwd=ctx.source_dir)
    except ToolError as e:
        raise StageError("pandoc.tool", str(e)) from e


def run(ctx: Context) -> None:
    inp = ctx.workdir / "pandoc_input.tex"
    inp.write_text(ctx.tex, encoding="utf-8")
    meta = ctx.workdir / "t2d-meta.json"
    failed_path = ctx.workdir / "mathfail.json"
    data = {
        "labels": {k: v.number for k, v in ctx.labels.items()},
        "types": {k: v.cref_type for k, v in ctx.labels.items() if v.cref_type},
        "cref": cref_names(ctx),
        "theorems": {k: asdict(v) for k, v in ctx.theorems.items()},
        "proof_name": ctx.config.proof_name,
        "styles": ctx.config.theorem_styles,
        "names": caption_names(ctx),
        "mathimg": {"mode": "collect", "out": str(failed_path)},
    }
    if ctx.config.math_fallback != "image":
        data["mathimg"] = None
    meta.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    out = ctx.workdir / "pandoc.docx"
    proc = _pandoc(ctx, inp, meta, out)

    # Second pass only when some formula could not be converted and LaTeX rendered it.
    images = mathimg.render(ctx, mathimg.load_failed(failed_path)) if data["mathimg"] else {}
    if images:
        data["mathimg"] = {"mode": "replace", "images": images}
        meta.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        proc = _pandoc(ctx, inp, meta, out)
        ctx.report.warn(STAGE, "pandoc.math-as-image", str(len(images)))

    collect_pandoc_messages(proc.stderr, inp.name, ctx)
    if proc.returncode != 0 or not out.exists():
        tail = proc.stderr.strip().splitlines()[-1:] or ["no output"]
        raise StageError("pandoc.failed", tail[0][:200])
    ctx.docx = out
