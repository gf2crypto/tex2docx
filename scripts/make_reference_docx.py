"""Build src/tex2docx/data/reference.docx from pandoc's default reference.

Run after changing styles here; the result is committed.
    python scripts/make_reference_docx.py

Paragraph styles that filters assign via custom-style must exist here,
otherwise pandoc creates them with Normal formatting.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from docx import Document
from docx.enum.style import WD_STYLE_TYPE
from docx.enum.text import WD_TAB_ALIGNMENT
from docx.shared import Cm, Pt

OUT = Path(__file__).resolve().parents[1] / "src" / "tex2docx" / "data" / "reference.docx"

BODY_FONT = "Times New Roman"
BODY_SIZE = Pt(12)

# Page: A4 with the usual Russian-article margins. pandoc copies the section
# properties of the reference document, and the tab stops of the Equation
# style below are computed from the resulting text width.
PAGE_W, PAGE_H = Cm(21.0), Cm(29.7)
MARGIN = Cm(2.5)

# style name -> (italic body, space before pt). Italic of the theorem *body*
# comes from pandoc's Emph runs; the style only controls spacing and keeping.
THEOREM_STYLES = {  # see also the Equation style below
    "Theorem": 6,
    "Definition": 6,
    "Remark": 6,
    "Proof": 3,
}


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["pandoc", "-o", str(OUT), "--print-default-data-file", "reference.docx"],
        check=True,
    )

    doc = Document(str(OUT))
    sec = doc.sections[0]
    sec.page_width, sec.page_height = PAGE_W, PAGE_H
    sec.left_margin = sec.right_margin = sec.top_margin = sec.bottom_margin = MARGIN
    text_width = PAGE_W - 2 * MARGIN
    styles = doc.styles
    for name in ("Normal", "Body Text", "First Paragraph", "Compact"):
        try:
            st = styles[name]
        except KeyError:
            continue
        st.font.name = BODY_FONT
        st.font.size = BODY_SIZE

    base = styles["Body Text"]
    for name, before in THEOREM_STYLES.items():
        try:
            st = styles[name]
        except KeyError:
            st = styles.add_style(name, WD_STYLE_TYPE.PARAGRAPH)
        st.base_style = base
        st.paragraph_format.space_before = Pt(before)
        st.paragraph_format.space_after = Pt(6)
        st.paragraph_format.keep_together = True

    # Display equation: "<tab> formula <tab> (number)" - the formula sits on the
    # centre tab, the number on the right tab (ADR 0004).
    try:
        eq = styles["Equation"]
    except KeyError:
        eq = styles.add_style("Equation", WD_STYLE_TYPE.PARAGRAPH)
    eq.base_style = base
    pf = eq.paragraph_format
    pf.first_line_indent = Cm(0)
    pf.left_indent = Cm(0)
    pf.space_before = Pt(6)
    pf.space_after = Pt(6)
    pf.keep_together = True
    pf.tab_stops.clear_all()
    pf.tab_stops.add_tab_stop(text_width // 2, WD_TAB_ALIGNMENT.CENTER)
    pf.tab_stops.add_tab_stop(text_width, WD_TAB_ALIGNMENT.RIGHT)
    doc.save(str(OUT))
    print(f"written {OUT}")


if __name__ == "__main__":
    main()
