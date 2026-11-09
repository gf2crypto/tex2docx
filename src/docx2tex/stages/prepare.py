"""Working copy of the docx for pandoc: facts that pandoc's docx reader would lose
are written into the text as private-use markers (removed again by filters/structures.lua).

Status: implemented (M1). The source docx is never modified (CLAUDE.md invariant).

  * every bookmark (except Word's own "_..." ones) gets a run U+E000 name U+E001 right
    after its start; a bookmark that starts between paragraphs (pandoc ignores those:
    tex2docx/pandoc put them around theorem Divs and sections) is marked at the start
    of the next paragraph and U+E003 name U+E001 at the end of its last paragraph;
  * REF fields (simple and complex) become hyperlinks to the bookmark, with the field
    result as text: pandoc 3.1 does not read REF fields, 3.12 does, so neither is relied on;
  * other fields (SEQ numbers, live mode) are flattened to their result runs;
  * a tab becomes U+E002 (pandoc turns tabs into spaces; the algorithm box uses tabs
    for the nesting level);
  * a paragraph numbered by a list level whose bullet is blank (pandoc writes those for
    the second and further paragraphs of a list item, e.g. a theorem inside \\item) starts
    with U+E004: pandoc reads it as a list of its own; the filter puts it back into the item;
  * a formula delimiter U+2225 (texmath writes it for \\lVert) becomes U+2016: texmath
    reads only the latter as a delimiter, the former as \\left. \\parallel.
"""

from __future__ import annotations

import re
import shutil
import zipfile
from pathlib import Path

from lxml import etree

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
M = "http://schemas.openxmlformats.org/officeDocument/2006/math"
MARK_START, MARK_END, MARK_TAB, MARK_CLOSE = "\ue000", "\ue001", "\ue002", "\ue003"
MARK_CONT = "\ue004"
# parts with paragraphs pandoc reads: the body and the notes (formulas, labels in footnotes)
TEXT_PARTS = ("word/document.xml", "word/footnotes.xml", "word/endnotes.xml")


def _q(tag: str) -> str:
    return f"{{{W}}}{tag}"


def _marker_run(name: str, start: str = MARK_START) -> etree._Element:
    r = etree.Element(_q("r"))
    t = etree.SubElement(r, _q("t"))
    t.text = start + name + MARK_END
    t.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
    return r


def _insert_at_start(p: etree._Element, el: etree._Element) -> None:
    ppr = p.find(_q("pPr"))
    if ppr is not None:
        ppr.addnext(el)
    else:
        p.insert(0, el)


def _mark_bookmarks(body: etree._Element) -> int:
    n = 0
    spanning: dict[str, str] = {}  # id -> name of bookmarks that start between paragraphs
    for bm in list(body.iter(_q("bookmarkStart"))):
        name = bm.get(_q("name"), "")
        if not name or (name.startswith("_") and not _KEPT.fullmatch(name)):
            continue  # Word's own _Toc/_GoBack/_Hlk; kept: _Ref (cross-references), pandoc hashes
        parent = bm.getparent()
        if parent.tag == _q("p"):
            bm.addnext(_marker_run(name))
            n += 1
            continue
        nxt = bm.getnext()
        while nxt is not None and nxt.tag != _q("p"):
            nxt = nxt.getnext()
        if nxt is None:
            continue
        _insert_at_start(nxt, _marker_run(name))
        spanning[bm.get(_q("id"), "")] = name
        n += 1
    # where such a bookmark ends (after its last paragraph): U+E003 name U+E001 there, so that
    # a theorem keeps the formulas that belong to it
    for be in list(body.iter(_q("bookmarkEnd"))):
        name = spanning.get(be.get(_q("id"), ""))
        if name is None or be.getparent().tag != _q("body"):
            continue
        prev = be.getprevious()
        while prev is not None and prev.tag != _q("p"):
            prev = prev.getprevious()
        if prev is not None:
            prev.append(_marker_run(name, MARK_CLOSE))
    return n


_REF = re.compile(r"^\s*REF\s+(\S+)")
_KEPT = re.compile(r"_[0-9a-f]{39}|_Ref\d+")  # pandoc 3.12 hashes Div ids to _<39 hex>


def _hyperlink(anchor: str, runs: list[etree._Element]) -> etree._Element:
    h = etree.Element(_q("hyperlink"))
    h.set(_q("anchor"), anchor)
    for r in runs:
        h.append(r)
    return h


def _simple_fields(body: etree._Element) -> None:
    for fld in list(body.iter(_q("fldSimple"))):
        instr = fld.get(_q("instr"), "")
        runs = list(fld)
        parent = fld.getparent()
        idx = parent.index(fld)
        parent.remove(fld)
        m = _REF.match(instr)
        if m:
            parent.insert(idx, _hyperlink(m.group(1), runs))
        elif instr.strip().upper().startswith("SEQ"):
            for i, r in enumerate(runs):
                parent.insert(idx + i, r)
        else:
            parent.insert(idx, fld)
            for r in runs:
                fld.append(r)


def _complex_fields(p: etree._Element) -> None:
    """Runs between fldChar begin and end: REF -> hyperlink, SEQ -> result runs."""
    children = list(p)
    i = 0
    while i < len(children):
        r = children[i]
        fc = r.find(_q("fldChar")) if r.tag == _q("r") else None
        if fc is None or fc.get(_q("fldCharType")) != "begin":
            i += 1
            continue
        instr, result, state, j, depth = "", [], "instr", i + 1, 1
        while j < len(children):
            rj = children[j]
            fcj = rj.find(_q("fldChar")) if rj.tag == _q("r") else None
            kind = fcj.get(_q("fldCharType")) if fcj is not None else None
            if kind == "begin":
                depth += 1
            elif kind == "end":
                depth -= 1
                if depth == 0:
                    break
            elif kind == "separate" and depth == 1:
                state = "result"
            elif state == "instr" and depth == 1:
                instr += "".join(t.text or "" for t in rj.iter(_q("instrText")))
            elif state == "result":
                result.append(rj)
            j += 1
        if j >= len(children):
            break
        m = _REF.match(instr)
        if m or instr.strip().upper().startswith("SEQ"):
            for k in range(i, j + 1):
                p.remove(children[k])
            if m:
                p.insert(i, _hyperlink(m.group(1), result))
            else:
                for k, rr in enumerate(result):
                    p.insert(i + k, rr)
            children = list(p)
            i += 1
        else:
            i = j + 1


def _tabs(body: etree._Element) -> None:
    for tab in list(body.iter(_q("tab"))):
        r = tab.getparent()
        if r is None or r.tag != _q("r"):
            continue
        t = etree.Element(_q("t"))
        t.text = MARK_TAB
        t.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
        r.replace(tab, t)


def continuation_levels(numbering: bytes | None) -> set[tuple[str, str]]:
    """(numId, ilvl) of list levels with a bullet that prints nothing: item continuations."""
    if not numbering:
        return set()
    root = etree.fromstring(numbering)
    blank: dict[str, set[str]] = {}
    for a in root.iter(_q("abstractNum")):
        for lvl in a.iter(_q("lvl")):
            fmt, text = lvl.find(_q("numFmt")), lvl.find(_q("lvlText"))
            if (fmt is not None and fmt.get(_q("val")) == "bullet" and text is not None
                    and not (text.get(_q("val")) or "").strip()):
                blank.setdefault(a.get(_q("abstractNumId")), set()).add(lvl.get(_q("ilvl")))
    out = set()
    for num in root.iter(_q("num")):
        abstract = num.find(_q("abstractNumId"))
        if abstract is not None:
            for ilvl in blank.get(abstract.get(_q("val")), ()):
                out.add((num.get(_q("numId")), ilvl))
    return out


def _continuations(body: etree._Element, levels: set[tuple[str, str]]) -> None:
    for p in body.iter(_q("p")):
        num_pr = p.find(f"{_q('pPr')}/{_q('numPr')}")
        if num_pr is None:
            continue
        num_id, ilvl = num_pr.find(_q("numId")), num_pr.find(_q("ilvl"))
        key = (num_id.get(_q("val")) if num_id is not None else None,
               ilvl.get(_q("val")) if ilvl is not None else "0")
        if key in levels:
            r = etree.Element(_q("r"))
            etree.SubElement(r, _q("t")).text = MARK_CONT
            _insert_at_start(p, r)


def _math_delimiters(body: etree._Element) -> None:
    for tag in ("begChr", "sepChr", "endChr"):
        for el in body.iter(f"{{{M}}}{tag}"):
            if el.get(f"{{{M}}}val") == "\u2225":
                el.set(f"{{{M}}}val", "\u2016")


def prepare_xml(xml: bytes, continuations: set[tuple[str, str]] | None = None) -> tuple[bytes, int]:
    root = etree.fromstring(xml)
    body = root.find(_q("body"))
    if body is None:  # footnotes.xml / endnotes.xml: the notes are the body
        if root.tag not in (_q("footnotes"), _q("endnotes")):
            return xml, 0
        body = root
    n = _mark_bookmarks(body)
    _simple_fields(body)
    for p in body.iter(_q("p")):
        _complex_fields(p)
    _tabs(body)
    _math_delimiters(body)
    if continuations:
        _continuations(body, continuations)
    return etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True), n


def prepare_docx(source: Path, dest: Path) -> int:
    """Copy source to dest with the body and the notes rewritten; returns the number of
    bookmarks marked."""
    with zipfile.ZipFile(source) as zin, zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as zout:
        n = 0
        names = zin.namelist()
        levels = continuation_levels(
            zin.read("word/numbering.xml") if "word/numbering.xml" in names else None)
        for item in zin.infolist():
            data = zin.read(item.filename)
            if item.filename in TEXT_PARTS:
                data, k = prepare_xml(data, levels)
                n += k
            zout.writestr(item, data)
    return n
