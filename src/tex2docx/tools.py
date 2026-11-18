"""External tools: pandoc, latexmk, pdftoppm. The only place that spawns processes."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path


class ToolError(RuntimeError):
    pass


def create_workdir(parent: Path | None, prefix: str) -> Path:
    """Give each conversion its own intermediates, optionally under a retained directory."""
    if parent is not None:
        parent = parent.resolve()
        parent.mkdir(parents=True, exist_ok=True)
    return Path(tempfile.mkdtemp(prefix=prefix, dir=parent)).resolve()


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


_LOG_LOCATION = re.compile(r"^(?P<file>.+?):(?P<line>[0-9]+):\s*")
_PACKAGE_ERROR = re.compile(r"Package ([A-Za-z0-9_.-]+) Error:")
_ERROR_TYPES = (
    "Undefined control sequence",
    "LaTeX Error",
    "Emergency stop",
    "Missing character",
    "Runaway argument",
)


def log_errors(log_file: Path, limit: int = 20) -> list[tuple[str, int | None]]:
    """Extract fixed error categories and generated-source line numbers for reports."""
    if not log_file.exists():
        return []
    errors = []
    for line in unwrap_log(log_file.read_text(encoding="utf-8", errors="replace")):
        location = _LOG_LOCATION.match(line)
        message = line[location.end():] if location else line.removeprefix("!").lstrip()
        if not location and not line.startswith("!"):
            continue
        if package := _PACKAGE_ERROR.match(message):
            category = f"Package {package[1]} Error"
        else:
            category = next((kind for kind in _ERROR_TYPES if message.startswith(kind)), None)
            if category is None:
                if not line.startswith("!"):
                    continue
                category = "TeX error"
        number = None
        if location and location["file"].replace("\\", "/").rsplit("/", 1)[-1] == (
            log_file.stem + ".tex"
        ):
            number = int(location["line"])
        errors.append((category, number))
        if len(errors) >= limit:
            break
    return errors


def pandoc_failure(proc: subprocess.CompletedProcess[str]) -> str:
    """Describe a failed invocation without copying stderr into the shareable report."""
    if proc.returncode == 0:
        return "no output"
    if any(line.startswith("Error running filter") for line in proc.stderr.splitlines()):
        return f"filter failed (exit {proc.returncode})"
    return f"exit {proc.returncode}"
