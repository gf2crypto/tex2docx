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
        if data.get("reference_docx"):
            ref = Path(data["reference_docx"])
            data["reference_docx"] = ref if ref.is_absolute() else Path(path).parent / ref
        return cls(**data)
