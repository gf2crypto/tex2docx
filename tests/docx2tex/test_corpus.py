"""docx2tex corpus: build each case's docx (make.py), convert, check expect.yaml.

Skipped until the docx2tex package exists (M0); xfail_* entries are the roadmap.
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

CORPUS = Path(__file__).parent / "corpus"
CASES = sorted(p.parent.name for p in CORPUS.glob("*/expect.yaml"))

needs_tools = pytest.mark.skipif(
    not all(shutil.which(t) for t in ("pandoc", "latexmk")), reason="pandoc and latexmk are required")
needs_docx2tex = pytest.mark.skipif(
    importlib.util.find_spec("docx2tex") is None, reason="docx2tex is not implemented yet (M0)")


def build_input(case: str) -> Path:
    subprocess.run([sys.executable, "-I", str(CORPUS / case / "make.py")], check=True)
    return CORPUS / case / "input.docx"


@pytest.fixture(scope="module", params=CASES)
def converted(request, tmp_path_factory):
    from docx2tex.pipeline import convert  # noqa: PLC0415 - exists from M0 on

    case = request.param
    out = tmp_path_factory.mktemp(case) / f"{case}.tex"
    convert(build_input(case), out, standalone=True)
    expect = yaml.safe_load((CORPUS / case / "expect.yaml").read_text(encoding="utf-8")) or {}
    report = json.loads(out.with_suffix(".report.json").read_text(encoding="utf-8"))
    tex = out.read_text(encoding="utf-8") if out.exists() else ""
    return case, expect, tex, report, out


@pytest.mark.e2e
@needs_tools
@needs_docx2tex
def test_strict(converted):
    case, expect, tex, report, out = converted
    assert tex, f"{case}: no .tex produced; report: {report}"
    for s in expect.get("tex_contains", []):
        assert s in tex, f"{case}: missing {s!r}"
    for s in expect.get("tex_not_contains", []):
        assert s not in tex, f"{case}: unexpected {s!r}"
    codes = {i["code"] for i in report}
    bad = codes & set(expect.get("report_absent", []))
    assert not bad, f"{case}: report has {bad}"
    if expect.get("compiles"):
        assert not any(i["code"] == "check.compile-errors" for i in report), f"{case}: does not compile"
    for pkg in expect.get("packages", []):
        assert any(i["code"] == "emit.package" and i["detail"] == pkg for i in report), \
            f"{case}: package {pkg} not required by the report"


def _xfail_items():
    for case in CASES:
        expect = yaml.safe_load((CORPUS / case / "expect.yaml").read_text(encoding="utf-8")) or {}
        for s in expect.get("xfail_tex_contains", []):
            yield pytest.param(case, s, id=f"{case}-{s!r}")


@pytest.mark.e2e
@needs_tools
@needs_docx2tex
@pytest.mark.xfail(reason="planned, see docs/docx2tex/roadmap.md", strict=False)
@pytest.mark.parametrize("case,item", list(_xfail_items()))
def test_planned(case, item, tmp_path):
    from docx2tex.pipeline import convert

    out = tmp_path / f"{case}.tex"
    convert(build_input(case), out)
    assert item in out.read_text(encoding="utf-8")
