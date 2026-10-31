"""A small .bib reader and a matcher of bibliography paragraphs against its entries (M3).

The docx carries the reference list as text ("Кнут Д. Искусство программирования. М.:
Вильямс, 2000."); the main document keeps a .bib. An entry matches a paragraph when the
entry's title (letters and digits only, case-folded) occurs in the paragraph, or when
the first author's surname and the year both occur. No guessing beyond that: an
unmatched paragraph is reported, not invented.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

from tex2docx.texscan import read_group, skip_ws


@dataclass
class Entry:
    key: str
    kind: str
    fields: dict[str, str] = field(default_factory=dict)

    @property
    def title(self) -> str:
        return self.fields.get("title", "")

    @property
    def year(self) -> str:
        return re.sub(r"\D", "", self.fields.get("year", ""))

    @property
    def surname(self) -> str:
        author = self.fields.get("author", "")
        first = re.split(r"\s+and\s+", author, maxsplit=1)[0]
        if "," in first:
            return first.split(",", 1)[0].strip()
        return first.strip().split()[-1] if first.strip() else ""


_ENTRY = re.compile(r"@(\w+)\s*\{\s*([^,\s]+)\s*,")
_FIELD = re.compile(r"\s*(\w+)\s*=\s*")


def parse_bib(text: str) -> list[Entry]:
    out: list[Entry] = []
    for m in _ENTRY.finditer(text):
        kind = m.group(1).lower()
        if kind in ("comment", "preamble", "string"):
            continue
        e = Entry(key=m.group(2), kind=kind)
        pos = m.end()
        while True:
            pos = skip_ws(text, pos)
            if pos >= len(text) or text[pos] == "}":
                break
            if text[pos] == ",":
                pos += 1
                continue
            fm = _FIELD.match(text, pos)
            if not fm:
                break
            name, pos = fm.group(1).lower(), fm.end()
            if pos < len(text) and text[pos] == "{":
                value, pos = read_group(text, pos)
            elif pos < len(text) and text[pos] == '"':
                end = text.find('"', pos + 1)
                value, pos = (text[pos + 1:end], end + 1) if end > 0 else ("", len(text))
            else:
                vm = re.match(r"[^,}\s]+", text[pos:])
                value, pos = (vm.group(0), pos + len(vm.group(0))) if vm else ("", pos)
            e.fields[name] = value.strip()
        out.append(e)
    return out


def read_bibs(paths: list[Path]) -> list[Entry]:
    entries: list[Entry] = []
    for p in paths:
        entries += parse_bib(p.read_text(encoding="utf-8", errors="replace"))
    return entries


def fold(text: str) -> str:
    """Letters and digits only, case-folded, accents stripped: the matching key."""
    text = re.sub(r"\\[A-Za-z]+", " ", text)
    text = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in text.casefold() if ch.isalnum())


def match_entry(paragraph: str, entries: list[Entry]) -> Entry | None:
    folded = fold(paragraph)
    for e in entries:
        t = fold(e.title)
        if len(t) >= 8 and t in folded:
            return e
    for e in entries:
        s, y = fold(e.surname), e.year
        if s and y and s in folded and y in folded:
            return e
    return None
