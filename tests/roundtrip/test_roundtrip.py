"""The round trip tex -> docx -> tex -> docx over the tex2docx corpus (M3 of docx2tex).

Checks, per docs/docx2tex/roundtrip-contract.md:
1. the .tex from docx2tex, put back into the original preamble, compiles and its .aux
   has the same labels with the same numbers;
2. tex2docx over that .tex gives a docx whose probe equals the first one;
3. a third round changes nothing (idempotent).
"""

from __future__ import annotations

import importlib.util
import re
import shutil
from pathlib import Path

import pytest

from tex2docx.auxfile import parse_aux
from tex2docx.pipeline import convert as tex_to_docx

from ..docxprobe import DocxProbe

CORPUS = Path(__file__).parents[1] / "corpus"
# cases whose body can be swapped (single file, no personal texmf, pdflatex)
CASES = ["basic", "numbering", "thmtools", "livenumbers", "thebib", "template"]

needs_all = pytest.mark.skipif(
    importlib.util.find_spec("docx2tex") is None
    or not all(shutil.which(t) for t in ("pandoc", "latexmk", "pdftoppm")),
    reason="docx2tex (M0) and the TeX tools are required")

_BODY = re.compile(r"\\begin\{document\}.*\\end\{document\}", re.S)


def with_body(main_tex: str, body: str) -> str:
    return _BODY.sub(lambda _: "\\begin{document}\n" + body + "\n\\end{document}", main_tex)


@needs_all
@pytest.mark.e2e
@pytest.mark.parametrize("case", CASES)
def test_roundtrip(case: str, tmp_path: Path):
    from docx2tex.pipeline import convert as docx_to_tex

    src = CORPUS / case
    work = tmp_path / case
    shutil.copytree(src, work)
    main = work / "main.tex"
    a_docx = work / "a.docx"
    tex_to_docx(main, a_docx)
    a_tex = work / "a.tex"
    docx_to_tex(a_docx, a_tex)

    # 1. same numbering after compiling the fragment inside the original preamble
    round1 = work / "round1.tex"
    round1.write_text(with_body(main.read_text(encoding="utf-8"), a_tex.read_text(encoding="utf-8")),
                      encoding="utf-8")
    b_docx = work / "b.docx"
    tex_to_docx(round1, b_docx, workdir=work / "wd1")
    orig = {k: v.number for k, v in parse_aux(work / "wd0" / "latex" / "main.aux").items()
            if not k.startswith("t2d:auto:")} if (work / "wd0").exists() else None
    if orig is not None:
        new = {k: v.number for k, v in parse_aux(work / "wd1" / "latex" / "main.aux").items()}
        assert orig.items() <= new.items(), f"{case}: numbering changed after the round trip"

    # 2. the second docx looks like the first one
    pa, pb = DocxProbe.open(a_docx), DocxProbe.open(b_docx)
    assert pb.text == pa.text, f"{case}: text differs after the round trip"
    assert (pb.math, pb.images, pb.styles) == (pa.math, pa.images, pa.styles)

    # 3. idempotent: a third pass changes nothing
    b_tex = work / "b.tex"
    docx_to_tex(b_docx, b_tex)
    assert b_tex.read_text(encoding="utf-8") == a_tex.read_text(encoding="utf-8"), \
        f"{case}: the fragment keeps changing between rounds"


@needs_all
@pytest.mark.e2e
def test_sidecar_inside_the_docx_is_enough(tmp_path: Path):
    """The companion file may get lost (docx mailed, renamed): the copy inside the docx
    (customXml) still gives the labels back."""
    from docx2tex.pipeline import convert as docx_to_tex

    work = tmp_path / "basic"
    shutil.copytree(CORPUS / "basic", work)
    a_docx = work / "a.docx"
    tex_to_docx(work / "main.tex", a_docx)
    (work / "a.t2d.xml").unlink()
    renamed = work / "chapter.docx"
    a_docx.rename(renamed)
    docx_to_tex(renamed, work / "chapter.tex")
    tex = (work / "chapter.tex").read_text(encoding="utf-8")
    assert "\\begin{equation}\\label{eq:square}" in tex
    assert "\\eqref{eq:square}" in tex
    assert "label.unmapped" not in (work / "chapter.report.md").read_text(encoding="utf-8")
