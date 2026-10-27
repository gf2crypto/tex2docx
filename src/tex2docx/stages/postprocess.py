"""Stage 9: fix the .docx itself (lxml over word/document.xml).

Status: implemented (M3, first part). Done:
- proof end mark (pandoc's "\\u00a0\\u25fb") pushed to the right margin by a tab;
- keep-with-next: a paragraph before a display equation, a figure before its
  caption, a table caption before its table;
- Russian typography: non-breaking space after one- and two-letter
  prepositions/conjunctions and before an em dash (prose runs only, math untouched);
- internal cross-references lose the blue Hyperlink character style.
TODO (M3): equation and theorem numbers as SEQ fields + bookmarks, references
as REF fields (config switch).
"""

from __future__ import annotations

import re
import shutil
import zipfile
from pathlib import Path

from lxml import etree

from ..context import Context
from . import StageError

STAGE = "postprocess"
W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
NS = {"w": W}
QED = "◻"  # pandoc's end-of-proof mark
NBSP = " "
DEFAULT_TEXT_WIDTH = 9071  # twips; A4 with 2.5 cm margins, as in reference.docx

# Words that must not end a line (Russian typography): short prepositions and conjunctions.
_SHORT_WORDS = (
    "а|и|о|у|в|к|с|я|не|ни|но|на|по|из|от|до|за|об|во|со|ко|от|уж|же|ли|бы|то|их|ее|ей|им|"
    "под|над|при|про|без|для|или|как|что|где|так|уже|все"
)
# Preceded by start/space/open bracket; followed by a space and a word character.
_SHORT = re.compile(rf"(?<![\w-])({_SHORT_WORDS}) (?=[\w(«])", re.IGNORECASE)
_DASH = re.compile(r"(?<=\S) (?=—)")


def w(tag: str) -> str:
    return f"{{{W}}}{tag}"


def nbsp_text(text: str) -> str:
    """Russian typography: glue short words to the next word and the em dash to the previous."""
    text = _SHORT.sub(lambda m: m.group(1) + NBSP, text)
    return _DASH.sub(NBSP, text)


def _style(p: etree._Element) -> str:
    st = p.find("w:pPr/w:pStyle", NS)
    return st.get(w("val")) if st is not None else ""


def _ppr(p: etree._Element) -> etree._Element:
    ppr = p.find("w:pPr", NS)
    if ppr is None:
        ppr = etree.Element(w("pPr"))
        p.insert(0, ppr)
    return ppr


def _set_keep_next(p: etree._Element) -> None:
    ppr = _ppr(p)
    if ppr.find("w:keepNext", NS) is None:
        kn = etree.Element(w("keepNext"))
        # schema order: pStyle, keepNext, keepLines, ...
        st = ppr.find("w:pStyle", NS)
        ppr.insert(0 if st is None else list(ppr).index(st) + 1, kn)


def _text_width(root: etree._Element) -> int:
    sect = root.find("w:body/w:sectPr", NS)
    if sect is None:
        return DEFAULT_TEXT_WIDTH
    sz, mar = sect.find("w:pgSz", NS), sect.find("w:pgMar", NS)
    if sz is None or mar is None or sz.get(w("w")) is None:
        return DEFAULT_TEXT_WIDTH
    return int(sz.get(w("w"))) - int(mar.get(w("left"), 0)) - int(mar.get(w("right"), 0))


def _add_right_tab(p: etree._Element, pos: int) -> None:
    ppr = _ppr(p)
    tabs = ppr.find("w:tabs", NS)
    if tabs is not None and any(t.get(w("val")) == "right" for t in tabs):
        return
    if tabs is None:
        tabs = etree.Element(w("tabs"))
        # after keepNext/keepLines/pageBreakBefore..., before spacing/ind/jc: put it
        # right after the last of (pStyle, keepNext, keepLines, widowControl, numPr, pBdr, shd)
        before = {"pStyle", "keepNext", "keepLines", "pageBreakBefore", "framePr",
                  "widowControl", "numPr", "suppressLineNumbers", "pBdr", "shd"}
        idx = 0
        for i, ch in enumerate(ppr):
            if etree.QName(ch).localname in before:
                idx = i + 1
        ppr.insert(idx, tabs)
    t = etree.SubElement(tabs, w("tab"))
    t.set(w("val"), "right")
    t.set(w("pos"), str(pos))


def _runs_text(p: etree._Element) -> list[etree._Element]:
    """w:t elements of prose runs (not inside math, not inside fields)."""
    return [t for t in p.iter(w("t")) if t.getparent().tag == w("r")]


def qed_to_right(p: etree._Element, width: int) -> bool:
    """'... text. ◻' -> '... text.<tab>◻' with a right tab stop at the margin."""
    ts = _runs_text(p)
    if not ts:
        return False
    last = ts[-1]
    txt = last.text or ""
    if not txt.endswith(QED):
        return False
    last.text = txt[:-1].rstrip(" " + NBSP)
    r = last.getparent()
    rpr = r.find("w:rPr", NS)
    tab_run = etree.Element(w("r"))
    if rpr is not None:
        tab_run.append(etree.fromstring(etree.tostring(rpr)))
    etree.SubElement(tab_run, w("tab"))
    qed_run = etree.Element(w("r"))
    if rpr is not None:
        qed_run.append(etree.fromstring(etree.tostring(rpr)))
    etree.SubElement(qed_run, w("t")).text = QED
    parent = r.getparent()
    i = list(parent).index(r)
    parent.insert(i + 1, tab_run)
    parent.insert(i + 2, qed_run)
    _add_right_tab(p, width)
    return True


def process_document(root: etree._Element) -> dict[str, int]:
    body = root.find("w:body", NS)
    width = _text_width(root)
    counts = {"qed": 0, "keep_next": 0, "nbsp": 0, "refs": 0}
    paras = list(body.iter(w("p")))

    # keep-with-next
    for prev, cur in zip(paras, paras[1:]):
        cur_style, prev_style = _style(cur), _style(prev)
        if cur_style == "Equation" and prev_style != "Equation" and _runs_text(prev):
            _set_keep_next(prev)
            counts["keep_next"] += 1
        elif cur_style == "ImageCaption" or prev_style == "TableCaption":
            _set_keep_next(prev)
            counts["keep_next"] += 1

    # proof end mark
    for p in paras:
        if _style(p) in ("Proof", "Equation") and qed_to_right(p, width):
            counts["qed"] += 1

    # typography
    for t in root.iter(w("t")):
        if t.getparent().tag != w("r") or not t.text:
            continue
        new = nbsp_text(t.text)
        if new != t.text:
            counts["nbsp"] += new.count(NBSP) - t.text.count(NBSP)
            t.text = new

    # internal references: plain text, still clickable
    for h in root.iter(w("hyperlink")):
        if h.get(w("anchor")) is None:
            continue
        for rs in h.iter(w("rStyle")):
            if rs.get(w("val")) == "Hyperlink":
                rs.getparent().remove(rs)
                counts["refs"] += 1
    return counts


def process_docx(src: Path, dst: Path) -> dict[str, int]:
    with zipfile.ZipFile(src) as zin:
        root = etree.fromstring(zin.read("word/document.xml"))
        counts = process_document(root)
        with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as zout:
            for item in zin.infolist():
                data = zin.read(item.filename)
                if item.filename == "word/document.xml":
                    data = etree.tostring(root, xml_declaration=True, encoding="UTF-8",
                                          standalone=True)
                zout.writestr(item, data)
    return counts


def run(ctx: Context) -> None:
    if ctx.docx is None:
        raise StageError("postprocess.no-input")
    ctx.output.parent.mkdir(parents=True, exist_ok=True)
    try:
        counts = process_docx(ctx.docx, ctx.output)
    except Exception as e:  # never lose the document: deliver pandoc's version
        shutil.copyfile(ctx.docx, ctx.output)
        ctx.report.warn(STAGE, "postprocess.skipped", type(e).__name__)
        return
    for k, v in counts.items():
        if v:
            ctx.report.info(STAGE, f"postprocess.{k}", str(v))
