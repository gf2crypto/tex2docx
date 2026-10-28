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

from ..bibliography import ABSTRACT_TITLES, BIB_TITLES, KEYWORDS_TITLES, bib_files, is_bibtex
from ..context import Context
from ..texmf import personal_packages
from ..texscan import document_language
from ..tools import ToolError, require
from ..tools import run as run_tool
from . import StageError, mathimg

STAGE = "pandoc"
FILTERS = ["oldmath.lua", "crossref.lua", "theorems.lua", "captions.lua", "headings.lua",
           "bibliography.lua", "lists.lua", "equations.lua", "mathimg.lua", "numbers.lua"]  # order matters; --citeproc after

CAPTION_NAMES = {  # babel language -> (figure, table, separator after the number)
    "russian": ("Рис.", "Таблица", "."),
    "ukrainian": ("Рис.", "Таблиця", "."),
    "english": ("Figure", "Table", ":"),
}


_CREFNAME = re.compile(r"(?<!\\)\\(crefname|Crefname)\s*\{(\w+)\}\s*\{([^{}]*)\}\s*\{([^{}]*)\}")


def cref_names(ctx: Context) -> dict:
    """cleveref names: the language defaults (data/cleveref-names.json, extracted from
    cleveref.sty) overridden by \\crefname/\\Crefname of the document and personal packages."""
    lang, _ = document_language(ctx.tex)
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
    lang, guessed = document_language(ctx.tex)
    if guessed:
        ctx.report.info(STAGE, "names.language-guessed", lang)
    fig, tab, sep = CAPTION_NAMES.get(lang, CAPTION_NAMES["english"])
    c = ctx.config
    return {"figure": c.figure_name or fig, "table": c.table_name or tab,
            "sep": c.caption_sep if c.caption_sep is not None else sep,
            "bibliography": BIB_TITLES.get(lang, BIB_TITLES["english"]),
            "abstract": ABSTRACT_TITLES.get(lang, ABSTRACT_TITLES["english"]),
            "keywords": KEYWORDS_TITLES.get(lang, KEYWORDS_TITLES["english"])}

_SKIPPED = re.compile(r"Skipped '(.+?)' at (.+?) line (\d+)")
_MATH_FAIL = re.compile(r"^\[WARNING\] Could not convert TeX math")
_UNEXPECTED = re.compile(r"unexpected control sequence (\\[A-Za-z@]+)")
_T2D = re.compile(r"^\[t2d\] (info|warning|error) (\S+) ?(.*)$")
_CITEPROC = re.compile(r"\[WARNING\] Citeproc: citation (\S+) not found")

# Skipped by pandoc but irrelevant for the output (handled elsewhere or cosmetic).
HARMLESS_SKIPS = {
    "\\maketitle", "\\centering", "\\numberwithin", "\\theoremstyle",
    "\\NeedsTeXFormat", "\\ProvidesPackage", "\\ProvidesFile", "\\noindent",
    "\\bigskip", "\\medskip", "\\smallskip", "\\newpage", "\\clearpage",
    # ntheorem / thmtools presentation settings: the Word styles decide the look
    "\\theorembodyfont", "\\theoremheaderfont", "\\theoremsymbol", "\\theoremseparator",
    "\\theoremindent", "\\theorempreskip", "\\theorempostskip", "\\theoremnumbering",
    "\\theoremprework", "\\theorempostwork", "\\declaretheoremstyle", "\\qedsymbol",
    "\\begin{t2dabstract}", "\\end{t2dabstract}", "\\begin{t2dkeywords}", "\\end{t2dkeywords}", "\\begin{titlingpage}", "\\end{titlingpage}",
    "\\begin{flushleft}", "\\end{flushleft}", "\\begin{flushright}", "\\end{flushright}",
    "\\begin{center}", "\\end{center}", "\\begin{samepage}", "\\end{samepage}",
    "\\newblock", "\\markboth", "\\markright", "\\newbibliography",
    "\\;", "\\,", "\\!", "\\:", "\\appendix", "\\geometry", "\\parindent", "\\parskip",
    "\\hyphenpenalty", "\\tolerance", "\\emergencystretch", "\\exhyphenpenalty", "\\binoppenalty",
    "\\relpenalty", "\\clubpenalty", "\\widowpenalty", "\\baselineskip", "\\textheight",
    # page layout, spacing, fonts and colors: Word styles decide the look
    "\\setlength", "\\addtolength", "\\vspace", "\\vspace*", "\\hspace", "\\hspace*",
    "\\hfil", "\\hfill", "\\vfill", "\\linewidth", "\\textwidth", "\\pagestyle",
    "\\thispagestyle", "\\linespread", "\\onehalfspacing", "\\doublespacing", "\\singlespacing",
    "\\OnehalfSpacing", "\\DoubleSpacing", "\\SingleSpacing", "\\counterwithout", "\\counterwithin",
    "\\setsecnumdepth", "\\maxtocdepth", "\\settocdepth", "\\DeclareGraphicsExtensions",
    "\\graphicspath", "\\definecolor", "\\color", "\\textcolor", "\\colorlet", "\\pagecolor",
    "\\tiny", "\\scriptsize", "\\footnotesize", "\\small", "\\normalsize", "\\large",
    "\\Large", "\\LARGE", "\\huge", "\\Huge", "\\bgroup", "\\egroup", "\\raggedright",
    "\\raggedleft", "\\sloppy", "\\fussy", "\\frenchspacing", "\\nonfrenchspacing",
    # memoir page design
    "\\settrimmedsize", "\\settypeblocksize", "\\setlrmarginsandblock", "\\setulmarginsandblock",
    "\\setmarginnotes", "\\setheadfoot", "\\setheaderspaces", "\\checkandfixthelayout",
    "\\makepagestyle", "\\makeevenhead", "\\makeoddhead", "\\makeevenfoot", "\\makeoddfoot",
    "\\aliaspagestyle", "\\makerunningwidth", "\\makeheadrule", "\\makefootrule",
    "\\nouppercaseheads", "\\chapterstyle", "\\setsecheadstyle", "\\setsubsecheadstyle",
}


def _pkg_path(*parts: str) -> Path:
    return Path(str(resources.files("tex2docx").joinpath(*parts)))


def _skipped_command(snippet: str) -> str:
    m = re.match(r"\\(?:begin|end)\{[^}]+\}|\\[A-Za-z@]+\*?|\\.", snippet)
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
        elif m := _CITEPROC.search(line):
            ctx.report.warn(STAGE, "bibliography.unknown-key", m.group(1))


def _local_packages(ctx: Context) -> None:
    """Copy the .sty/.cls lying next to the document into the workdir as UTF-8.

    pandoc reads \\usepackage'd files relative to its cwd (not --resource-path) and
    chokes on non-UTF-8 bytes (old Russian styles are cp866/cp1251), so it runs in
    the workdir with clean copies."""
    for f in sorted(ctx.source_dir.glob("*.sty")) + sorted(ctx.source_dir.glob("*.cls")):
        raw = f.read_bytes()
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            text = raw.decode("cp1251", errors="replace")  # comments only, usually
        (ctx.workdir / f.name).write_text(text, encoding="utf-8")


def _pandoc(ctx: Context, inp: Path, meta: Path, out: Path, bibs: list[Path]):
    pandoc = require("pandoc")
    ref = ctx.config.reference_docx or _pkg_path(
        "data", "reference-standard.docx" if ctx.config.profile == "standard" else "reference.docx")
    # cwd = workdir with copies of the local .sty files: pandoc reads \usepackage'd
    # files relative to cwd (not --resource-path), and that is how it sees local
    # macro packages; images are found through --resource-path.
    cmd = [
        pandoc, str(inp), "-f", "latex", "-t", "docx", "-o", str(out),
        "--reference-doc", str(ref),
        "--resource-path", os.pathsep.join([str(ctx.workdir), str(ctx.source_dir)]),
        "-M", f"t2d-meta={meta}",
        "--verbose",
    ]
    for f in FILTERS:
        cmd += ["--lua-filter", str(_pkg_path("filters", f))]
    if bibs:  # ADR 0005: .bib -> citeproc with the GOST style, offline
        csl = ctx.config.csl or _pkg_path("data", "csl", "gost-r-7-0-5-2008-numeric.csl")
        cmd += ["--citeproc", "--csl", str(csl), "-M", "link-citations=false"]
        for b in bibs:
            cmd += ["--bibliography", str(b)]
    try:
        return run_tool(cmd, cwd=ctx.workdir)
    except ToolError as e:
        raise StageError("pandoc.tool", str(e)) from e


def run(ctx: Context) -> None:
    inp = ctx.workdir / "pandoc_input.tex"
    inp.write_text(ctx.tex, encoding="utf-8")
    _local_packages(ctx)
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
        "bibcites": ctx.bibcites,
        "live_numbers": ctx.config.live_numbers,
        "section_level": 2 if re.search(r"(?<!\\)\\chapter\b", ctx.tex) else 1,
        "mathimg": {"mode": "collect", "out": str(failed_path)},
    }
    bibs = [] if is_bibtex(ctx) else bib_files(ctx)  # BibTeX lists come from the .bbl
    if bibs:
        ctx.report.info(STAGE, "bibliography.citeproc", str(len(bibs)))
    if ctx.config.math_fallback != "image":
        data["mathimg"] = None
    meta.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    out = ctx.workdir / "pandoc.docx"
    proc = _pandoc(ctx, inp, meta, out, bibs)

    # Second pass only when some formula could not be converted and LaTeX rendered it.
    images = mathimg.render(ctx, mathimg.load_failed(failed_path)) if data["mathimg"] else {}
    if images:
        data["mathimg"] = {"mode": "replace", "images": images}
        meta.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        proc = _pandoc(ctx, inp, meta, out, bibs)
        ctx.report.warn(STAGE, "pandoc.math-as-image", str(len(images)))

    collect_pandoc_messages(proc.stderr, inp.name, ctx)
    if proc.returncode != 0 or not out.exists():
        tail = proc.stderr.strip().splitlines()[-1:] or ["no output"]
        raise StageError("pandoc.failed", tail[0][:200])
    ctx.docx = out
