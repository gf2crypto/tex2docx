"""Regression tests for file safety and reporting at the conversion entry points."""

from __future__ import annotations

import re
import shutil
from pathlib import Path
from subprocess import CompletedProcess

import pytest
from docx import Document

from docx2tex.cli import main as docx_cli
from docx2tex.pipeline import OutputConflictError
from docx2tex.pipeline import convert as docx_to_tex
from tex2docx.cli import main as tex_cli
from tex2docx.pipeline import convert as tex_to_docx
from tex2docx.stages import pandoc_run
from tex2docx.tools import log_errors

from .docxprobe import DocxProbe

needs_pandoc = pytest.mark.skipif(not shutil.which("pandoc"), reason="pandoc is required")
needs_tex = pytest.mark.skipif(
    not all(shutil.which(tool) for tool in ("pandoc", "latexmk", "pdflatex")),
    reason="pandoc, latexmk and pdflatex are required",
)
PICTURE = Path(__file__).parent / "docx2tex" / "fixtures" / "pic.png"


def article(path: Path, body: str, preamble: str = "") -> Path:
    path.write_text(
        "\\documentclass{article}\n" + preamble
        + "\\begin{document}\n" + body + "\n\\end{document}\n",
        encoding="utf-8",
    )
    return path


def test_into_refuses_to_replace_main_document(tmp_path, capsys):
    source = tmp_path / "main.docx"
    doc = Document()
    doc.add_paragraph("Text from Word.")
    doc.save(source)
    main = article(tmp_path / "main.tex", "Original LaTeX.")
    original = main.read_bytes()

    with pytest.raises(SystemExit) as err:
        docx_cli([str(source), "--into", str(main)])
    assert err.value.code == 1
    assert "would overwrite" in capsys.readouterr().err
    assert main.read_bytes() == original

    with pytest.raises(OutputConflictError):
        docx_to_tex(source, main, into=main)
    assert main.read_bytes() == original


def test_into_protects_main_from_standalone_output(tmp_path):
    source = tmp_path / "chapter.docx"
    main = article(tmp_path / "chapter.standalone.tex", "Original LaTeX.")
    with pytest.raises(OutputConflictError):
        docx_to_tex(source, tmp_path / "chapter.tex", into=main, standalone=True)


@pytest.mark.e2e
@needs_pandoc
def test_images_from_two_word_documents_coexist(tmp_path):
    # Both DOCX packages use word/media/image1.png. A different byte sequence
    # reproduces the collision without depending on an optional image library.
    second_picture = tmp_path / "second.png"
    second_picture.write_bytes(PICTURE.read_bytes() + b"second")
    inputs = []
    for name, picture in (("first", PICTURE), ("second", second_picture)):
        source = tmp_path / f"{name}.docx"
        doc = Document()
        doc.add_picture(str(picture))
        doc.save(source)
        inputs.append((source, picture.read_bytes()))

    fragments = []
    for source, image in inputs:
        fragment = source.with_suffix(".tex")
        report = docx_to_tex(source, fragment)
        assert report.output_written
        text = fragment.read_text(encoding="utf-8")
        match = re.search(r"\\includegraphics\{([^}]+)\}", text)
        assert match
        fragments.append((tmp_path / match[1], image))

    assert fragments[0][0] != fragments[1][0]
    for path, expected in fragments:
        assert path.read_bytes() == expected

    first = inputs[0][0]
    fragment = first.with_suffix(".tex")
    old_text = fragment.read_bytes()
    assert docx_to_tex(first, fragment).output_written
    assert fragment.read_bytes() == old_text


@pytest.mark.parametrize(
    "cli,in_ext,out_ext",
    [(tex_cli, ".tex", ".docx"), (docx_cli, ".docx", ".tex")],
)
def test_fatal_run_cannot_report_old_output_as_success(tmp_path, capsys, cli, in_ext, out_ext):
    source = tmp_path / ("missing" + in_ext)
    output = tmp_path / ("result" + out_ext)
    output.write_bytes(b"previous output")
    sidecar = output.with_suffix(".t2d.xml")
    sidecar.write_bytes(b"previous sidecar")

    assert cli([str(source), "-o", str(output)]) == 1
    assert "FAILED" in capsys.readouterr().out
    assert output.read_bytes() == b"previous output"
    assert sidecar.read_bytes() == b"previous sidecar"


@pytest.mark.e2e
@needs_tex
def test_reused_workdir_cannot_supply_aux_from_another_document(tmp_path):
    workdir = tmp_path / "work"
    first = article(tmp_path / "first.tex", r"\section{First}\label{sec:first}")
    first_out = tmp_path / "first.docx"
    assert tex_to_docx(first, first_out, workdir=workdir).output_written
    assert len(list(workdir.glob("*/latex/main.aux"))) == 1

    second = article(
        tmp_path / "second.tex", r"See \ref{sec:first}.",
        "\\usepackage{t2d-review-missing-package}\n",
    )
    second_out = tmp_path / "second.docx"
    report = tex_to_docx(second, second_out, workdir=workdir)
    assert report.output_written
    assert "crossref.unresolved" in {item.code for item in report.items}
    assert "[sec:first]" in DocxProbe.open(second_out).text


@pytest.mark.e2e
@needs_tex
def test_shareable_report_omits_latex_error_message(tmp_path):
    secret = "PRIVATE_DOCUMENT_SENTENCE"
    source = article(
        tmp_path / "main.tex", r"Text. \PackageError{review}{" + secret + "}{Help}",
    )
    output = source.with_suffix(".docx")
    workdir = tmp_path / "work"
    report = tex_to_docx(source, output, workdir=workdir)

    assert report.output_written
    assert ("Package review Error", 3) in {
        (item.detail, item.line) for item in report.items if item.code == "latex.log"
    }
    for path in report.paths(output):
        assert secret not in path.read_text(encoding="utf-8")
    log, = workdir.glob("*/latex/main.log")
    assert secret in log.read_text(encoding="utf-8")


def test_log_errors_allow_only_error_categories_and_line_numbers(tmp_path):
    log = tmp_path / "main.log"
    log.write_text(
        "C:\\Some Directory\\main.tex:12: Package review Error: PRIVATE_TEXT\n"
        "! PRIVATE_OTHER_TEXT\n"
        "./package.sty:3: LaTeX Error: PRIVATE_LATEX_TEXT\n",
        encoding="utf-8",
    )
    assert log_errors(log) == [
        ("Package review Error", 12), ("TeX error", None), ("LaTeX Error", None)
    ]


def test_pandoc_failure_does_not_copy_stderr(tmp_path, monkeypatch):
    source = article(tmp_path / "main.tex", "Text.")
    output = source.with_suffix(".docx")
    monkeypatch.setattr(
        pandoc_run, "_pandoc",
        lambda *args: CompletedProcess([], 65, stderr="PRIVATE_PANDOC_TEXT"),
    )
    monkeypatch.setattr(
        "tex2docx.stages.latex_compile.latexmk", lambda *args, **kwargs: CompletedProcess([], 0)
    )

    report = tex_to_docx(source, output)
    assert not report.output_written
    assert ("pandoc.failed", "exit 65") in {(item.code, item.detail) for item in report.items}
    for path in report.paths(output):
        assert "PRIVATE_PANDOC_TEXT" not in path.read_text(encoding="utf-8")
