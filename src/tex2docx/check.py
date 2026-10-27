"""tex2docx --check: is everything in place? Meant for a computer without internet,
where a missing piece cannot be fetched later. Exit status 1 if something required is missing."""

from __future__ import annotations

import importlib
import shutil
import subprocess
import sys

TOOLS = {  # name -> (required, why)
    "pandoc": (True, "конвертация LaTeX → docx (нужна версия ≥ 3.1)"),
    "latexmk": (True, "компиляция LaTeX для номеров, рисунков, библиографии"),
    "pdflatex": (True, "движок TeX по умолчанию"),
    "kpsewhich": (True, "поиск пакетов TeX"),
    "bibtex": (True, "библиография BibTeX"),
    "pdftoppm": (True, "растеризация рисунков и формул-картинок (poppler)"),
    "xelatex": (False, "движок для документов с fontspec (--engine xelatex)"),
    "lualatex": (False, "движок LuaLaTeX (--engine lualatex)"),
    "biber": (False, "библиография biblatex с backend=biber"),
    "magick": (False, "перевод BMP/TIFF в PNG, если нет Pillow"),
}
MODULES = {"docx": "python-docx", "lxml": "lxml", "yaml": "PyYAML"}
OPTIONAL_MODULES = {"PIL": "Pillow (перевод BMP/TIFF в PNG)"}
# TeX files the pipeline relies on: without them conversion degrades or fails
TEX_FILES = {
    "preview.sty": "рисунки TikZ, алгоритмы, формулы-картинки (пакет preview)",
    "t2aenc.def": "кириллица в pdflatex (пакет cyrillic)",
    "russianb.ldf": "babel russian",
    "amsthm.sty": "теоремы (amsthm)",
    "amsmath.sty": "amsmath",
    "tikz.sty": "TikZ",
    "algorithm.sty": "алгоритмы (algorithms)",
    "algpseudocode.sty": "алгоритмы (algorithmicx)",
    "biblatex.sty": "biblatex",
    "gost2008.bst": "стиль BibTeX ГОСТ (пакет gost)",
    "fontspec.sty": "fontspec (xelatex/lualatex)",
}


def _version(cmd: list[str]) -> str:
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=60,
                             encoding="utf-8", errors="replace")
        return (out.stdout or out.stderr).strip().splitlines()[0]
    except Exception as e:  # noqa: BLE001
        return f"? ({type(e).__name__})"


def main() -> int:
    ok = True
    print(f"python {sys.version.split()[0]}")
    for name, (required, why) in TOOLS.items():
        path = shutil.which(name)
        mark = "ok  " if path else ("НЕТ " if required else "нет ")
        flag = "-v" if name == "pdftoppm" else "--version"
        info = _version([path, flag]) if path else why
        print(f"{mark} {name:10} {info}")
        ok &= bool(path) or not required
    if shutil.which("pandoc"):
        ver = _version(["pandoc", "--version"]).split()[-1]
        try:
            if tuple(int(x) for x in ver.split(".")[:2]) < (3, 1):
                print(f"НЕТ  pandoc {ver} слишком старый: нужен 3.1 или новее")
                ok = False
        except ValueError:
            pass
    for mod, pkg in MODULES.items():
        try:
            importlib.import_module(mod)
            print(f"ok   {pkg}")
        except ImportError:
            print(f"НЕТ  {pkg} (pip)")
            ok = False
    for mod, pkg in OPTIONAL_MODULES.items():
        try:
            importlib.import_module(mod)
            print(f"ok   {pkg}")
        except ImportError:
            print(f"нет  {pkg} — необязательно")
    if shutil.which("kpsewhich"):
        found = subprocess.run(["kpsewhich", *TEX_FILES], capture_output=True, text=True,
                               encoding="utf-8", errors="replace").stdout
        for f, why in TEX_FILES.items():
            present = f in found
            print(f"{'ok  ' if present else 'нет '} TeX: {f:18} {why}")
            if f in ("preview.sty", "t2aenc.def", "amsthm.sty", "amsmath.sty") and not present:
                ok = False
    print("\nВсе необходимое на месте." if ok else "\nЧего-то не хватает: см. строки «НЕТ».")
    return 0 if ok else 1
