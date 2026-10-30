"""Build the Word style templates from pandoc's default reference.docx.

    python scripts/make_reference_docx.py      # rebuilds every profile; commit the result

- src/tex2docx/data/reference.docx          default look (pandoc's styles, Times New Roman 12 pt)
- src/tex2docx/data/reference-standard.docx profile "standard": the house requirements in
  PROFILES["standard"] (config `profile: standard` / `tex2docx --profile standard`).
  New requirements go into that table; nothing else changes.

Paragraph styles that filters assign via custom-style must exist in every template,
otherwise pandoc creates them with Normal formatting.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from docx import Document
from docx.enum.style import WD_STYLE_TYPE
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_TAB_ALIGNMENT
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

DATA = Path(__file__).resolve().parents[1] / "src" / "tex2docx" / "data"

# A profile is a set of requirements for the whole document. Keys:
#   font, size          - every paragraph style (body, headings, captions, lists, ...)
#   space_before/after  - paragraph spacing, points (None = pandoc's defaults)
#   line_spacing        - 1.0 / 1.5 / 2.0 (None = single, pandoc's default)
#   heading_color       - RGB hex for Title, Subtitle, Heading 1-9 (None = pandoc's blue)
#   heading_sizes       - {style name: points} when headings differ from the body size
#   first_line_indent   - cm, for body paragraphs (None = pandoc's default)
#   justify             - True: body paragraphs justified (both margins)
PROFILES: dict[str, dict] = {
    "default": dict(font="Times New Roman", size=12, space_before=None, space_after=None,
                    line_spacing=None, heading_color=None, heading_sizes={},
                    first_line_indent=None, justify=False),
    # Требования заказчика к стандартному шаблону (2026-10-28): Times New Roman 14,
    # без интервалов между абзацами, межстрочный 1,5, все заголовки черные,
    # текст по ширине, абзацный отступ 1,25 см.
    "standard": dict(font="Times New Roman", size=14, space_before=0, space_after=0,
                     line_spacing=1.5, heading_color="000000", heading_sizes={},
                     first_line_indent=1.25, justify=True),
}
OUTPUTS = {"default": "reference.docx", "standard": "reference-standard.docx"}
HEADINGS = ["Title", "Subtitle", "Author", "Date", "Abstract Title"] + [f"Heading {i}" for i in range(1, 10)]
BODY_STYLES = ["Normal", "Body Text", "First Paragraph", "Compact", "Block Text", "Abstract",
               "Bibliography", "Caption", "Table Caption", "Image Caption",
               "Definition Term", "Definition", "Footnote Text", "Source Code"]

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


def _style(styles, name: str):
    """Lookup by display name or style id: python-docx's own lookup trips over the
    built-in heading names ("heading 1" vs "Heading 1")."""
    wanted = {name, name.replace(" ", ""), name.lower()}
    for st in styles:
        if st.type == WD_STYLE_TYPE.PARAGRAPH and (st.name in wanted or st.style_id in wanted):
            return st
    return None


def apply_profile(doc: Document, profile: dict) -> None:
    """Fonts, sizes, spacing and heading color of every known style."""
    styles = doc.styles
    body_pt = Pt(profile["size"])
    for name in BODY_STYLES + HEADINGS:
        st = _style(styles, name)
        if st is None:
            continue
        st.font.name = profile["font"]
        # East-Asian/complex-script font slots too, or Word falls back to Calibri there
        rpr = st.element.get_or_add_rPr()
        rfonts = rpr.find(qn("w:rFonts"))
        if rfonts is None:
            rfonts = rpr.makeelement(qn("w:rFonts"), {})
            rpr.insert(0, rfonts)
        for attr in ("w:ascii", "w:hAnsi", "w:eastAsia", "w:cs"):
            rfonts.set(qn(attr), profile["font"])
        # theme fonts/colors (pandoc's headings: majorHAnsi, accent1) override explicit values
        for attr in ("w:asciiTheme", "w:hAnsiTheme", "w:eastAsiaTheme", "w:cstheme"):
            if rfonts.get(qn(attr)) is not None:
                del rfonts.attrib[qn(attr)]
        color = rpr.find(qn("w:color"))
        if color is not None:
            for attr in ("w:themeColor", "w:themeShade", "w:themeTint"):
                if color.get(qn(attr)) is not None:
                    del color.attrib[qn(attr)]
        if name in HEADINGS:
            st.font.size = Pt(profile["heading_sizes"].get(name, profile["size"]))
            if profile["heading_color"]:
                st.font.color.rgb = RGBColor.from_string(profile["heading_color"])
            if st.font.bold is None:
                st.font.bold = True
            # headings inherit from Normal: no body indent / justification there
            st.paragraph_format.first_line_indent = Cm(0)
            if name in ("Title", "Subtitle", "Author", "Date", "Abstract Title"):
                st.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
            elif profile["justify"]:
                st.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.LEFT
        else:
            st.font.size = body_pt
        pf = st.paragraph_format
        if profile["space_before"] is not None:
            pf.space_before = Pt(profile["space_before"])
        if profile["space_after"] is not None:
            pf.space_after = Pt(profile["space_after"])
        if profile["line_spacing"] is not None:
            pf.line_spacing = profile["line_spacing"]
        if name in ("Body Text", "First Paragraph", "Normal"):
            if profile["first_line_indent"] is not None:
                pf.first_line_indent = Cm(profile["first_line_indent"])
            if profile["justify"]:
                pf.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY


def build(profile_name: str) -> Path:
    profile = PROFILES[profile_name]
    out = DATA / OUTPUTS[profile_name]
    out.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["pandoc", "-o", str(out), "--print-default-data-file", "reference.docx"],
        check=True,
    )

    doc = Document(str(out))
    sec = doc.sections[0]
    sec.page_width, sec.page_height = PAGE_W, PAGE_H
    sec.left_margin = sec.right_margin = sec.top_margin = sec.bottom_margin = MARGIN
    text_width = PAGE_W - 2 * MARGIN
    styles = doc.styles
    apply_profile(doc, profile)

    base = styles["Body Text"]
    sp_before = profile["space_before"]
    sp_after = profile["space_after"]
    for name, before in THEOREM_STYLES.items():
        try:
            st = styles[name]
        except KeyError:
            st = styles.add_style(name, WD_STYLE_TYPE.PARAGRAPH)
        st.base_style = base
        st.paragraph_format.space_before = Pt(before if sp_before is None else sp_before)
        st.paragraph_format.space_after = Pt(6 if sp_after is None else sp_after)
        st.paragraph_format.keep_together = True

    # styles based on Body Text that must not inherit the body indent/justification
    for name in ("Compact", "Bibliography", "Image Caption", "Table Caption"):
        st = _style(styles, name)
        if st is not None:
            st.paragraph_format.first_line_indent = Cm(0)
            if name in ("Image Caption", "Table Caption"):
                st.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
            elif profile["justify"]:
                st.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY

    # center / flushright / flushleft environments (filters/lists.lua)
    for name, align in (("Centered", WD_ALIGN_PARAGRAPH.CENTER),
                        ("Right Aligned", WD_ALIGN_PARAGRAPH.RIGHT),
                        ("Left Aligned", WD_ALIGN_PARAGRAPH.LEFT)):
        try:
            st = styles[name]
        except KeyError:
            st = styles.add_style(name, WD_STYLE_TYPE.PARAGRAPH)
        st.base_style = base
        st.paragraph_format.alignment = align
        st.paragraph_format.first_line_indent = Cm(0)

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
    pf.alignment = WD_ALIGN_PARAGRAPH.LEFT  # tabs do the centering
    pf.space_before = Pt(6 if sp_before is None else sp_before)
    pf.space_after = Pt(6 if sp_after is None else sp_after)
    pf.keep_together = True
    pf.tab_stops.clear_all()
    pf.tab_stops.add_tab_stop(text_width // 2, WD_TAB_ALIGNMENT.CENTER)
    pf.tab_stops.add_tab_stop(text_width, WD_TAB_ALIGNMENT.RIGHT)
    doc.save(str(out))
    print(f"written {out}")
    return out


def main() -> None:
    for name in PROFILES:
        build(name)


if __name__ == "__main__":
    main()
