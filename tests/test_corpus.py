"""End-to-end: every tests/corpus/<case>/main.tex is converted and checked
against tests/corpus/<case>/expect.yaml.

xfail_* entries are the executable roadmap: when one starts passing,
pytest reports XPASS - move it to the strict list.
"""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

import pytest
import yaml

from tex2docx.pipeline import convert

from .docxprobe import DocxProbe

CORPUS = Path(__file__).parent / "corpus"
CASES = sorted(p.parent.name for p in CORPUS.glob("*/main.tex"))

needs_tools = pytest.mark.skipif(
    not all(shutil.which(t) for t in ("pandoc", "latexmk", "pdftoppm")),
    reason="pandoc, latexmk and pdftoppm are required",
)


def convert_case(case: str, out: Path) -> None:
    """Convert a corpus case. A texmf/ folder in the case plays the user's personal
    texmf tree: it is prepended to TEXMFHOME for the duration of the conversion."""
    texmf = CORPUS / case / "texmf"
    saved = os.environ.get("TEXMFHOME")
    if texmf.is_dir():
        os.environ["TEXMFHOME"] = "{" + str(texmf) + ("," + saved if saved else "") + "}"
    try:
        convert(CORPUS / case / "main.tex", out)
    finally:
        if texmf.is_dir():
            if saved is None:
                del os.environ["TEXMFHOME"]
            else:
                os.environ["TEXMFHOME"] = saved


@pytest.fixture(scope="module", params=CASES)
def converted(request, tmp_path_factory):
    case = request.param
    out = tmp_path_factory.mktemp(case) / f"{case}.docx"
    convert_case(case, out)
    expect = yaml.safe_load((CORPUS / case / "expect.yaml").read_text(encoding="utf-8")) or {}
    report = json.loads(out.with_suffix(".report.json").read_text(encoding="utf-8"))
    probe = DocxProbe.open(out) if out.exists() else None
    return case, expect, probe, report


@pytest.mark.e2e
@needs_tools
def test_strict(converted):
    case, expect, probe, report = converted
    assert probe is not None, f"{case}: no docx produced; report: {report}"
    for s in expect.get("contains", []):
        assert s in probe.text, f"{case}: missing {s!r}"
    for s in expect.get("not_contains", []):
        assert s not in probe.text, f"{case}: unexpected {s!r}"
    assert probe.math >= expect.get("math_min", 0)
    assert probe.images >= expect.get("images_min", 0)
    missing_styles = set(expect.get("styles", [])) - probe.styles
    assert not missing_styles, f"{case}: styles not used: {missing_styles}"
    codes = {i["code"] for i in report}
    bad = codes & set(expect.get("report_absent", []))
    assert not bad, f"{case}: report has {bad}"


def _xfail_items():
    for case in CASES:
        expect = yaml.safe_load((CORPUS / case / "expect.yaml").read_text(encoding="utf-8")) or {}
        for s in expect.get("xfail_contains", []):
            yield pytest.param(case, "contains", s, id=f"{case}-contains-{s!r}")
        for c in expect.get("xfail_report_absent", []):
            yield pytest.param(case, "report_absent", c, id=f"{case}-report-{c}")


@pytest.mark.e2e
@needs_tools
@pytest.mark.xfail(reason="planned, see ROADMAP.md", strict=False)
@pytest.mark.parametrize("case,kind,item", list(_xfail_items()))
def test_planned(case, kind, item, tmp_path):
    out = tmp_path / f"{case}.docx"
    convert_case(case, out)
    if kind == "contains":
        assert item in DocxProbe.open(out).text
    else:
        report = json.loads(out.with_suffix(".report.json").read_text(encoding="utf-8"))
        assert item not in {i["code"] for i in report}
