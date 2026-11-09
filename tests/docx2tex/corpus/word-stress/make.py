"""Build input.docx: what broke docx2tex in the stress run of 2026-11-09.

- two Author paragraphs (pandoc gives meta.author as a plain List: the filter crashed);
- brackets that are not citations ("[см. выше]", "[2-3]" past the list end) next to real
  ones: the text before them was dropped; a range "[1–2]" is a citation;
- a picture inside a text paragraph (pandoc 3.5+ wraps it in \\pandocbounded);
- underlined and struck-out runs (\\ul, \\st need soul), \\mathfrak and pmatrix without
  \\mathbb (amssymb, amsmath);
- Unicode pdflatex cannot take: U+2284 in a formula, U+2212 in text;
- a line break inside a table cell (\\\\ there ends the table row);
- tracked changes (pandoc accepts them silently);
- upright operators in a formula (\\operatorname{rank}, \\bmod, \\mathrm{d}: texmath made them
  italic letters);
- numbers typed by hand: "formula <tab> (2.1)", bold "Лемма 2." with a reference
  "леммы 2";
- a hyperlink to a heading that Word bookmarked (_Toc), its text a word, not a number.
Run: python make.py  (python-docx; the OMML XML is pasted as raw elements).
"""

from __future__ import annotations

from pathlib import Path

from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm
from lxml import etree

HERE = Path(__file__).parent
FIXTURES = HERE.parents[1] / "fixtures"


def omml(name: str):
    return etree.fromstring((FIXTURES / "omml" / f"{name}.xml").read_bytes())


def tracked(p, kind: str, text: str, rid: int) -> None:
    el = OxmlElement(f"w:{kind}")
    el.set(qn("w:id"), str(rid))
    el.set(qn("w:author"), "Coauthor")
    el.set(qn("w:date"), "2026-11-01T10:00:00Z")
    r = OxmlElement("w:r")
    t = OxmlElement("w:delText" if kind == "del" else "w:t")
    t.set(qn("xml:space"), "preserve")
    t.text = text
    r.append(t)
    el.append(r)
    p._p.append(el)


def main() -> None:
    doc = Document()
    doc.add_paragraph("Глава для стресс-теста", style="Title")
    doc.add_paragraph("А. Первый", style="Normal").style = doc.styles.add_style("Author", 1)
    doc.add_paragraph("Б. Второй", style="Author")
    h = doc.add_heading("", level=1)
    start = OxmlElement("w:bookmarkStart")
    start.set(qn("w:id"), "50")
    start.set(qn("w:name"), "_Toc100")
    h._p.append(start)
    h.add_run("Раздел")
    end = OxmlElement("w:bookmarkEnd")
    end.set(qn("w:id"), "50")
    h._p.append(end)
    p = doc.add_paragraph("Текст ")
    p.add_run("подчеркнутый").underline = True
    p.add_run(" и ")
    p.add_run("зачеркнутый").font.strike = True
    p.add_run(", значок ")
    p.add_run().add_picture(str(FIXTURES / "pic.png"), width=Cm(0.5))
    p.add_run(" в строке.")
    p = doc.add_paragraph("Формулы ")
    p._p.append(omml("not-subset"))
    p.add_run(" и ")
    p._p.append(omml("pmatrix"))
    p.add_run(", температура −5 градусов.")
    p = doc.add_paragraph("Ссылки [1], [1, 2], [1–2], как сказано [см. выше], и [2-3] в конце.")
    p = doc.add_paragraph("Правка: было ")
    tracked(p, "del", "старое", 901)
    tracked(p, "ins", "новое", 902)
    p.add_run(" слово.")
    p = doc.add_paragraph("Операторы ")
    p._p.append(omml("operators"))
    p.add_run(".")
    p = doc.add_paragraph()
    p._p.append(omml("inline-x2"))
    p.add_run("\t(2.1)")
    p = doc.add_paragraph()
    p.add_run("Лемма 2.").bold = True
    p.add_run(" Утверждение леммы.")
    p = doc.add_paragraph("Из (2.1) и леммы 2 следует все, см. ")
    link = OxmlElement("w:hyperlink")
    link.set(qn("w:anchor"), "_Toc100")
    r = OxmlElement("w:r")
    t = OxmlElement("w:t")
    t.text = "раздел"
    r.append(t)
    link.append(r)
    p._p.append(link)
    p.add_run(".")
    t = doc.add_table(rows=2, cols=2)
    t.style = "Table Grid"
    t.cell(0, 0).text, t.cell(0, 1).text = "Ключ", "Значение"
    t.cell(1, 0).text, t.cell(1, 1).text = "Две\nстроки", "x"
    doc.add_heading("Список литературы", level=1)
    doc.add_paragraph("Иванов И. И. Книга. М.: Наука, 2020.", style="List Number")
    doc.add_paragraph("Petrov P. Paper // J. Math. 2021. V. 1. P. 1-10.", style="List Number")
    doc.save(str(HERE / "input.docx"))


if __name__ == "__main__":
    main()
