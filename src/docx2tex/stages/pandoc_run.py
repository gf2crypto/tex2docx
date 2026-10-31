"""Stage 2: pandoc docx -> LaTeX fragment with our filters; images extracted.

Status: implemented (M0). Data for the filters: JSON passed as metadata 'd2t-meta'.
Filter messages '[d2t] level code detail' go to the report (never document text).
"""

from __future__ import annotations

import hashlib
import json
import re
from importlib import resources
from pathlib import Path

from tex2docx.tools import ToolError, require
from tex2docx.tools import run as run_tool

from ..config import DEFAULT_THEOREM_ENVS
from ..context import Context
from . import StageError

STAGE = "pandoc"
FILTERS = ["structures.lua"]
_D2T = re.compile(r"^\[d2t\] (info|warning|error) (\S+) ?(.*)$")
_MATHFAIL = re.compile(r"Could not convert|Unable to parse OMML", re.I)


def _pkg_path(*parts: str) -> Path:
    return Path(str(resources.files("docx2tex").joinpath(*parts)))


def bookmark_labels(ctx: Context) -> dict[str, str]:
    """Bookmark name -> label: the sidecar's t2d_ names, plus the names pandoc >= 3.12
    gives to bookmarks and link targets made from identifiers: "_" + sha1(id) without
    its first hex digit (docs/pandoc-behavior.md)."""
    out = dict(ctx.sidecar.labels)
    for label in set(ctx.sidecar.labels.values()):
        out["_" + hashlib.sha1(label.encode("utf-8")).hexdigest()[1:40]] = label
    return out


def run(ctx: Context) -> None:
    pandoc = require("pandoc")
    meta = ctx.workdir / "d2t-meta.json"
    meta.write_text(json.dumps({
        "language": ctx.language,
        "bookmarks": ctx.bookmarks,
        "labels": bookmark_labels(ctx),
        "theorems": ctx.sidecar.theorems,
        "names": ctx.sidecar.names,
        "cites": ctx.sidecar.cites,
        "theorem_envs": {**DEFAULT_THEOREM_ENVS, **ctx.config.theorem_envs},
    }, ensure_ascii=False), encoding="utf-8")
    out = ctx.workdir / "pandoc.tex"
    # relative --extract-media so that image paths come out as media/..., not absolute
    cmd = [pandoc, str(ctx.prepared or ctx.source), "-f", "docx+styles", "-t", "latex", "-o", str(out),
           "--extract-media", "media", "-M", f"d2t-meta={meta}", "--wrap=none"]
    for f in FILTERS:
        cmd += ["--lua-filter", str(_pkg_path("filters", f))]
    try:
        proc = run_tool(cmd, cwd=ctx.workdir)
    except ToolError as e:
        raise StageError("pandoc.tool", str(e)) from e
    for line in proc.stderr.splitlines():
        if m := _D2T.match(line.strip()):
            if m.group(2) == "theorem.env":  # env|Title: what \newtheorem must provide
                env, _, title = m.group(3).partition("|")
                ctx.theorem_envs_used.setdefault(env, title)
                continue
            ctx.report.add(m.group(1), "filter", m.group(2), m.group(3))
        elif _MATHFAIL.search(line):
            ctx.report.warn(STAGE, "math.not-converted", "")
    if proc.returncode != 0 or not out.exists():
        tail = proc.stderr.strip().splitlines()[-1:] or ["no output"]
        raise StageError("pandoc.failed", tail[0][:200])
    ctx.tex = out.read_text(encoding="utf-8")
