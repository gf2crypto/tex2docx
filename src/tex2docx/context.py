"""Shared state passed through the pipeline stages."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .config import Config
from .report import Report


@dataclass
class Label:
    name: str
    number: str  # exactly as LaTeX printed it, e.g. "1.2" or "(i)"
    page: str = ""
    cref_type: str = ""  # counter name from cleveref's name@cref entry, e.g. "theorem"


@dataclass
class TheoremDecl:
    env: str
    title: str
    style: str = "plain"  # amsthm: plain | definition | remark (or custom)
    numbered: bool = True  # False for \newtheorem*
    counter: str | None = None  # shared counter: \newtheorem{lemma}[theorem]{...}
    within: str | None = None  # \newtheorem{theorem}{...}[section]


@dataclass
class Context:
    source: Path  # absolute path to the main .tex
    output: Path  # target .docx
    workdir: Path  # all intermediate files live here, never next to the source
    config: Config
    report: Report = field(default_factory=Report)

    # Two views of the same flattened source:
    #   latex_tex - what real LaTeX compiles (flatten + autolabel only);
    #   tex       - what pandoc reads (additionally normalized/rewritten).
    # Stages that change structure (autolabel) must change both in the same way.
    latex_tex: str = ""
    tex: str = ""
    # Origin of every line of the flattened text: (file relative to source_dir, line).
    # Stages must keep the line count of both views so that this stays valid.
    line_map: list[tuple[str, int]] = field(default_factory=list)

    # Personal packages/classes (outside the TeX distribution and the source dir),
    # name -> path; filled once by texmf.personal_packages(). None = not resolved yet.
    packages: dict[str, Path] | None = None
    labels: dict[str, Label] = field(default_factory=dict)  # from .aux
    bibcites: dict[str, str] = field(default_factory=dict)  # \bibcite key -> number (thebibliography)
    theorems: dict[str, TheoremDecl] = field(default_factory=dict)
    figures: list[Path] = field(default_factory=list)  # rendered images, source order
    docx: Path | None = None  # pandoc output before postprocessing

    @property
    def source_dir(self) -> Path:
        return self.source.parent
