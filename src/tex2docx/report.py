"""Conversion report: everything the converter could not do faithfully.

The report is what the user sends back when a document converts badly, so it
must never contain document text. Allowed: command and environment names,
label names, counts, line numbers, tool error headers.
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path

LEVELS = ("info", "warning", "error")


@dataclass
class Item:
    level: str
    stage: str
    code: str  # stable identifier, e.g. "pandoc.skipped-command"
    detail: str = ""  # command/env/label name; never document text
    line: int | None = None  # line in the flattened source


class Report:
    def __init__(self) -> None:
        self.items: list[Item] = []

    def add(self, level: str, stage: str, code: str, detail: str = "",
            line: int | None = None) -> None:
        assert level in LEVELS, level
        self.items.append(Item(level, stage, code, detail, line))

    def info(self, stage: str, code: str, detail: str = "", line: int | None = None) -> None:
        self.add("info", stage, code, detail, line)

    def warn(self, stage: str, code: str, detail: str = "", line: int | None = None) -> None:
        self.add("warning", stage, code, detail, line)

    def error(self, stage: str, code: str, detail: str = "", line: int | None = None) -> None:
        self.add("error", stage, code, detail, line)

    @property
    def has_errors(self) -> bool:
        return any(i.level == "error" for i in self.items)

    def counts(self) -> Counter[str]:
        return Counter(i.level for i in self.items)

    def write(self, base: Path) -> tuple[Path, Path]:
        """Write <base>.report.json and <base>.report.md, return both paths."""
        jpath = base.with_suffix(".report.json")
        mpath = base.with_suffix(".report.md")
        jpath.write_text(
            json.dumps([asdict(i) for i in self.items], ensure_ascii=False, indent=1),
            encoding="utf-8",
        )
        mpath.write_text(self.to_markdown(), encoding="utf-8")
        return jpath, mpath

    def to_markdown(self) -> str:
        c = self.counts()
        out = [
            "# Отчет tex2docx",
            "",
            f"Ошибок: {c['error']}, предупреждений: {c['warning']}, заметок: {c['info']}.",
            "",
        ]
        # Group identical (level, code, detail) so a macro used 300 times is one line.
        grouped: Counter[tuple[str, str, str, str]] = Counter(
            (i.level, i.stage, i.code, i.detail) for i in self.items
        )
        lines_of: dict[tuple[str, str, str, str], list[int]] = {}
        for i in self.items:
            if i.line is not None:
                lines_of.setdefault((i.level, i.stage, i.code, i.detail), []).append(i.line)
        for level in reversed(LEVELS):
            rows = [k for k in grouped if k[0] == level]
            if not rows:
                continue
            out += [f"## {level}", "",
                    "| этап | код | объект | раз | строки |", "|---|---|---|---|---|"]
            for k in sorted(rows):
                ls = lines_of.get(k, [])
                shown = ", ".join(map(str, ls[:8])) + (" …" if len(ls) > 8 else "")
                out.append(f"| {k[1]} | {k[2]} | `{k[3]}` | {grouped[k]} | {shown} |")
            out.append("")
        return "\n".join(out)
