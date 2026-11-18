"""The round trip tex -> docx -> tex -> docx over the tex2docx corpus (M3 of docx2tex).

Checks, per docs/docx2tex/roundtrip-contract.md:
1. the .tex from docx2tex, put back into the original preamble, compiles and its .aux
   has the same labels with the same numbers;
2. tex2docx over that .tex gives a docx whose probe equals the first one;
3. a third round changes nothing (idempotent).
"""

from __future__ import annotations

import importlib.util
import json
import re
import shutil
from pathlib import Path

import pytest

from tex2docx.auxfile import parse_aux, parse_aux_bibcites
from tex2docx.pipeline import convert as tex_to_docx

from ..docxprobe import DocxProbe

CORPUS = Path(__file__).parents[1] / "corpus"
# cases whose body can be swapped (single file, no personal texmf, pdflatex)
CASES = ["basic", "numbering", "thmtools", "livenumbers", "thebib", "template", "roundtrip-stress"]

needs_all = pytest.mark.skipif(
    importlib.util.find_spec("docx2tex") is None
    or not all(shutil.which(t) for t in ("pandoc", "latexmk", "pdftoppm")),
    reason="docx2tex (M0) and the TeX tools are required")

_BODY = re.compile(r"\\begin\{document\}.*\\end\{document\}", re.S)


def with_body(main_tex: str, body: str) -> str:
    return _BODY.sub(lambda _: "\\begin{document}\n" + body + "\n\\end{document}", main_tex)


def roundtrip_aux(workdir: Path) -> Path:
    # --workdir retains a unique run directory under the requested path.
    aux_files = list(workdir.glob("*/latex/main.aux"))
    assert len(aux_files) == 1, f"expected one main.aux under {workdir}, got {aux_files}"
    return aux_files[0]


def label_numbers(aux: Path) -> dict[str, str]:
    return {
        name: label.number
        for name, label in parse_aux(aux).items()
        if not name.startswith("t2d:auto:")
    }


def assert_roundtrip_numbers(before: Path, after: Path) -> None:
    orig_aux, converted_aux = roundtrip_aux(before), roundtrip_aux(after)
    original = label_numbers(orig_aux)
    converted = label_numbers(converted_aux)
    mismatches = {
        name: (number, converted.get(name))
        for name, number in original.items()
        if converted.get(name) != number
    }
    assert not mismatches, f"changed or missing LaTeX label numbers: {mismatches}"

    original_cites = parse_aux_bibcites(orig_aux)
    converted_cites = parse_aux_bibcites(converted_aux)
    assert original or original_cites, f"no author labels or citations in {orig_aux}"
    assert converted_cites == original_cites, "LaTeX citation numbers changed after the round trip"


@pytest.mark.parametrize("number", ["2", None], ids=["changed-label", "missing-label"])
def test_aux_comparison_detects_numbering_regressions(tmp_path: Path, number: str | None):
    before, after = tmp_path / "before", tmp_path / "after"
    for workdir, value in [(before, "1"), (after, number)]:
        aux = workdir / "t2d-run" / "latex" / "main.aux"
        aux.parent.mkdir(parents=True)
        aux.write_text(
            rf"\newlabel{{eq:test}}{{{{{value}}}{{1}}}}" if value is not None else r"\relax",
            encoding="utf-8",
        )
    with pytest.raises(AssertionError, match="changed or missing LaTeX label numbers.*eq:test"):
        assert_roundtrip_numbers(before, after)
    (after / "t2d-run" / "latex" / "main.aux").unlink()
    with pytest.raises(AssertionError, match="expected one main.aux"):
        assert_roundtrip_numbers(before, after)


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
    before, after = work / "wd0", work / "wd1"
    assert tex_to_docx(main, a_docx, workdir=before).output_written
    a_tex = work / "a.tex"
    docx_to_tex(a_docx, a_tex)
    # theorem names come back without their numbers ("Лемма", not "Лемма 2.3")
    # both tools ran in one folder on one name: each keeps its own report (stress run, item 23)
    assert (work / "a.report.md").read_text(encoding="utf-8").startswith("# Отчет tex2docx")
    report_path = work / "a.docx2tex.report.json"
    d2t_md = (work / "a.docx2tex.report.md").read_text(encoding="utf-8")
    assert d2t_md.startswith("# Отчет docx2tex")
    report = json.loads(report_path.read_text(encoding="utf-8"))
    titles = [i["detail"] for i in report if i["code"] == "emit.newtheorem"]
    assert not [t for t in titles if re.search(r"\d", t)], f"{case}: numbered names {titles}"

    # 1. same numbering after compiling the fragment inside the original preamble
    round1 = work / "round1.tex"
    round1.write_text(with_body(main.read_text(encoding="utf-8"), a_tex.read_text(encoding="utf-8")),
                      encoding="utf-8")
    b_docx = work / "b.docx"
    assert tex_to_docx(round1, b_docx, workdir=after).output_written
    assert_roundtrip_numbers(before, after)

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
    report = (work / "chapter.docx2tex.report.md").read_text(encoding="utf-8")
    assert "label.unmapped" not in report


@needs_all
@pytest.mark.e2e
def test_into_main_document_with_bib(tmp_path: Path):
    """--into main.tex: citations get the keys of the main document's .bib by the text of
    the reference list, the list itself is dropped (the main document prints it), and the
    report says what the preamble lacks and how to \\input the fragment."""
    from docx2tex.pipeline import convert as docx_to_tex

    work = tmp_path / "bibliography"
    shutil.copytree(CORPUS / "bibliography", work)
    tex_to_docx(work / "main.tex", work / "chapter.docx")
    (work / "chapter.t2d.xml").unlink()  # the list is matched by text, not by the sidecar
    docx_to_tex(work / "chapter.docx", work / "chapter.tex", into=work / "main.tex")
    tex = (work / "chapter.tex").read_text(encoding="utf-8")
    assert "\\cite{knuth2000,lamport1978}" in tex
    assert "thebibliography" not in tex and "bib:1" not in tex
    report = (work / "chapter.docx2tex.report.md").read_text(encoding="utf-8")
    assert "bib.matched" in report and "into.input" in report
    assert "into.missing" not in report
