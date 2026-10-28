"""The conversion pipeline: an ordered list of stages over one Context."""

from __future__ import annotations

import shutil
import tempfile
import traceback
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from .config import Config
from .context import Context
from .report import Report
from .stages import (
    StageError,
    algorithms,
    autolabel,
    figures,
    flatten,
    latex_compile,
    macros,
    normalize,
    pandoc_run,
    postprocess,
    theorems,
)


@dataclass(frozen=True)
class Stage:
    name: str
    run: Callable[[Context], None]
    fatal: bool  # an error here stops the conversion


STAGES: list[Stage] = [
    Stage("flatten", flatten.run, fatal=True),
    Stage("autolabel", autolabel.run, fatal=False),
    Stage("latex", latex_compile.run, fatal=False),
    Stage("theorems", theorems.run, fatal=False),
    Stage("normalize", normalize.run, fatal=False),
    Stage("macros", macros.run, fatal=False),
    Stage("algorithms", algorithms.run, fatal=False),
    Stage("figures", figures.run, fatal=False),
    Stage("pandoc", pandoc_run.run, fatal=True),
    Stage("postprocess", postprocess.run, fatal=True),
]


def convert(source: Path, output: Path, config: Config | None = None, *,
            workdir: Path | None = None, keep_workdir: bool = False) -> Report:
    """Convert source .tex to output .docx. Always writes <output>.report.{md,json}."""
    config = config or Config()
    source = source.resolve()
    output = output.resolve()
    own_tmp = workdir is None
    wd = Path(tempfile.mkdtemp(prefix="t2d-")) if own_tmp else workdir.resolve()
    wd.mkdir(parents=True, exist_ok=True)

    ctx = Context(source=source, output=output, workdir=wd, config=config)
    try:
        for st in STAGES:
            try:
                st.run(ctx)
            except StageError as e:
                ctx.report.error(st.name, e.code, e.detail)
                if st.fatal:
                    break
            except Exception as e:  # a bug in our code: record it, keep the report useful
                where = traceback.extract_tb(e.__traceback__)[-1]
                at = f"{Path(where.filename).name}:{where.lineno}"
                ctx.report.error(st.name, "internal-error", f"{type(e).__name__} at {at}")
                if st.fatal:
                    break
    finally:
        if own_tmp and keep_workdir:
            ctx.report.info("pipeline", "workdir-kept", str(wd))
        output.parent.mkdir(parents=True, exist_ok=True)
        ctx.report.write(output)
        if own_tmp and not keep_workdir:
            shutil.rmtree(wd, ignore_errors=True)
    return ctx.report
