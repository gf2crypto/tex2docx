"""Fast unit tests: no external tools."""

from __future__ import annotations

from pathlib import Path

from tex2docx.aux import parse_aux_text
from tex2docx.config import Config
from tex2docx.context import Context
from tex2docx.report import Report
from tex2docx.stages.flatten import flatten_text
from tex2docx.stages.normalize import normalize_text
from tex2docx.stages.pandoc_run import collect_pandoc_messages
from tex2docx.stages.theorems import scan_decls
from tex2docx.texscan import blank_comment_lines, read_group, strip_tex

# --- texscan -----------------------------------------------------------------

def test_read_group_nested_and_escaped():
    s = r"{a{b}\}c}tail"
    inner, end = read_group(s, 0)
    assert inner == r"a{b}\}c"
    assert s[end:] == "tail"


def test_strip_tex():
    assert strip_tex(r"\relax 1.2") == "1.2"
    assert strip_tex(r"\textup {(i)}") == "(i)"


def test_blank_comment_lines_keeps_numbering():
    s = "a\n  % c\nb % trailing stays\n"
    assert blank_comment_lines(s) == "a\n\nb % trailing stays\n"


# --- aux ---------------------------------------------------------------------

def test_aux_plain_and_hyperref():
    aux = r"""
\newlabel{thm:main}{{1.2}{1}}
\newlabel{eq:x}{{2.1}{3}{Section title}{equation.2.1}{}}
\newlabel{it:a}{{\textup {(i)}}{4}{}{}{}}
\newlabel{thm:main@cref}{{[theorem][2][1]1.2}{[1][1][]1}}
"""
    labels = parse_aux_text(aux)
    assert labels["thm:main"].number == "1.2"
    assert labels["eq:x"].number == "2.1" and labels["eq:x"].page == "3"
    assert labels["it:a"].number == "(i)"
    assert "thm:main@cref" not in labels


# --- theorem declarations ----------------------------------------------------

def test_scan_decls_styles_counters():
    src = r"""
\theoremstyle{plain}
\newtheorem{theorem}{Теорема}[section]
\newtheorem{lemma}[theorem]{Лемма}
\newtheorem*{conj}{Гипотеза}
\theoremstyle{definition}
\newtheorem{definition}[theorem]{Определение}
"""
    d, style = scan_decls(src)
    assert style == "definition"
    assert d["theorem"].within == "section" and d["theorem"].style == "plain"
    assert d["lemma"].counter == "theorem"
    assert d["conj"].numbered is False
    assert d["definition"].style == "definition"


# --- flatten -----------------------------------------------------------------

def test_flatten_inputs(tmp_path: Path):
    (tmp_path / "sec").mkdir()
    (tmp_path / "sec" / "a.tex").write_text("A \\input{sec/b}", encoding="utf-8")
    (tmp_path / "sec" / "b.tex").write_text("B", encoding="utf-8")
    r = Report()
    out = flatten_text("x \\input{sec/a} y\n%\\input{gone}\n\\include{missing}", tmp_path, r)
    assert out.startswith("x A B y")
    assert [i.code for i in r.items] == ["flatten.missing-input"]


# --- normalize ---------------------------------------------------------------

def test_babel_shorthands():
    assert normalize_text('код "--- это') == "код --- это"
    assert normalize_text('Шура"=Адамара') == "Шура-Адамара"
    assert normalize_text(r'\"o') == r'\"o'


# --- pandoc message collection ----------------------------------------------

def test_collect_pandoc_messages(tmp_path: Path):
    ctx = Context(source=tmp_path / "m.tex", output=tmp_path / "m.docx",
                  workdir=tmp_path, config=Config())
    stderr = "\n".join([
        "[INFO] Skipped '\\foo{x}' at /w/pandoc_input.tex line 7 column 3",
        "[INFO] Skipped '\\maketitle' at /w/pandoc_input.tex line 9 column 1",
        "[INFO] Skipped '\\ProvidesPackage' at mine.sty line 2 column 1",
        "[WARNING] Could not convert TeX math \\bar{secret} + y, rendering as TeX:",
        "  \\bar{secret}",
        "  unexpected control sequence \\bar",
        "[t2d] warning crossref.unresolved eq:x",
    ])
    collect_pandoc_messages(stderr, "pandoc_input.tex", ctx)
    got = [(i.code, i.detail, i.line) for i in ctx.report.items]
    assert got == [
        ("pandoc.skipped", "\\foo", 7),
        ("pandoc.math-as-text", "\\bar", None),
        ("crossref.unresolved", "eq:x", None),
    ]
    # privacy: no document text in the report
    assert "secret" not in ctx.report.to_markdown()
