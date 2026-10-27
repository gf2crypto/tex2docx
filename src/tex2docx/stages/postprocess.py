"""Stage 9: fix the .docx itself (python-docx / lxml).

Status: PARTIAL - only copies the file. TODO (M2-M3), see ROADMAP.md:
- Russian typography: non-breaking space after single-letter prepositions,
  between number and unit;
- theorem header keep-with-next, proof end mark alignment;
- equation and theorem numbers as SEQ fields + bookmarks, so Word renumbers
  on edit and cross references become REF fields (optional, config switch).
"""

from __future__ import annotations

import shutil

from ..context import Context
from . import StageError

STAGE = "postprocess"


def run(ctx: Context) -> None:
    if ctx.docx is None:
        raise StageError("postprocess.no-input")
    ctx.output.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ctx.docx, ctx.output)
