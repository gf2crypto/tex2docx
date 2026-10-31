"""Stage 1: open the docx, read what pandoc throws away, load the sidecar.

Status: implemented (M0): bookmarks (name -> plain text inside), simple fields
(w:instr), the sidecar <name>.t2d.xml next to the docx, document language
(sidecar, config, else guessed from the text). M1: the working copy
workdir/prepared.docx with markers for pandoc (stages/prepare.py).
"""

from __future__ import annotations

import re
import zipfile

from tex2docx.sidecar import Sidecar
from tex2docx.texscan import document_language

from ..context import Context
from . import StageError
from .prepare import prepare_docx

STAGE = "extract"
W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def read_facts(xml: bytes) -> tuple[dict[str, str], list[str], str]:
    """(bookmarks, fields, plain text) from word/document.xml."""
    from lxml import etree

    root = etree.fromstring(xml)
    ns = {"w": W}
    fields = [f.get(f"{{{W}}}instr", "") for f in root.iter(f"{{{W}}}fldSimple")]
    # bookmark text: w:t runs between bookmarkStart and the matching bookmarkEnd
    starts = {b.get(f"{{{W}}}id"): b for b in root.iter(f"{{{W}}}bookmarkStart")}
    bookmarks: dict[str, str] = {}
    for bid, start in starts.items():
        name = start.get(f"{{{W}}}name", "")
        if not name or name.startswith("_"):
            continue
        texts = []
        for el in start.itersiblings():
            if el.tag == f"{{{W}}}bookmarkEnd" and el.get(f"{{{W}}}id") == bid:
                break
            texts += [t.text or "" for t in el.iter(f"{{{W}}}t")]
        bookmarks[name] = "".join(texts).strip()
    plain = " ".join(t.text or "" for t in root.iterfind(".//w:t", ns))
    return bookmarks, fields, plain


def run(ctx: Context) -> None:
    if not ctx.source.is_file():
        raise StageError("extract.no-source", str(ctx.source))
    try:
        with zipfile.ZipFile(ctx.source) as z:
            xml = z.read("word/document.xml")
    except (zipfile.BadZipFile, KeyError) as e:
        raise StageError("extract.not-a-docx", type(e).__name__) from e
    ctx.bookmarks, ctx.fields, plain = read_facts(xml)
    sc = Sidecar.load(Sidecar.path_for(ctx.source))
    if sc is not None:
        ctx.sidecar = sc
        ctx.report.info(STAGE, "sidecar.read", Sidecar.path_for(ctx.source).name)
    if ctx.config.language:
        ctx.language = ctx.config.language
    elif ctx.sidecar.language:
        ctx.language = ctx.sidecar.language
    else:
        ctx.language, guessed = document_language("\\begin{document}" + plain)
        if guessed:
            ctx.report.info(STAGE, "names.language-guessed", ctx.language)
    n_bm = sum(1 for b in ctx.bookmarks if b.startswith("t2d_"))
    if n_bm:
        ctx.report.info(STAGE, "extract.t2d-bookmarks", str(n_bm))
    ctx.workdir.mkdir(parents=True, exist_ok=True)
    ctx.prepared = ctx.workdir / "prepared.docx"
    marked = prepare_docx(ctx.source, ctx.prepared)
    if marked:
        ctx.report.info(STAGE, "extract.bookmarks", str(marked))
    if re.search(r"[Ѐ-ӿ]", plain) and ctx.language == "english":
        ctx.report.info(STAGE, "extract.cyrillic-but-english", "")
