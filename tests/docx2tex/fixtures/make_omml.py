"""Produce omml/*.xml and pic.png for the docx2tex corpus (needs pandoc)."""

from __future__ import annotations

import struct
import subprocess
import tempfile
import zipfile
import zlib
from pathlib import Path

HERE = Path(__file__).parent
FORMULAS = {"inline-x2": "$x^2$", "display-sum": r"$$\sum_{i=1}^{n} x_i$$",
            "bold-G": r"$\mathbf{G}\mathbf{x} \in \mathbb{F}_q^n$"}
NS = ('xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math" '
      'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"')


def main() -> None:
    (HERE / "omml").mkdir(exist_ok=True)
    for name, tex in FORMULAS.items():
        out = Path(tempfile.mkdtemp()) / f"{name}.docx"
        subprocess.run(["pandoc", "-f", "latex", "-t", "docx", "-o", str(out)], input=tex,
                       text=True, check=True)
        xml = zipfile.ZipFile(out).read("word/document.xml").decode("utf-8")
        start = xml.index("<m:oMath>")
        end = xml.index("</m:oMath>") + len("</m:oMath>")
        frag = "<m:oMath " + NS + ">" + xml[start + len("<m:oMath>"):end]
        (HERE / "omml" / f"{name}.xml").write_text(frag, encoding="utf-8")
    w, h = 40, 20
    raw = b"".join(b"\x00" + b"\x40\x80\xc0" * w for _ in range(h))

    def chunk(t: bytes, d: bytes) -> bytes:
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)

    png = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
           + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))
    (HERE / "pic.png").write_bytes(png)
    print("written")


if __name__ == "__main__":
    main()
