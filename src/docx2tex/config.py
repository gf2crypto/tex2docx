"""docx2tex settings. The same YAML as tex2docx may carry a `docx2tex:` section;
top-level keys that docx2tex knows are accepted as well."""

from __future__ import annotations

from dataclasses import dataclass, field, fields
from pathlib import Path

import yaml

# Word of a theorem header -> amsthm environment (lower-cased, without the number).
DEFAULT_THEOREM_ENVS: dict[str, str] = {
    "теорема": "theorem", "лемма": "lemma", "следствие": "corollary",
    "предложение": "proposition", "утверждение": "proposition", "определение": "definition",
    "замечание": "remark", "пример": "example", "гипотеза": "conjecture", "задача": "problem",
    "theorem": "theorem", "lemma": "lemma", "corollary": "corollary", "proposition": "proposition",
    "definition": "definition", "remark": "remark", "example": "example", "conjecture": "conjecture",
}


@dataclass
class Config:
    # TeX engine for the --standalone self-check.
    engine: str = "pdflatex"
    # Header word -> environment; merged over DEFAULT_THEOREM_ENVS.
    theorem_envs: dict[str, str] = field(default_factory=dict)
    # Folder (relative to the output .tex) for images extracted from the docx.
    images_dir: str = "images"
    # Document language when neither the sidecar nor the text decides: babel name.
    language: str | None = None
    # LaTeX macros of the main document to fold back: {"\\matr": "\\mathbf"} means that
    # \mathbf{X} in the fragment becomes \matr{X} (M2).
    macros: dict[str, str] = field(default_factory=dict)

    def theorem_env(self, word: str) -> str | None:
        return {**DEFAULT_THEOREM_ENVS, **self.theorem_envs}.get(word.lower().strip())

    @classmethod
    def load(cls, path: Path | None) -> Config:
        if path is None:
            return cls()
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
        section = data.get("docx2tex") or {}
        known = {f.name for f in fields(cls)}
        merged = {k: v for k, v in data.items() if k in known}
        merged.update({k: v for k, v in section.items()})
        unknown = set(section) - known
        if unknown:
            raise ValueError(f"unknown docx2tex config keys in {path}: {sorted(unknown)}")
        return cls(**merged)
