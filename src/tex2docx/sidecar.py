r"""The companion file <name>.t2d.xml shared by tex2docx and docx2tex (ADR 0007, 0008).

tex2docx writes it next to the .docx: what the document needs to go back to LaTeX
exactly (labels behind bookmarks, theorem declarations, language, caption names, the
profile and macros used). docx2tex reads it when present, keeps it next to the .tex
and adds its own facts. The author may edit it to pin conversion settings for the
next round. Plain XML, UTF-8, no document text.

<t2d version="1" source="main.tex" language="russian" profile="standard">
  <names figure="Рис." table="Таблица" sep="." proof="Доказательство"/>
  <theorems>
    <theorem env="theorem" title="Теорема" style="plain" numbered="true" within="section"/>
  </theorems>
  <labels>
    <label bookmark="t2d_thm_main" name="thm:main" kind="theorem"/>
  </labels>
  <cites>
    <cite key="knuth" number="1"/>
  </cites>
  <macros>
    <macro name="\matr" body="\mathbf"/>
  </macros>
</t2d>
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from xml.etree import ElementTree as ET

VERSION = "1"


@dataclass
class Sidecar:
    source: str = ""
    language: str = ""
    profile: str = ""
    names: dict[str, str] = field(default_factory=dict)
    theorems: dict[str, dict[str, str]] = field(default_factory=dict)  # env -> attributes
    labels: dict[str, str] = field(default_factory=dict)  # bookmark -> label
    label_kinds: dict[str, str] = field(default_factory=dict)  # label -> kind
    macros: dict[str, str] = field(default_factory=dict)  # \name -> body
    cites: dict[str, str] = field(default_factory=dict)  # number as printed -> \cite key

    @staticmethod
    def path_for(document: Path) -> Path:
        """main.docx -> main.t2d.xml (same stem, beside the document)."""
        return document.with_suffix(".t2d.xml")

    @classmethod
    def load(cls, path: Path) -> Sidecar | None:
        if not path.is_file():
            return None
        root = ET.parse(path).getroot()
        if root.tag != "t2d":
            return None
        sc = cls(source=root.get("source", ""), language=root.get("language", ""),
                 profile=root.get("profile", ""))
        names = root.find("names")
        if names is not None:
            sc.names = dict(names.attrib)
        for t in root.iterfind("theorems/theorem"):
            env = t.get("env")
            if env:
                sc.theorems[env] = {k: v for k, v in t.attrib.items() if k != "env"}
        for lb in root.iterfind("labels/label"):
            bm, name = lb.get("bookmark"), lb.get("name")
            if name:
                if bm:
                    sc.labels[bm] = name
                if lb.get("kind"):
                    sc.label_kinds[name] = lb.get("kind", "")
        for m in root.iterfind("macros/macro"):
            if m.get("name"):
                sc.macros[m.get("name", "")] = m.get("body", "")
        for c in root.iterfind("cites/cite"):
            if c.get("key") and c.get("number"):
                sc.cites[c.get("number", "")] = c.get("key", "")
        return sc

    def save(self, path: Path) -> None:
        root = ET.Element("t2d", {"version": VERSION})
        for k in ("source", "language", "profile"):
            if getattr(self, k):
                root.set(k, getattr(self, k))
        if self.names:
            ET.SubElement(root, "names", {k: str(v) for k, v in self.names.items()})
        if self.theorems:
            ts = ET.SubElement(root, "theorems")
            for env, attrs in sorted(self.theorems.items()):
                ET.SubElement(ts, "theorem", {"env": env, **{k: str(v) for k, v in attrs.items()}})
        if self.labels or self.label_kinds:
            ls = ET.SubElement(root, "labels")
            by_name = {v: k for k, v in self.labels.items()}
            for name in sorted(set(self.labels.values()) | set(self.label_kinds)):
                attrs = {"name": name}
                if name in by_name:
                    attrs["bookmark"] = by_name[name]
                if name in self.label_kinds:
                    attrs["kind"] = self.label_kinds[name]
                ET.SubElement(ls, "label", attrs)
        if self.cites:
            cs = ET.SubElement(root, "cites")
            for num, key in sorted(self.cites.items(), key=lambda kv: (len(kv[0]), kv[0])):
                ET.SubElement(cs, "cite", {"key": key, "number": num})
        if self.macros:
            ms = ET.SubElement(root, "macros")
            for name, body in sorted(self.macros.items()):
                ET.SubElement(ms, "macro", {"name": name, "body": body})
        tree = ET.ElementTree(root)
        ET.indent(tree, space="  ")
        tree.write(path, encoding="utf-8", xml_declaration=True)
