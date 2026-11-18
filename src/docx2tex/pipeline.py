"""The docx2tex pipeline, same shape as tex2docx.pipeline."""

from __future__ import annotations

import shutil
import traceback
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from tex2docx.report import Report
from tex2docx.sidecar import Sidecar
from tex2docx.tools import create_workdir

from .config import Config
from .context import Context
from .stages import StageError, bibmatch, check, emit, extract, maindoc, normalize, pandoc_run


class OutputConflictError(ValueError):
    """An output path would overwrite one of the input documents."""


@dataclass(frozen=True)
class Stage:
    name: str
    run: Callable[[Context], None]
    fatal: bool


STAGES: list[Stage] = [
    Stage("extract", extract.run, fatal=True),
    Stage("maindoc", maindoc.run, fatal=True),
    Stage("pandoc", pandoc_run.run, fatal=True),
    Stage("normalize", normalize.run, fatal=False),
    Stage("bibmatch", bibmatch.run, fatal=False),
    Stage("emit", emit.run, fatal=True),
    Stage("check", check.run, fatal=False),
]


def convert(source: Path, output: Path, config: Config | None = None, *, standalone: bool = False,
            workdir: Path | None = None, keep_workdir: bool = False, into: Path | None = None) -> Report:
    config = config or Config()
    source, output = source.resolve(), output.resolve()
    main = into.resolve() if into else None
    outputs = [output, Sidecar.path_for(output), *Report("docx2tex").paths(output)]
    if standalone:
        outputs.append(output.with_suffix(".standalone.tex"))
    for target in outputs:
        for original in (source, main):
            if original is None:
                continue
            if target.resolve() == original or (
                target.exists() and original.exists() and target.samefile(original)
            ):
                raise OutputConflictError(
                    f"Output {target} would overwrite {original}. Choose a different -o path."
                )
    own_tmp = workdir is None
    wd = create_workdir(workdir, "d2t-")
    ctx = Context(source=source, output=output, workdir=wd, config=config, standalone=standalone,
                  main=main)
    try:
        for st in STAGES:
            try:
                st.run(ctx)
            except StageError as e:
                ctx.report.error(st.name, e.code, e.detail)
                if st.fatal:
                    break
            except Exception as e:  # noqa: BLE001 - a bug: keep the report useful
                where = traceback.extract_tb(e.__traceback__)[-1]
                ctx.report.error(st.name, "internal-error",
                                 f"{type(e).__name__} at {Path(where.filename).name}:{where.lineno}")
                if st.fatal:
                    break
    finally:
        output.parent.mkdir(parents=True, exist_ok=True)
        ctx.report.write(output)
        if ctx.report.output_written:  # the sidecar travels with this run's fragment
            sc = ctx.sidecar
            sc.language = sc.language or ctx.language
            sc.save(Sidecar.path_for(output))
        if own_tmp and not keep_workdir:
            shutil.rmtree(wd, ignore_errors=True)
    return ctx.report
