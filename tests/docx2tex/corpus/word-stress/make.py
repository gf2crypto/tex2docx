"""Build input.docx: what broke docx2tex in the stress run of 2026-11-09.

- two Author paragraphs (pandoc gives meta.author as a plain List: the filter crashed);
- brackets that are not citations ("[см. выше]", "[2-3]" past the list end) next to real
  ones: the text before them was dropped; a range "[1–2]" is a citation;
- a picture inside a text paragraph (pandoc 3.5+ wraps it in \\pandocbounded);
- underlined and struck-out runs (\\ul, \\st need soul), \\mathfrak and pmatrix without
  \\mathbb (amssymb, amsmath);
- Unicode pdflatex cannot take: U+2284 in a formula, U+2212 in text;
- a line break inside a table cell (\\\\ there ends the table row).
Run: python make.py  (python-docx; the OMML XML is pasted as raw elements).
"""

from __future__ import annotations

from pathlib import Path

from docx import Document
from docx.shared import Cm
from lxml import etree

HERE = Path(__file__).parent
FIXTURES = HERE.parents[1] / "fixtures"


def omml(name: str):
    return etree.fromstring((FIXTURES / "omml" / f"{name}.xml").read_bytes())


def main() -> None:
    doc = Document()
    doc.add_paragraph("Глава для стресс-теста", style="Title")
    doc.add_paragraph("А. Первый", style="Normal").style = doc.styles.add_style("Author", 1)
    doc.add_paragraph("Б. Второй", style="Author")
    doc.add_heading("Раздел", level=1)
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
