"""Extract cleveref's default \\crefname/\\Crefname texts and conjunctions for the
languages we support into src/tex2docx/data/cleveref-names.json.

Run when cleveref changes:  python scripts/make_cleveref_names.py
The russian texts are written with \\cyr* macros in cleveref.sty; they are decoded here.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "src" / "tex2docx" / "data" / "cleveref-names.json"
LANGUAGES = ("english", "russian", "ukrainian")
CYR = dict(a="а", b="б", v="в", g="г", d="д", e="е", zh="ж", z="з", i="и", ishrt="й", k="к",
           l="л", m="м", n="н", o="о", p="п", r="р", s="с", t="т", u="у", f="ф", h="х", c="ц",
           ch="ч", sh="ш", shch="щ", hrdsn="ъ", ery="ы", sftsn="ь", erev="э", yu="ю", ya="я",
           yo="е", ie="є", ii="і", yi="ї", gup="ґ")


def decyr(s: str) -> str:
    def rep(m: re.Match[str]) -> str:
        name = m.group(1)
        ch = CYR.get(name[3:].lower(), "?")
        return ch.upper() if name[0] == "C" else ch

    s = re.sub(r"\\(cyr[a-z]+|CYR[A-Z]+)\s*", rep, s)
    return s.replace("\\nobreakspace", " ").replace("\\ ", " ").replace("~", " ").strip()


def language_block(src: str, lang: str) -> str | None:
    m = re.search(r"\\cref@addlanguagedefs\{%s\}\{" % lang, src)
    if not m:
        return None
    i, depth = m.end(), 1
    while depth:
        depth += {"{": 1, "}": -1}.get(src[i], 0)
        i += 1
    return re.sub(r"%[^\n]*\n\s*", "", src[m.end():i - 1])


def main() -> None:
    sty = subprocess.check_output(["kpsewhich", "cleveref.sty"], text=True).strip()
    src = Path(sty).read_text(encoding="utf-8", errors="replace")
    out: dict[str, dict] = {}
    for lang in LANGUAGES:
        b = language_block(src, lang)
        if b is None:
            continue
        names: dict[str, dict[str, str]] = {}
        for m in re.finditer(r"\\(Crefname|crefname)\{(\w+)\}\{([^{}]*)\}\{([^{}]*)\}", b):
            kind, typ, sg, pl = m.groups()
            d = names.setdefault(typ, {})
            d["Sg" if kind == "Crefname" else "sg"] = decyr(sg)
            d["Pl" if kind == "Crefname" else "pl"] = decyr(pl)
        conj = {}
        for key in ("pair", "middle", "last", "range"):
            mm = re.search(r"\\renewcommand\{?\\cref%sconjunction\}?\s*\{([^{}]*)\}" % key, b)
            conj[key] = decyr(mm.group(1)) if mm else ""
        out[lang] = {"names": names, "conjunctions": conj}
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"written {OUT}: {', '.join(out)}")


if __name__ == "__main__":
    main()
