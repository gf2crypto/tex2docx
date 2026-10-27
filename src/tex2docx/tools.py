"""External tools: pandoc, latexmk, pdftoppm. The only place that spawns processes."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path


class ToolError(RuntimeError):
    pass


def require(name: str) -> str:
    path = shutil.which(name)
    if path is None:
        raise ToolError(f"required tool not found in PATH: {name}")
    return path


def run(cmd: list[str], *, cwd: Path, env: dict[str, str] | None = None,
        timeout: int = 600) -> subprocess.CompletedProcess[str]:
    """Run a command, capture text output. Never raises on non-zero exit."""
    try:
        return subprocess.run(
            cmd, cwd=cwd, env=env, timeout=timeout,
            capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
    except subprocess.TimeoutExpired as e:
        raise ToolError(f"{Path(cmd[0]).name} timed out after {timeout}s") from e


def tex_env(*search_dirs: Path) -> dict[str, str]:
    """Environment where TeX also finds files next to the original source.

    The trailing separator keeps the default TeX search path.
    """
    env = dict(os.environ)
    extra = os.pathsep.join(str(d) for d in search_dirs)
    for var in ("TEXINPUTS", "BIBINPUTS", "BSTINPUTS"):
        env[var] = extra + os.pathsep + env.get(var, "")
    return env


LATEXMK_ENGINE_FLAG = {"pdflatex": "-pdf", "xelatex": "-xelatex", "lualatex": "-lualatex"}


def latexmk(tex_file: Path, engine: str, *, search_dirs: list[Path],
            timeout: int) -> subprocess.CompletedProcess[str]:
    """Compile tex_file (a copy in the workdir) with cwd = the document's own directory,
    so that paths like \\documentclass{./class/x} and \\graphicspath resolve as for the
    author; every output goes to the copy's directory (-outdir), nothing next to the source."""
    cwd = search_dirs[0] if search_dirs else tex_file.parent
    cmd = [
        require("latexmk"), LATEXMK_ENGINE_FLAG[engine],
        "-interaction=nonstopmode", "-file-line-error", "-f",
        f"-outdir={tex_file.parent}", str(tex_file),
    ]
    return run(cmd, cwd=cwd, env=tex_env(*search_dirs), timeout=timeout)


def kpsewhich(names: list[str], *, cwd: Path, env: dict[str, str] | None = None) -> dict[str, Path]:
    """Resolve file names (with extension) the way TeX does. Missing names are absent."""
    if not names:
        return {}
    proc = run([require("kpsewhich"), *names], cwd=cwd, env=env, timeout=60)
    found: dict[str, Path] = {}
    for line in proc.stdout.splitlines():
        line = line.strip()
        if line:
            found[Path(line).name] = (cwd / line).resolve()
    return found


def texmf_var(name: str, *, cwd: Path, env: dict[str, str] | None = None) -> str:
    proc = run([require("kpsewhich"), "-var-value", name], cwd=cwd, env=env, timeout=60)
    return proc.stdout.strip()


MAX_PRINT_LINE = 79  # TeX wraps log lines at this width; joined back below


def unwrap_log(text: str) -> list[str]:
    """Lines of a TeX log with the wrapping at max_print_line undone."""
    out: list[str] = []
    buf = ""
    for line in text.splitlines():
        buf += line
        if len(line) == MAX_PRINT_LINE:
            continue  # wrapped: the next line continues this one
        out.append(buf)
        buf = ""
    if buf:
        out.append(buf)
    return out


def log_errors(log_file: Path, limit: int = 20) -> list[str]:
    """Error headers ('! ...' or 'file:line: ...') from a TeX log, without context lines."""
    if not log_file.exists():
        return []
    out = []
    for line in unwrap_log(log_file.read_text(encoding="utf-8", errors="replace")):
        if (line.startswith("!") or ": LaTeX Error:" in line or ": Undefined control" in line
                or re.search(r": Package [\w.]+ Error:", line)):
            out.append(line.strip())
            if len(out) >= limit:
                break
    return out
