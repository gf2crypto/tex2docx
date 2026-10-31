"""The main LaTeX document the fragment goes into (--into main.tex, M3): its theorem
declarations, simple macros, packages, language and .bib files. Read only; never written."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from tex2docx.stages.sidecar import simple_macros
from tex2docx.stages.theorems import collect_decls
from tex2docx.texmf import package_requests
from tex2docx.texscan import document_language

from .bibtex import Entry, read_bibs

_BIB = re.compile(r"(?<!\\)\\(?:bibliography|addbibresource)\s*(?:\{[^{}]*\}\s*)?\{([^{}]+)\}")
_THEBIB = re.compile(r"\\begin\{thebibliography\}")


@dataclass
class MainDoc:
    path: Path
    text: str
    theorems: dict[str, dict[str, str]] = field(default_factory=dict)  # env -> sidecar-style attrs
    macros: dict[str, str] = field(default_factory=dict)
    packages: set[str] = field(default_factory=set)
    language: str = ""
    bib_paths: list[Path] = field(default_factory=list)
    bib_entries: list[Entry] = field(default_factory=list)
    has_thebibliography: bool = False


def read_main(path: Path) -> MainDoc:
    text = path.read_text(encoding="utf-8", errors="replace")
    md = MainDoc(path=path, text=text)
    for env, d in collect_decls(path.parent, text).items():
        attrs = {"title": d.title, "style": d.style, "numbered": str(d.numbered).lower()}
        if d.within:
            attrs["within"] = d.within
        md.theorems[env] = attrs
    local = "".join(p.read_text(encoding="utf-8", errors="replace")
                    for p in sorted(path.parent.glob("*.sty")))
    md.macros = simple_macros(local + text)
    md.packages = {name.rsplit(".", 1)[0] for name, _ in package_requests(text)}
    lang, guessed = document_language(text)
    md.language = "" if guessed else lang
    for m in _BIB.finditer(text):
        for name in m.group(1).split(","):
            name = name.strip()
            if not name:
                continue
            cand = path.parent / name
            for p in (cand, cand.with_name(cand.name + ".bib")):
                if p.is_file():
                    md.bib_paths.append(p)
                    break
    md.bib_entries = read_bibs(md.bib_paths)
    md.has_thebibliography = _THEBIB.search(text) is not None
    return md
