r"""The companion file <name>.t2d.xml shared by tex2docx and docx2tex (ADR 0007, 0008).

tex2docx writes it next to the .docx: what the document needs to go back to LaTeX
exactly (labels behind bookmarks, theorem declarations, language, caption names, the
profile and macros used), and the same XML inside the docx as a custom XML part
(embed / read_embedded), so that a renamed or mailed docx still carries it. docx2tex
reads the file when present, else the copy inside the docx, keeps it next to the .tex
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

import re
import zipfile
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
        return cls.from_bytes(path.read_bytes())

    @classmethod
    def from_bytes(cls, data: bytes) -> Sidecar | None:
        try:
            root = ET.fromstring(data)
        except ET.ParseError:
            return None
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
        path.write_bytes(self.to_bytes())

    def to_bytes(self) -> bytes:
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
        ET.indent(root, space="  ")
        return b'<?xml version="1.0" encoding="utf-8"?>\n' + ET.tostring(root, encoding="utf-8")


# --- the copy inside the docx: a custom XML part (customXml/itemN.xml) -----------------
# Word keeps custom XML parts as they are; a custom document property (docProps/custom.xml)
# would be cut to 255 characters on the next save in Word.

_CT_NS = "http://schemas.openxmlformats.org/package/2006/content-types"
_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
_CUSTOMXML_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/customXml"
_PROPS_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/customXmlProps"
_PROPS_CT = "application/vnd.openxmlformats-officedocument.customXmlProperties+xml"
_ITEM_PROPS = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
               '<ds:datastoreItem ds:itemID="{3A1D0B7C-9E55-4C1B-9D0E-7D2D4E1F0A5B}" '
               'xmlns:ds="http://schemas.openxmlformats.org/officeDocument/2006/customXml">'
               '<ds:schemaRefs/></ds:datastoreItem>')
_T2D_META_PROP = re.compile(r'<property\b[^>]*name="t2d-meta"[^>]*>.*?</property>', re.S)


def _t2d_part(names: list[str], reader) -> str | None:
    for n in names:
        if re.fullmatch(r"customXml/item\d+\.xml", n):
            try:
                if ET.fromstring(reader(n)).tag == "t2d":
                    return n
            except ET.ParseError:
                continue
    return None


def embed(docx: Path, sc: Sidecar) -> str:
    """Write the sidecar into the docx as a custom XML part; returns the part name.
    Also drops the 't2d-meta' custom property that pandoc derives from our metadata."""
    with zipfile.ZipFile(docx) as z:
        names = z.namelist()
        parts = {n: z.read(n) for n in names}
    part = _t2d_part(names, parts.__getitem__)
    if part is None:
        used = {int(m.group(1)) for n in names if (m := re.fullmatch(r"customXml/item(\d+)\.xml", n))}
        k = max(used, default=0) + 1
        part = f"customXml/item{k}.xml"
    k = re.search(r"\d+", part).group(0)
    parts[part] = sc.to_bytes()
    parts[f"customXml/itemProps{k}.xml"] = _ITEM_PROPS.encode("utf-8")
    parts[f"customXml/_rels/item{k}.xml.rels"] = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        f'<Relationships xmlns="{_REL_NS}"><Relationship Id="rId1" Type="{_PROPS_REL}" '
        f'Target="itemProps{k}.xml"/></Relationships>').encode("utf-8")
    # content types
    ct = ET.fromstring(parts["[Content_Types].xml"])
    if not any(o.get("PartName") == f"/customXml/itemProps{k}.xml" for o in ct.iter(f"{{{_CT_NS}}}Override")):
        ET.SubElement(ct, f"{{{_CT_NS}}}Override",
                      {"PartName": f"/customXml/itemProps{k}.xml", "ContentType": _PROPS_CT})
    if not any(d.get("Extension") == "xml" for d in ct.iter(f"{{{_CT_NS}}}Default")):
        ct.insert(0, ET.Element(f"{{{_CT_NS}}}Default", {"Extension": "xml", "ContentType": "application/xml"}))
    ET.register_namespace("", _CT_NS)
    parts["[Content_Types].xml"] = ET.tostring(ct, encoding="utf-8", xml_declaration=True)
    # relationship from the main document
    rels_name = "word/_rels/document.xml.rels"
    rels = ET.fromstring(parts[rels_name])
    target = f"../customXml/item{k}.xml"
    if not any(r.get("Target") == target for r in rels.iter(f"{{{_REL_NS}}}Relationship")):
        ET.SubElement(rels, f"{{{_REL_NS}}}Relationship",
                      {"Id": f"rIdT2D{k}", "Type": _CUSTOMXML_REL, "Target": target})
    ET.register_namespace("", _REL_NS)
    parts[rels_name] = ET.tostring(rels, encoding="utf-8", xml_declaration=True)
    if "docProps/custom.xml" in parts:
        text = parts["docProps/custom.xml"].decode("utf-8")
        parts["docProps/custom.xml"] = _T2D_META_PROP.sub("", text).encode("utf-8")
    tmp = docx.with_suffix(docx.suffix + ".tmp")
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as out:
        for n in names:
            out.writestr(n, parts[n])
        for n in parts:
            if n not in names:
                out.writestr(n, parts[n])
    tmp.replace(docx)
    return part


def read_embedded(docx: Path) -> Sidecar | None:
    """The sidecar stored inside the docx by embed(), if any."""
    try:
        with zipfile.ZipFile(docx) as z:
            part = _t2d_part(z.namelist(), z.read)
            return Sidecar.from_bytes(z.read(part)) if part else None
    except (zipfile.BadZipFile, KeyError):
        return None
