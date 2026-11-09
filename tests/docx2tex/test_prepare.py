"""stages/prepare.py: what pandoc would lose is written into the text as markers."""

from __future__ import annotations

from docx2tex.stages.prepare import (
    MARK_CLOSE,
    MARK_CONT,
    MARK_END,
    MARK_START,
    MARK_TAB,
    continuation_levels,
    prepare_xml,
)

W = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'


def _doc(body: str) -> bytes:
    return f'<w:document {W}><w:body>{body}</w:body></w:document>'.encode("utf-8")


def test_body_level_bookmark_marks_first_and_last_paragraph():
    xml = _doc('<w:bookmarkStart w:id="1" w:name="thm:main"/>'
               '<w:p><w:pPr><w:pStyle w:val="Theorem"/></w:pPr><w:r><w:t>Теорема</w:t></w:r></w:p>'
               '<w:p><w:r><w:t>формула</w:t></w:r></w:p>'
               '<w:bookmarkEnd w:id="1"/>'
               '<w:p><w:r><w:t>дальше</w:t></w:r></w:p>')
    out, n = prepare_xml(xml)
    text = out.decode("utf-8")
    assert n == 1
    start, close = MARK_START + "thm:main" + MARK_END, MARK_CLOSE + "thm:main" + MARK_END
    assert text.index("</w:pPr>") < text.index(start) < text.index("Теорема")
    assert text.index("формула") < text.index(close) < text.index("дальше")


def test_in_paragraph_bookmark_and_words_own_are_handled():
    xml = _doc('<w:p><w:r><w:t>(</w:t></w:r><w:bookmarkStart w:id="2" w:name="t2d_eq_a"/>'
               '<w:r><w:t>1.1</w:t></w:r><w:bookmarkEnd w:id="2"/><w:r><w:t>)</w:t></w:r>'
               '<w:bookmarkStart w:id="3" w:name="_GoBack"/><w:bookmarkEnd w:id="3"/></w:p>')
    out, n = prepare_xml(xml)
    text = out.decode("utf-8")
    assert n == 1
    assert MARK_START + "t2d_eq_a" + MARK_END in text
    assert "_GoBack" + MARK_END not in text
    assert MARK_CLOSE not in text


def test_ref_fields_become_hyperlinks_and_seq_fields_their_result():
    simple = ('<w:p><w:fldSimple w:instr=" REF t2d_thm_main \\h "><w:r><w:t>1.2</w:t></w:r></w:fldSimple>'
              '<w:fldSimple w:instr=" SEQ equation "><w:r><w:t>3</w:t></w:r></w:fldSimple></w:p>')
    complex_ = ('<w:p><w:r><w:fldChar w:fldCharType="begin"/></w:r>'
                '<w:r><w:instrText> REF t2d_eq_a \\h </w:instrText></w:r>'
                '<w:r><w:fldChar w:fldCharType="separate"/></w:r>'
                '<w:r><w:t>(2.1)</w:t></w:r>'
                '<w:r><w:fldChar w:fldCharType="end"/></w:r></w:p>')
    out, _ = prepare_xml(_doc(simple + complex_))
    text = out.decode("utf-8")
    assert '<w:hyperlink w:anchor="t2d_thm_main"><w:r><w:t>1.2</w:t></w:r></w:hyperlink>' in text
    assert '<w:hyperlink w:anchor="t2d_eq_a"><w:r><w:t>(2.1)</w:t></w:r></w:hyperlink>' in text
    assert "fldSimple" not in text and "fldChar" not in text and "<w:t>3</w:t>" in text


def test_tabs_become_markers():
    out, _ = prepare_xml(_doc('<w:p><w:r><w:t>1:</w:t></w:r><w:r><w:tab/></w:r><w:r><w:tab/></w:r></w:p>'))
    assert out.decode("utf-8").count(MARK_TAB) == 2


def test_item_continuations_are_marked():
    """pandoc writes the second paragraph of a list item (a theorem in \\item) with a
    blank-bullet list level; prepare marks it so the filter can put it back into the item."""
    numbering = (f'<w:numbering {W}>'
                 '<w:abstractNum w:abstractNumId="990"><w:lvl w:ilvl="0"><w:numFmt w:val="bullet"/>'
                 '<w:lvlText w:val=" "/></w:lvl></w:abstractNum>'
                 '<w:abstractNum w:abstractNumId="991"><w:lvl w:ilvl="0"><w:numFmt w:val="bullet"/>'
                 '<w:lvlText w:val="\uf0b7"/></w:lvl></w:abstractNum>'
                 '<w:num w:numId="1000"><w:abstractNumId w:val="990"/></w:num>'
                 '<w:num w:numId="1001"><w:abstractNumId w:val="991"/></w:num>'
                 '</w:numbering>').encode()
    levels = continuation_levels(numbering)
    assert levels == {("1000", "0")}

    def item(num_id: str, text: str) -> str:
        return (f'<w:p><w:pPr><w:numPr><w:ilvl w:val="0"/><w:numId w:val="{num_id}"/></w:numPr>'
                f'</w:pPr><w:r><w:t>{text}</w:t></w:r></w:p>')

    out, _ = prepare_xml(_doc(item("1001", "пункт") + item("1000", "Лемма")), levels)
    text = out.decode("utf-8")
    assert text.count(MARK_CONT) == 1
    assert text.index("пункт") < text.index(MARK_CONT) < text.index("Лемма")


def test_parallel_delimiter_and_footnotes():
    """U+2225 around a norm becomes U+2016 (texmath reads only that one as a delimiter);
    footnotes.xml is prepared too (bookmarks of formulas in footnotes)."""
    m = 'xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math"'
    xml = (f'<w:footnotes {W} {m}><w:footnote w:id="1"><w:p>'
           '<m:oMath><m:d><m:dPr><m:begChr m:val="\u2225"/><m:endChr m:val="\u2225"/></m:dPr>'
           '<m:e><m:r><m:t>v</m:t></m:r></m:e></m:d></m:oMath>'
           '<w:bookmarkStart w:id="3" w:name="t2d_eq_fn"/><w:r><w:t>1</w:t></w:r>'
           '<w:bookmarkEnd w:id="3"/></w:p></w:footnote></w:footnotes>').encode()
    out, n = prepare_xml(xml)
    text = out.decode("utf-8")
    assert n == 1 and MARK_START + "t2d_eq_fn" + MARK_END in text
    assert "\u2225" not in text and text.count("\u2016") == 2
