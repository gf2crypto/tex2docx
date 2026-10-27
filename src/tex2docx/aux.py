"""Parse LaTeX .aux files: label -> number exactly as LaTeX printed it."""

from __future__ import annotations

import re
from pathlib import Path

from .context import Label
from .texscan import read_group, strip_tex

_NEWLABEL = re.compile(r"\\newlabel\{")
_BIBCITE = re.compile(r"\\bibcite\{([^{}]+)\}\{")
_INPUT = re.compile(r"\\@input\{([^}]+)\}")


def parse_aux_text(text: str) -> dict[str, Label]:
    """\\newlabel{name}{{number}{page}...} with arbitrary extra hyperref fields."""
    labels: dict[str, Label] = {}
    cref_types: dict[str, str] = {}
    for m in _NEWLABEL.finditer(text):
        try:
            name, pos = read_group(text, m.end() - 1)
            body, _ = read_group(text, pos)
            if name.endswith("@cref"):  # cleveref: {{[theorem][1][1]1.1}{...}}
                t = re.match(r"\{\[(\w+)\]", body)
                if t:
                    cref_types[name[: -len("@cref")]] = t.group(1)
                continue
            number, p2 = read_group(body, 0)
            page = ""
            if p2 < len(body) and body[p2] == "{":
                page, _ = read_group(body, p2)
            labels[name] = Label(name=name, number=strip_tex(number), page=strip_tex(page))
        except ValueError:
            continue  # malformed entry: skip, LaTeX itself would complain
    for name, typ in cref_types.items():
        if name in labels:
            labels[name].cref_type = typ
    return labels


def parse_bibcites(text: str) -> dict[str, str]:
    """\\bibcite{key}{label} (thebibliography / BibTeX): key -> number as printed."""
    out: dict[str, str] = {}
    for m in _BIBCITE.finditer(text):
        try:
            label, _ = read_group(text, m.end() - 1)
        except ValueError:
            continue
        out[m.group(1)] = strip_tex(label)
    return out


def _aux_files(path: Path) -> list[Path]:
    if not path.is_file():
        return []
    text = path.read_text(encoding="utf-8", errors="replace")
    files = [path]
    for sub in _INPUT.findall(text):
        files += _aux_files(path.parent / sub)
    return files


def parse_aux(path: Path) -> dict[str, Label]:
    """Parse an .aux file and the files it pulls in via \\@input (\\include)."""
    labels: dict[str, Label] = {}
    for f in _aux_files(path):
        labels.update(parse_aux_text(f.read_text(encoding="utf-8", errors="replace")))
    return labels


def parse_aux_bibcites(path: Path) -> dict[str, str]:
    """\\bibcite from the main .aux, its \\@input files and the other .aux files of the
    run (multibbl writes one per bibliography)."""
    out: dict[str, str] = {}
    files = _aux_files(path)
    files += [p for p in sorted(path.parent.glob("*.aux")) if p not in files]
    for f in files:
        out.update(parse_bibcites(f.read_text(encoding="utf-8", errors="replace")))
    return out
