# Архитектура

## Поток данных

```
main.tex ─► flatten ─► autolabel ─► latex ─────► theorems ─► normalize ─► macros ─► figures ─► pandoc ─► postprocess ─► out.docx
             │            │           │ .aux        │                                  │ preview   │ Lua-фильтры        │
             │            │           ▼             ▼                                  ▼           ▼                    ▼
             └─ ctx.latex_tex / ctx.tex   ctx.labels   ctx.theorems                 ctx.figures   ctx.docx        out.report.{md,json}
```

Все этапы получают один объект `Context` (`context.py`) и пишут файлы только в `ctx.workdir`.

| Этап | Файл | Что делает | Статус |
|---|---|---|---|
| flatten | `stages/flatten.py` | склейка `\input`/`\include`, пустые строки вместо строк-комментариев | готов |
| autolabel | `stages/autolabel.py` | `\label{t2d:auto:N}` для нумеруемых объектов без метки | готов |
| latex | `stages/latex_compile.py` | latexmk → `.aux` → `ctx.labels` | готов |
| theorems | `stages/theorems.py` | `\newtheorem`, `\theoremstyle` → `ctx.theorems` | готов (amsthm) |
| normalize | `stages/normalize.py` | бабелевские сокращения в `ctx.tex` | готов |
| macros | `stages/macros.py` | ручные переопределения из конфига | частично |
| figures | `stages/figures.py` | `preview` → PNG → `\includegraphics` | готов |
| pandoc | `stages/pandoc_run.py` | pandoc + фильтры, сбор сообщений | готов |
| postprocess | `stages/postprocess.py` | правки docx | заглушка |

## Два представления исходника

- `ctx.latex_tex` компилирует настоящий LaTeX. Меняется только там, где нужно спросить TeX
  (вставка меток). Иначе номера из `.aux` перестанут соответствовать тексту.
- `ctx.tex` читает pandoc. Сюда идут все переписывания для pandoc (нормализация, подстановка
  картинок, макросы).

## Как фильтры получают данные

`pandoc_run.py` пишет `workdir/t2d-meta.json`:

```json
{"labels": {"thm:main": "1.2"}, "theorems": {"theorem": {"style": "plain", "numbered": true, ...}},
 "proof_name": "Доказательство", "styles": {"plain": "Theorem", ...}}
```

путь передается метаданными `-M t2d-meta=<path>`, фильтр читает его через `t2d.load(doc.meta)`.

Фильтры выполняются по порядку из `FILTERS`: `crossref` → `theorems` → `equations`.

## Отчет

- Python: `ctx.report.warn(stage, code, detail, line=...)`.
- Lua: `t2d.report('warning', 'code', 'detail')` → stderr → `pandoc_run.collect_pandoc_messages`.
- Также в отчет идут: команды, которые pandoc пропустил (кроме безвредных из `HARMLESS_SKIPS`),
  и формулы, которые texmath не перевел (только имя непонятой команды).
- Результат: `<out>.report.md` для человека, `<out>.report.json` для разбора.
- Уровни: `error` — результат заведомо неполон; `warning` — вероятно неточно; `info` — к сведению
  (в том числе `stage.not-implemented`, пока этап не готов).

## Ошибки

- `StageError(code, detail)` — ожидаемая неудача этапа. Если этап `fatal`, конвейер останавливается.
- Любое другое исключение — баг: записывается как `internal-error` с файлом и строкой, без текста.
- Отчет пишется всегда, даже если docx не получился.

## Зачем запускать pandoc из каталога исходника

pandoc читает `\usepackage{local}` как файл `local.sty` относительно текущего каталога и так
узнает макросы личных пакетов. `--resource-path` на это не влияет. См. `docs/pandoc-behavior.md`.
