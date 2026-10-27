"""Conversion settings. Defaults must work for a typical Russian math article."""

from __future__ import annotations

from dataclasses import dataclass, field, fields
from pathlib import Path

import yaml

ENGINES = ("pdflatex", "xelatex", "lualatex")


@dataclass
class Config:
    # TeX engine used for the "ask LaTeX" runs (numbering, figures).
    engine: str = "pdflatex"
    # Word style template; None means the bundled data/reference.docx.
    reference_docx: Path | None = None
    # Heading of the proof environment (pandoc writes English "Proof.").
    proof_name: str = "Доказательство"
    # amsthm \theoremstyle -> Word paragraph style name.
    theorem_styles: dict[str, str] = field(
        default_factory=lambda: {
            "plain": "Theorem",
            "definition": "Definition",
            "remark": "Remark",
        }
    )
    # Caption prefixes: "Рис. 1. ..." / "Таблица 1. ...". None = by babel language
    # (russian: Рис./Таблица and "."; otherwise Figure/Table and ":").
    figure_name: str | None = None
    table_name: str | None = None
    caption_sep: str | None = None
    # Manual macro overrides: {"\\matr": "\\mathbf"}. Applied before pandoc.
    macros: dict[str, str] = field(default_factory=dict)
    # Environments rendered as pictures via the preview package.
    figure_envs: list[str] = field(default_factory=lambda: ["tikzpicture", "algorithm", "algorithmic"])
    figure_dpi: int = 300
    # Numbers as Word fields (SEQ in bookmarks, references as REF), so that Word renumbers
    # after editing; plain-number objects only (ADR 0006). Off: numbers are text as in the PDF.
    live_numbers: bool = False
    # CSL style for the .bib bibliography; None = bundled GOST R 7.0.5-2008 numeric (ADR 0005).
    csl: Path | None = None
    # Formula texmath cannot convert: "image" (rendered by LaTeX, see stages/mathimg.py)
    # or "text" (left as raw TeX, as pandoc does).
    math_fallback: str = "image"
    # Seconds per LaTeX run.
    latex_timeout: int = 600

    def __post_init__(self) -> None:
        if self.engine not in ENGINES:
            raise ValueError(f"engine must be one of {ENGINES}, got {self.engine!r}")
        if self.math_fallback not in ("image", "text"):
            raise ValueError(f"math_fallback must be 'image' or 'text', got {self.math_fallback!r}")

    @classmethod
    def load(cls, path: Path | None) -> Config:
        if path is None:
            return cls()
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
        known = {f.name for f in fields(cls)}
        unknown = set(data) - known
        if unknown:
            raise ValueError(f"unknown config keys in {path}: {sorted(unknown)}")
        for key in ("reference_docx", "csl"):
            if data.get(key):
                ref = Path(data[key])
                data[key] = ref if ref.is_absolute() else Path(path).parent / ref
        return cls(**data)
