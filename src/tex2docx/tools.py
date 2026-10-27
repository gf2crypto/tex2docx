"""External tools: pandoc, latexmk, pdftoppm. The only place that spawns processes."""

from __future__ import annotations

import os
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
    cmd = [
        require("latexmk"), LATEXMK_ENGINE_FLAG[engine],
        "-interaction=nonstopmode", "-file-line-error", "-f",
        tex_file.name,
    ]
    return run(cmd, cwd=tex_file.parent, env=tex_env(*search_dirs), timeout=timeout)


def log_errors(log_file: Path, limit: int = 20) -> list[str]:
    """Error headers ('! ...' or 'file:line: ...') from a TeX log, without context lines."""
    if not log_file.exists():
        return []
    out = []
    for line in log_file.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith("!") or ": LaTeX Error:" in line or ": Undefined control" in line:
            out.append(line.strip())
            if len(out) >= limit:
                break
    return out
