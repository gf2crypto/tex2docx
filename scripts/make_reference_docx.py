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
from docx.shared import Pt

OUT = Path(__file__).resolve().parents[1] / "src" / "tex2docx" / "data" / "reference.docx"

BODY_FONT = "Times New Roman"
BODY_SIZE = Pt(12)

# style name -> (italic body, space before pt). Italic of the theorem *body*
# comes from pandoc's Emph runs; the style only controls spacing and keeping.
THEOREM_STYLES = {
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
    doc.save(str(OUT))
    print(f"written {OUT}")


if __name__ == "__main__":
    main()
