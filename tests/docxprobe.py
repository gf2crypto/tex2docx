"""Read a produced .docx for assertions: text without math, math count, styles."""

from __future__ import annotations

import re
import zipfile
from dataclasses import dataclass
from pathlib import Path

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


@dataclass
class DocxProbe:
    text: str  # paragraph texts joined by "\n"; math is excluded, tabs kept
    math: int
    images: int
    styles: set[str]
    fields: list[str]  # w:instr of every simple field, in document order

    @classmethod
    def open(cls, path: Path) -> DocxProbe:
        from lxml import etree

        xml = zipfile.ZipFile(path).read("word/document.xml")
        root = etree.fromstring(xml)
        paras = []
        for p in root.iter(f"{W}p"):
            parts = []
            for el in p.iter(f"{W}t", f"{W}tab"):
                # w:t inside math (m:r) is excluded: we only test prose here
                if any(a.tag.startswith("{http://schemas.openxmlformats.org/officeDocument/2006/math}")
                       for a in el.iterancestors()):
                    continue
                if el.tag == f"{W}tab" and el.getparent().tag != f"{W}r":
                    continue  # a tab stop definition in w:pPr/w:tabs, not a character
                parts.append("\t" if el.tag == f"{W}tab" else (el.text or ""))
            paras.append("".join(parts))
        s = xml.decode("utf-8")
        return cls(
            # NBSP (from ~) compared as a plain space; test NBSP explicitly if needed
            text="\n".join(paras).replace("\xa0", " "),
            math=len(re.findall(r"<m:oMath>", s)),
            images=len(re.findall(r"<pic:pic\b", s)),
            styles=set(re.findall(r'<w:pStyle w:val="([^"]+)"', s)),
            fields=re.findall(r'<w:fldSimple w:instr="([^"]*)"', s),
        )
