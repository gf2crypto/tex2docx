"""Build input.docx: a chapter typed in Word by hand, without any template.

Default styles only: a bold "Теорема 1." paragraph, an italic "Доказательство." one ending
with the end sign, a centered formula paragraph, a nested list, a table with merged cells,
a picture with Word's own caption (SEQ field, _Ref bookmark) and a cross-reference to it
(REF field), a formula with bold letters (the main document's \\matr macro, config.yaml).
Run: python make.py  (python-docx; fields, bookmarks and OMML are raw XML).
"""

from __future__ import annotations

from pathlib import Path

from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm
from lxml import etree

HERE = Path(__file__).parent
OMML = HERE.parents[1] / "fixtures" / "omml"


def omml(name: str):
    return etree.fromstring((OMML / f"{name}.xml").read_bytes())


def run_with_text(text: str):
    r = OxmlElement("w:r")
    t = OxmlElement("w:t")
    t.set(qn("xml:space"), "preserve")
    t.text = text
    r.append(t)
    return r


def field(instr: str, result: str):
    """A simple field as Word writes it: fldSimple with the cached result inside."""
    f = OxmlElement("w:fldSimple")
    f.set(qn("w:instr"), instr)
    f.append(run_with_text(result))
    return f


def bookmark(p, bid: int, name: str, *children):
    start = OxmlElement("w:bookmarkStart")
    start.set(qn("w:id"), str(bid))
    start.set(qn("w:name"), name)
    p._p.append(start)
    for c in children:
        p._p.append(c)
    end = OxmlElement("w:bookmarkEnd")
    end.set(qn("w:id"), str(bid))
    p._p.append(end)


def main() -> None:
    doc = Document()
    doc.add_heading("Глава без шаблона", level=1)
    p = doc.add_paragraph()
    p.add_run("Теорема 1.").bold = True
    p.add_run(" Для любого ")
    p._p.append(omml("inline-x2"))
    p.add_run(" утверждение верно.")
    p = doc.add_paragraph()
    p.add_run("Доказательство.").italic = True
    p.add_run(" Очевидно. ◻")
    p = doc.add_paragraph("Пусть ")
    p._p.append(omml("bold-G"))
    p.add_run(".")
    eq = doc.add_paragraph()
    eq.alignment = 1
    eq._p.append(omml("display-sum"))
    # a nested list as Word numbers it: one numId, ilvl 0 / 1 on the paragraphs (python-docx's
    # template defines only level 0 of the bullet list; Word defines all nine)
    num_id = doc.styles["List Bullet"].element.pPr.numPr.numId.val
    numbering = doc.part.numbering_part.element
    abstract_id = numbering.num_having_numId(num_id).abstractNumId.val
    for abstract in numbering.findall(qn("w:abstractNum")):
        if abstract.get(qn("w:abstractNumId")) == str(abstract_id):
            abstract.append(etree.fromstring(
                '<w:lvl xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" w:ilvl="1">'
                '<w:start w:val="1"/><w:numFmt w:val="bullet"/><w:lvlText w:val="o"/><w:lvlJc w:val="left"/>'
                '<w:pPr><w:ind w:left="1440" w:hanging="360"/></w:pPr></w:lvl>'))
    for text, level in (("Внешний пункт", 0), ("Вложенный пункт", 1), ("Снова внешний", 0)):
        p = doc.add_paragraph(text, style="List Bullet")
        num_pr = p._p.get_or_add_pPr().get_or_add_numPr()
        num_pr.get_or_add_ilvl().val = level
        num_pr.get_or_add_numId().val = num_id
    t = doc.add_table(rows=3, cols=3)
    t.style = "Table Grid"
    t.cell(0, 0).merge(t.cell(0, 1)).text = "Объединено по горизонтали"
    t.cell(0, 2).text = "c"
    t.cell(1, 0).merge(t.cell(2, 0)).text = "Вертикально"
    t.cell(1, 1).text, t.cell(1, 2).text = "1", "2"
    t.cell(2, 1).text, t.cell(2, 2).text = "3", "4"
    doc.add_picture(str(HERE.parents[1] / "fixtures" / "pic.png"), width=Cm(3))
    cap = doc.add_paragraph(style="Caption")
    cap.add_run("Рисунок ")
    bookmark(cap, 1, "_Ref100", field(" SEQ Рисунок \\* ARABIC ", "1"))
    cap.add_run(" – Пример картинки")
    p = doc.add_paragraph("Как показано на ")
    p._p.append(field(" REF _Ref100 \\h ", "Рисунок 1"))
    p.add_run(", все хорошо.")
    doc.save(str(HERE / "input.docx"))


if __name__ == "__main__":
    main()
