"""Fast unit tests: no external tools."""

from __future__ import annotations

import re
from pathlib import Path

from tex2docx.aux import parse_aux_text
from tex2docx.config import Config
from tex2docx.context import Context
from tex2docx.report import Report
from tex2docx.stages.autolabel import insert_labels
from tex2docx.stages.flatten import flatten_lines, flatten_text
from tex2docx.stages.normalize import normalize_text
from tex2docx.stages.macros import extract_definitions
from tex2docx.stages.pandoc_run import collect_pandoc_messages
from tex2docx.stages.postprocess import W, nbsp_text, process_document
from tex2docx.stages.theorems import scan_decls
from tex2docx.texmf import package_requests
from tex2docx.texscan import babel_languages, blank_comment_lines, read_group, strip_tex

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


def test_babel_languages():
    assert babel_languages(r"\usepackage[english,russian]{babel}") == ["english", "russian"]
    assert babel_languages(r"\usepackage[main=russian, english]{babel}") == ["russian", "english"]
    assert babel_languages(r"\usepackage{babel}") == []


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

def test_flatten_inputs_and_line_map(tmp_path: Path):
    (tmp_path / "sec").mkdir()
    (tmp_path / "sec" / "a.tex").write_text("A1\nA2 \\input{sec/b}", encoding="utf-8")
    (tmp_path / "sec" / "b.tex").write_text("B", encoding="utf-8")
    r = Report()
    src = "x \\input{sec/a} y\n%\\input{gone}\nz \\include{missing}"
    lines, origins = flatten_lines(src, tmp_path, r, "main.tex")
    assert lines == ["x ", "A1", "A2 ", "B", "", " y", "", "z \\include{missing}"]
    assert origins == [("main.tex", 1), ("sec/a.tex", 1), ("sec/a.tex", 2), ("sec/b.tex", 1),
                       ("sec/a.tex", 2), ("main.tex", 1), ("main.tex", 2), ("main.tex", 3)]
    assert [(i.code, i.line) for i in r.items] == [("flatten.missing-input", 8)]
    r.line_map, r.main_file = origins, "main.tex"
    assert r.locate(2) == "sec/a.tex:1" and r.locate(6) == "1" and r.locate(99) == "99"
    assert flatten_text(src, tmp_path, Report()) == "\n".join(lines)


# --- normalize ---------------------------------------------------------------

def test_babel_shorthands():
    assert normalize_text('код "--- это') == "код --- это"
    assert normalize_text('Шура"=Адамара') == "Шура-Адамара"
    assert normalize_text(r'\"o') == r'\"o'


def test_normalize_math_envs():
    assert normalize_text(r"\begin{alignat}{2} a \end{alignat}") == r"\begin{align} a \end{align}"
    assert normalize_text(r"\begin{alignat*}{3}") == r"\begin{align*}"
    assert normalize_text(r"\begin{flalign} \end{flalign}") == r"\begin{align} \end{align}"
    assert normalize_text("\\begin{subequations}\\label{s}\n\\begin{equation}\\label{a} x "
                          "\\end{equation}\n\\end{subequations}") \
        == "\n\\begin{equation}\\label{a} x \\end{equation}\n"


# --- postprocess -------------------------------------------------------------

def test_nbsp_text():
    assert nbsp_text("Пусть в поле и к нему") == "Пусть в\u00a0поле и\u00a0к\u00a0нему"
    assert nbsp_text("В начале. А потом") == "В\u00a0начале. А\u00a0потом"
    assert nbsp_text("код — это") == "код\u00a0— это"
    assert nbsp_text("или-или и т. д.") == "или-или и\u00a0т. д."
    assert nbsp_text("x и ") == "x и "  # nothing to glue to


def test_postprocess_qed_and_keep_next():
    from lxml import etree

    xml = f"""<w:document xmlns:w="{W}"><w:body>
<w:p><w:pPr><w:pStyle w:val="BodyText"/></w:pPr><w:r><w:t>intro:</w:t></w:r></w:p>
<w:p><w:pPr><w:pStyle w:val="Equation"/></w:pPr><w:r><w:tab/></w:r></w:p>
<w:p><w:pPr><w:pStyle w:val="Proof"/></w:pPr><w:r><w:rPr><w:i/></w:rPr><w:t>Proof.</w:t></w:r>
<w:r><w:t>done.\u00a0\u25fb</w:t></w:r></w:p>
<w:sectPr><w:pgSz w:w="11906"/><w:pgMar w:left="1417" w:right="1417"/></w:sectPr>
</w:body></w:document>"""
    root = etree.fromstring(xml)
    counts = process_document(root)
    assert counts["qed"] == 1 and counts["keep_next"] == 1
    paras = root.findall(f".//{{{W}}}p")
    assert paras[0].find(f"{{{W}}}pPr/{{{W}}}keepNext") is not None
    assert paras[1].find(f"{{{W}}}pPr/{{{W}}}keepNext") is None
    proof = paras[2]
    tab = proof.find(f"{{{W}}}pPr/{{{W}}}tabs/{{{W}}}tab")
    assert tab.get(f"{{{W}}}val") == "right" and tab.get(f"{{{W}}}pos") == "9072"
    texts = [t.text for t in proof.iter(f"{{{W}}}t")]
    assert texts == ["Proof.", "done.", "\u25fb"]
    assert proof.findall(f"{{{W}}}r/{{{W}}}tab")


# --- macros from personal packages -------------------------------------------

def test_extract_definitions():
    sty = r"""
\newcommand{\matr}[1]{\mathbf{#1}}
\newcommand\vect[1]{\boldsymbol{#1}}
\providecommand{\norm}[2][2]{\lVert #2 \rVert_{#1}}
\DeclareMathOperator*{\argmin}{arg\,min}
\def\eps{\varepsilon}
\def\pair#1#2{\langle #1, #2 \rangle}
\newcommand{\@secret}{x}
\newcommand{\usesecret}{\@secret}
\theoremstyle{plain}
\newtheorem{claim}{Claim}[section]
\newtheorem*{note}{Note}
"""
    defs, skipped = extract_definitions(sty)
    assert defs == [
        r"\newcommand{\matr}[1]{\mathbf{#1}}",
        r"\newcommand{\vect}[1]{\boldsymbol{#1}}",
        r"\providecommand{\norm}[2][2]{\lVert #2 \rVert_{#1}}",
        r"\DeclareMathOperator*{\argmin}{arg\,min}",
        r"\newcommand{\eps}{\varepsilon}",
        r"\theoremstyle{plain}",
        r"\newtheorem{claim}{Claim}[section]",
        r"\newtheorem*{note}{Note}",
    ]
    assert skipped == [r"\pair", r"\@secret", r"\usesecret"]


def test_package_requests():
    src = r"\documentclass[12pt]{amsart}\usepackage[utf8]{inputenc}\usepackage{a, b}\RequirePackage{c}"
    assert package_requests(src) == [("amsart.cls", "documentclass"), ("inputenc.sty", "usepackage"),
                                     ("a.sty", "usepackage"), ("b.sty", "usepackage"),
                                     ("c.sty", "RequirePackage")]


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


# --- autolabel ---------------------------------------------------------------

THM = {"theorem", "lemma"}


def _labels(text: str) -> list[str]:
    return re.findall(r"\\label\{(t2d:auto:\d+)\}", text)


def test_autolabel_theorems():
    src = "\\begin{document}\n\\begin{theorem}[Main]\nA\n\\end{theorem}\n" \
          "\\begin{lemma}\\label{lem:x}\nB\n\\end{lemma}\n" \
          "\\begin{conj}\nC\n\\end{conj}\n\\end{document}"
    out, n = insert_labels(src, THM)
    assert n == 1
    assert "\\begin{theorem}[Main]\\label{t2d:auto:1}\n" in out
    assert _labels(out) == ["t2d:auto:1"]
    assert out.count("\\label") == 2  # the lemma keeps its own label only


def test_autolabel_equation_and_starred():
    src = "\\begin{document}\n\\begin{equation}\na=b\n\\end{equation}\n" \
          "\\begin{equation*}\nc=d\n\\end{equation*}\n\\[ e=f \\]\n" \
          "\\begin{equation}\\label{eq:own} g=h \\end{equation}\n\\end{document}"
    out, n = insert_labels(src, set())
    assert n == 1
    assert "\\begin{equation}\\label{t2d:auto:1}\na=b" in out
    assert "equation*}\\label" not in out


def test_autolabel_align_lines():
    src = "\\begin{document}\n\\begin{align}\n" \
          "a &= \\begin{cases} 1, & x \\\\ 2, & y \\end{cases}, \\\\\n" \
          "b &= c, \\notag \\\\\n" \
          "d &= e, \\label{eq:d} \\\\\n" \
          "f &= \\substack{1 \\\\ 2}, \\\\[2pt]\n" \
          "g &= h.\n" \
          "\\end{align}\n\\end{document}"
    out, n = insert_labels(src, set())
    assert n == 3
    assert "\\end{cases}, \\label{t2d:auto:1}\\\\\n" in out
    assert "\\notag \\\\\n" in out and "\\label{eq:d} \\\\\n" in out
    assert "2}, \\label{t2d:auto:2}\\\\[2pt]\n" in out
    assert "g &= h.\\label{t2d:auto:3}\n\\end{align}" in out


def test_autolabel_align_trailing_linebreak_and_star():
    src = "\\begin{document}\n\\begin{gather}\na \\\\\nb \\\\\n\\end{gather}\n" \
          "\\begin{align*}\nc \\\\ d\n\\end{align*}\n\\end{document}"
    out, n = insert_labels(src, set())
    assert n == 3  # amsmath numbers the empty line after the trailing \\\\ as well
    assert "b \\label{t2d:auto:2}\\\\\\label{t2d:auto:3}\n\\end{gather}" in out
    assert "align*" in out and "d\\label" not in out


def test_autolabel_floats():
    src = "\\begin{document}\n\\begin{figure}\n\\caption{One}\n\\end{figure}\n" \
          "\\begin{figure*}\n\\caption{Two \\label{fig:two}}\n\\end{figure*}\n" \
          "\\begin{table}\n\\caption{Three}\\label{tab:3}\n\\end{table}\n" \
          "\\begin{figure}\nno caption\n\\end{figure}\n\\end{document}"
    out, n = insert_labels(src, set())
    assert n == 1
    assert "\\caption{One}\\label{t2d:auto:1}\n" in out


def test_autolabel_skips_verbatim_and_preamble():
    src = "\\newtheorem{theorem}{T}\n\\begin{document}\n" \
          "\\begin{verbatim}\n\\begin{equation}\nx\n\\end{equation}\n\\end{verbatim}\n" \
          "\\begin{theorem}\nA\n\\end{theorem}\n\\end{document}"
    out, n = insert_labels(src, THM)
    assert n == 1
    assert "\\begin{equation}\nx" in out


def test_autolabel_nested_equation_in_theorem():
    src = "\\begin{document}\n\\begin{theorem}\nA\n\\begin{equation}\\label{eq:in}\nx\n" \
          "\\end{equation}\n\\end{theorem}\n\\end{document}"
    out, n = insert_labels(src, THM)
    assert n == 1  # the equation's label does not count as the theorem's
    assert "\\begin{theorem}\\label{t2d:auto:1}\n" in out


def test_autolabel_subequations_source_order():
    src = "\\begin{document}\n\\begin{subequations}\n\\begin{equation} n \\end{equation}\n" \
          "\\end{subequations}\n\\end{document}"
    out, n = insert_labels(src, set())
    assert n == 2
    assert "\\begin{subequations}\\label{t2d:auto:1}\n\\begin{equation}\\label{t2d:auto:2} n" in out
