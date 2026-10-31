"""stages/prepare.py: what pandoc would lose is written into the text as markers."""

from __future__ import annotations

from docx2tex.stages.prepare import MARK_CLOSE, MARK_END, MARK_START, MARK_TAB, prepare_xml

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
