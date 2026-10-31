"""Shared state of the docx2tex pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from tex2docx.report import Report
from tex2docx.sidecar import Sidecar

from .config import Config


@dataclass
class Context:
    source: Path  # the .docx
    output: Path  # the .tex fragment
    workdir: Path
    config: Config
    standalone: bool = False
    prepared: Path | None = None  # working copy of the docx with markers (stages/extract.py)
    report: Report = field(default_factory=Report)
    sidecar: Sidecar = field(default_factory=Sidecar)
    language: str = "english"
    # facts from the docx XML that pandoc drops
    bookmarks: dict[str, str] = field(default_factory=dict)  # bookmark name -> text inside
    fields: list[str] = field(default_factory=list)  # w:instr of simple fields, in order
    # pipeline products
    tex: str = ""  # the fragment
    packages: list[str] = field(default_factory=list)  # what the fragment needs
    theorem_envs_used: dict[str, str] = field(default_factory=dict)  # env -> title

    @property
    def source_dir(self) -> Path:
        return self.source.parent
